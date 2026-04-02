"""Breakout routing helpers with basic clearance-aware pathfinding."""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from math import hypot

from .models import BreakoutConfig, HeaderPin, Pad, TraceSegment

EPSILON = 1e-6
SAMPLE_STEP_MM = 0.2
TURN_PENALTY = 0.4


@dataclass(frozen=True, slots=True)
class _Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class _Rect:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def contains(self, point: _Point) -> bool:
        return (
            (self.min_x + EPSILON) < point.x < (self.max_x - EPSILON)
            and (self.min_y + EPSILON) < point.y < (self.max_y - EPSILON)
        )


def route(
    pads: list[Pad] | tuple[Pad, ...],
    headers: list[HeaderPin] | tuple[HeaderPin, ...],
    *,
    config: BreakoutConfig,
) -> list[TraceSegment]:
    """Route logical pads to generated header pins without overlapping copper."""

    if len(pads) != len(headers):
        raise ValueError("Pad and header counts must match for routing.")

    header_by_net = {header.net: header for header in headers}
    if len(header_by_net) != len(headers):
        raise ValueError("Header nets must be unique for breakout routing.")

    pairs: list[tuple[Pad, HeaderPin]] = []
    for pad in pads:
        if pad.net is None or pad.net not in header_by_net:
            raise ValueError(f"Unable to find a header pin for pad '{pad.name}'.")
        pairs.append((pad, header_by_net[pad.net]))

    routed: list[TraceSegment] = []
    for pad, header in sorted(pairs, key=_route_priority):
        obstacles = _build_obstacles(
            pads=pads,
            headers=headers,
            traces=routed,
            own_net=header.net,
            config=config,
        )
        path = _find_path(
            start=_Point(pad.x, pad.y),
            end=_Point(header.x, header.y),
            pads=pads,
            headers=headers,
            obstacles=obstacles,
            config=config,
        )
        if path is None:
            raise ValueError(
                f"Unable to route pad '{pad.name}' to the {header.side} header."
            )
            # raise Warning(
            #     f"Unable to route pad '{pad.name}' to the {header.side} header. "
            #     "Consider adjusting the breakout settings to create more space for routing."
            # )
        mitred_path = _apply_miters(path, obstacles=obstacles, config=config)
        routed.extend(_segments_from_path(mitred_path, net=header.net))

    _validate_routes(routed, pads=pads, headers=headers, config=config)
    return routed


def _route_priority(pair: tuple[Pad, HeaderPin]) -> tuple[float, str, str]:
    pad, header = pair
    return (
        abs(pad.x - header.x) + abs(pad.y - header.y),
        header.side,
        pad.name,
    )


def _build_obstacles(
    *,
    pads: list[Pad] | tuple[Pad, ...],
    headers: list[HeaderPin] | tuple[HeaderPin, ...],
    traces: list[TraceSegment],
    own_net: str,
    config: BreakoutConfig,
) -> list[_Rect]:
    copper_margin = (config.trace_width_mm / 2.0) + config.trace_clearance_mm
    obstacles: list[_Rect] = []

    for pad in pads:
        if pad.net == own_net:
            continue
        half_width = max(pad.width_mm / 2.0, copper_margin)
        half_height = max(pad.height_mm / 2.0, copper_margin)
        obstacles.append(
            _Rect(
                min_x=pad.x - (half_width + config.trace_clearance_mm),
                min_y=pad.y - (half_height + config.trace_clearance_mm),
                max_x=pad.x + (half_width + config.trace_clearance_mm),
                max_y=pad.y + (half_height + config.trace_clearance_mm),
            )
        )

    header_radius = (config.header_pad_diameter_mm / 2.0) + config.trace_clearance_mm
    for header in headers:
        if header.net == own_net:
            continue
        obstacles.append(
            _Rect(
                min_x=header.x - header_radius,
                min_y=header.y - header_radius,
                max_x=header.x + header_radius,
                max_y=header.y + header_radius,
            )
        )

    trace_radius = (config.trace_width_mm / 2.0) + config.trace_clearance_mm
    for trace in traces:
        obstacles.append(
            _Rect(
                min_x=min(trace.start_x, trace.end_x) - trace_radius,
                min_y=min(trace.start_y, trace.end_y) - trace_radius,
                max_x=max(trace.start_x, trace.end_x) + trace_radius,
                max_y=max(trace.start_y, trace.end_y) + trace_radius,
            )
        )

    return obstacles


def _find_path(
    *,
    start: _Point,
    end: _Point,
    pads: list[Pad] | tuple[Pad, ...],
    headers: list[HeaderPin] | tuple[HeaderPin, ...],
    obstacles: list[_Rect],
    config: BreakoutConfig,
) -> list[_Point] | None:
    x_values = _candidate_axis_values(
        maximum=config.board_width_mm,
        current=start.x,
        target=end.x,
        pads=pads,
        headers=headers,
        obstacles=obstacles,
        is_horizontal=True,
        config=config,
    )
    y_values = _candidate_axis_values(
        maximum=config.board_height_mm,
        current=start.y,
        target=end.y,
        pads=pads,
        headers=headers,
        obstacles=obstacles,
        is_horizontal=False,
        config=config,
    )

    nodes = _build_nodes(
        x_values=x_values,
        y_values=y_values,
        start=start,
        end=end,
        obstacles=obstacles,
        config=config,
    )
    if start not in nodes or end not in nodes:
        return None

    adjacency = _build_adjacency(nodes=nodes, obstacles=obstacles, config=config)
    return _a_star(start=start, end=end, adjacency=adjacency)


def _candidate_axis_values(
    *,
    maximum: float,
    current: float,
    target: float,
    pads: list[Pad] | tuple[Pad, ...],
    headers: list[HeaderPin] | tuple[HeaderPin, ...],
    obstacles: list[_Rect],
    is_horizontal: bool,
    config: BreakoutConfig,
) -> list[float]:
    spacing = max(config.route_spacing_mm, config.header_pad_diameter_mm / 2.0)
    values = {
        0.0,
        maximum,
        current,
        target,
    }

    if is_horizontal:
        values.update({config.margin_mm, maximum - config.margin_mm})
        for pad in pads:
            values.update(
                {
                    pad.x,
                    pad.x - spacing,
                    pad.x + spacing,
                    pad.x - (2.0 * spacing),
                    pad.x + (2.0 * spacing),
                }
            )
        for header in headers:
            values.update({header.x, header.x - spacing, header.x + spacing})
        for obstacle in obstacles:
            values.update({obstacle.min_x, obstacle.max_x})
    else:
        values.update({config.header_offset_mm, maximum - config.header_offset_mm})
        for pad in pads:
            values.update(
                {
                    pad.y,
                    pad.y - spacing,
                    pad.y + spacing,
                    pad.y - (2.0 * spacing),
                    pad.y + (2.0 * spacing),
                }
            )
        for header in headers:
            values.update({header.y, header.y - spacing, header.y + spacing})
        for obstacle in obstacles:
            values.update({obstacle.min_y, obstacle.max_y})

    return sorted(
        {
            _clamp(_quantize(value), lower=0.0, upper=maximum)
            for value in values
            if -EPSILON <= value <= maximum + EPSILON
        }
    )


def _build_nodes(
    *,
    x_values: list[float],
    y_values: list[float],
    start: _Point,
    end: _Point,
    obstacles: list[_Rect],
    config: BreakoutConfig,
) -> set[_Point]:
    nodes: set[_Point] = {start, end}
    for x_value in x_values:
        for y_value in y_values:
            point = _Point(x_value, y_value)
            if point in {start, end}:
                nodes.add(point)
                continue
            if not config.point_is_inside_outline(point.x, point.y):
                continue
            if _point_blocked(point, obstacles):
                continue
            nodes.add(point)
    return nodes


def _build_adjacency(
    *,
    nodes: set[_Point],
    obstacles: list[_Rect],
    config: BreakoutConfig,
) -> dict[_Point, list[_Point]]:
    adjacency = {node: [] for node in nodes}
    rows: dict[float, list[_Point]] = {}
    columns: dict[float, list[_Point]] = {}

    for node in nodes:
        rows.setdefault(node.y, []).append(node)
        columns.setdefault(node.x, []).append(node)

    for row in rows.values():
        ordered = sorted(row, key=lambda point: point.x)
        for left, right in zip(ordered, ordered[1:]):
            if _segment_is_clear(left, right, obstacles=obstacles, config=config):
                adjacency[left].append(right)
                adjacency[right].append(left)

    for column in columns.values():
        ordered = sorted(column, key=lambda point: point.y)
        for top, bottom in zip(ordered, ordered[1:]):
            if _segment_is_clear(top, bottom, obstacles=obstacles, config=config):
                adjacency[top].append(bottom)
                adjacency[bottom].append(top)

    return adjacency


def _a_star(
    *,
    start: _Point,
    end: _Point,
    adjacency: dict[_Point, list[_Point]],
) -> list[_Point] | None:
    frontier: list[tuple[float, int, _Point, str | None]] = []
    ticket = count()
    heappush(frontier, (0.0, next(ticket), start, None))

    best_cost: dict[tuple[_Point, str | None], float] = {(start, None): 0.0}
    parents: dict[tuple[_Point, str | None], tuple[_Point, str | None] | None] = {
        (start, None): None
    }

    while frontier:
        _, _, node, direction = heappop(frontier)
        state = (node, direction)
        current_cost = best_cost[state]

        if node == end:
            return _reconstruct_path(state, parents)

        for neighbour in adjacency[node]:
            next_direction = _segment_direction(node, neighbour)
            step_cost = _distance(node, neighbour)
            if direction is not None and next_direction != direction:
                step_cost += TURN_PENALTY

            next_state = (neighbour, next_direction)
            total_cost = current_cost + step_cost
            if total_cost >= best_cost.get(next_state, float("inf")):
                continue

            best_cost[next_state] = total_cost
            parents[next_state] = state
            heuristic = abs(neighbour.x - end.x) + abs(neighbour.y - end.y)
            heappush(
                frontier,
                (total_cost + heuristic, next(ticket), neighbour, next_direction),
            )

    return None


def _reconstruct_path(
    state: tuple[_Point, str | None],
    parents: dict[tuple[_Point, str | None], tuple[_Point, str | None] | None],
) -> list[_Point]:
    path: list[_Point] = []
    current: tuple[_Point, str | None] | None = state
    while current is not None:
        path.append(current[0])
        current = parents[current]
    path.reverse()
    return _compress_path(path)


def _compress_path(path: list[_Point]) -> list[_Point]:
    if len(path) <= 2:
        return path

    compressed = [path[0]]
    for index in range(1, len(path) - 1):
        point = path[index]
        if _is_collinear(compressed[-1], point, path[index + 1]):
            continue
        compressed.append(point)
    compressed.append(path[-1])
    return _dedupe_path(compressed)


def _dedupe_path(path: list[_Point]) -> list[_Point]:
    deduped: list[_Point] = []
    for point in path:
        if deduped and _same_point(deduped[-1], point):
            continue
        deduped.append(point)
    return deduped


def _apply_miters(
    path: list[_Point],
    *,
    obstacles: list[_Rect],
    config: BreakoutConfig,
) -> list[_Point]:
    if len(path) < 3:
        return path

    adjusted: list[_Point] = [path[0]]
    for index in range(1, len(path) - 1):
        previous = adjusted[-1]
        corner = path[index]
        next_point = path[index + 1]

        if _is_collinear(previous, corner, next_point):
            continue

        inset = min(
            max(config.trace_width_mm * 1.5, 0.4),
            (_distance(previous, corner) / 2.0) - EPSILON,
            (_distance(corner, next_point) / 2.0) - EPSILON,
        )
        if inset <= 0.1:
            adjusted.append(corner)
            continue

        before = _point_towards(corner, previous, inset)
        after = _point_towards(corner, next_point, inset)

        if (
            not _segment_is_clear(previous, before, obstacles=obstacles, config=config)
            or not _segment_is_clear(before, after, obstacles=obstacles, config=config)
            or not config.point_is_inside_outline(after.x, after.y)
        ):
            adjusted.append(corner)
            continue

        adjusted.extend([before, after])

    adjusted.append(path[-1])
    return _dedupe_path(adjusted)


def _segments_from_path(path: list[_Point], *, net: str) -> list[TraceSegment]:
    segments: list[TraceSegment] = []
    for start, end in zip(path, path[1:]):
        if _same_point(start, end):
            continue
        segments.append(
            TraceSegment(
                start_x=start.x,
                start_y=start.y,
                end_x=end.x,
                end_y=end.y,
                net=net,
            )
        )
    return segments


def _validate_routes(
    traces: list[TraceSegment],
    *,
    pads: list[Pad] | tuple[Pad, ...],
    headers: list[HeaderPin] | tuple[HeaderPin, ...],
    config: BreakoutConfig,
) -> None:
    for trace in traces:
        if _distance(
            _Point(trace.start_x, trace.start_y),
            _Point(trace.end_x, trace.end_y),
        ) <= EPSILON:
            raise ValueError("Routing produced a zero-length trace segment.")
        if not _segment_has_supported_angle(trace):
            raise ValueError("Routing produced a trace angle that is not 45 or 90 degrees.")
        if not _segment_is_clear(
            _Point(trace.start_x, trace.start_y),
            _Point(trace.end_x, trace.end_y),
            obstacles=_build_obstacles(
                pads=pads,
                headers=headers,
                traces=[],
                own_net=trace.net,
                config=config,
            ),
            config=config,
        ):
            raise ValueError("Routing produced a trace that violates the breakout clearances.")

    for index, first in enumerate(traces):
        for second in traces[index + 1 :]:
            if first.net == second.net:
                continue
            if _segments_intersect(first, second):
                raise ValueError("Routing produced intersecting breakout traces.")


def _segment_has_supported_angle(segment: TraceSegment) -> bool:
    dx = abs(segment.end_x - segment.start_x)
    dy = abs(segment.end_y - segment.start_y)
    return dx <= EPSILON or dy <= EPSILON or abs(dx - dy) <= EPSILON


def _segments_intersect(first: TraceSegment, second: TraceSegment) -> bool:
    first_start = _Point(first.start_x, first.start_y)
    first_end = _Point(first.end_x, first.end_y)
    second_start = _Point(second.start_x, second.start_y)
    second_end = _Point(second.end_x, second.end_y)

    if any(
        _same_point(point_a, point_b)
        for point_a in (first_start, first_end)
        for point_b in (second_start, second_end)
    ):
        return False

    return _raw_segments_intersect(first_start, first_end, second_start, second_end)


def _raw_segments_intersect(
    first_start: _Point,
    first_end: _Point,
    second_start: _Point,
    second_end: _Point,
) -> bool:
    orientation_1 = _orientation(first_start, first_end, second_start)
    orientation_2 = _orientation(first_start, first_end, second_end)
    orientation_3 = _orientation(second_start, second_end, first_start)
    orientation_4 = _orientation(second_start, second_end, first_end)

    if orientation_1 == 0 and _point_on_segment(second_start, first_start, first_end):
        return True
    if orientation_2 == 0 and _point_on_segment(second_end, first_start, first_end):
        return True
    if orientation_3 == 0 and _point_on_segment(first_start, second_start, second_end):
        return True
    if orientation_4 == 0 and _point_on_segment(first_end, second_start, second_end):
        return True

    return orientation_1 != orientation_2 and orientation_3 != orientation_4


def _orientation(first: _Point, second: _Point, third: _Point) -> int:
    value = (
        (second.y - first.y) * (third.x - second.x)
        - (second.x - first.x) * (third.y - second.y)
    )
    if abs(value) <= EPSILON:
        return 0
    return 1 if value > 0 else 2


def _point_on_segment(point: _Point, start: _Point, end: _Point) -> bool:
    return (
        min(start.x, end.x) - EPSILON <= point.x <= max(start.x, end.x) + EPSILON
        and min(start.y, end.y) - EPSILON <= point.y <= max(start.y, end.y) + EPSILON
    )


def _point_blocked(point: _Point, obstacles: list[_Rect]) -> bool:
    return any(obstacle.contains(point) for obstacle in obstacles)


def _segment_is_clear(
    start: _Point,
    end: _Point,
    *,
    obstacles: list[_Rect],
    config: BreakoutConfig,
) -> bool:
    for point in _sample_segment(start, end):
        if not config.point_is_inside_outline(point.x, point.y):
            return False
        if _point_blocked(point, obstacles):
            return False
    return True


def _sample_segment(start: _Point, end: _Point) -> list[_Point]:
    length = _distance(start, end)
    if length <= EPSILON:
        return [start]

    steps = max(int(length / SAMPLE_STEP_MM), 1)
    points: list[_Point] = []
    for step in range(steps + 1):
        fraction = step / steps
        points.append(
            _Point(
                x=start.x + ((end.x - start.x) * fraction),
                y=start.y + ((end.y - start.y) * fraction),
            )
        )
    return points


def _segment_direction(start: _Point, end: _Point) -> str:
    return "V" if abs(start.x - end.x) <= EPSILON else "H"


def _distance(start: _Point, end: _Point) -> float:
    return hypot(end.x - start.x, end.y - start.y)


def _is_collinear(first: _Point, second: _Point, third: _Point) -> bool:
    return (
        abs((second.x - first.x) * (third.y - second.y) - (second.y - first.y) * (third.x - second.x))
        <= EPSILON
    )


def _point_towards(origin: _Point, target: _Point, distance: float) -> _Point:
    total_distance = _distance(origin, target)
    if total_distance <= EPSILON:
        return origin
    fraction = distance / total_distance
    return _Point(
        x=_quantize(origin.x + ((target.x - origin.x) * fraction)),
        y=_quantize(origin.y + ((target.y - origin.y) * fraction)),
    )


def _same_point(first: _Point, second: _Point) -> bool:
    return abs(first.x - second.x) <= EPSILON and abs(first.y - second.y) <= EPSILON


def _clamp(value: float, *, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _quantize(value: float) -> float:
    return round(value, 3)
