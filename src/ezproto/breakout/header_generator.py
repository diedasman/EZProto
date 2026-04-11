"""Header placement for breakout boards."""

from __future__ import annotations

from .models import BreakoutConfig, HeaderPin, Pad


def generate_headers(pads: list[Pad] | tuple[Pad, ...], config: BreakoutConfig) -> list[HeaderPin]:
    """Generate breakout headers around the selected board edges."""

    if not pads:
        raise ValueError("The footprint must contain at least one pad.")

    capacities = {side: _side_capacity(side, config) for side in config.sides}
    total_capacity = sum(capacities.values())
    if total_capacity < len(pads):
        raise ValueError(
            "The selected board edges do not have enough room for all header pins "
            "at the requested pitch."
        )

    allocations = _allocate_counts(len(pads), config.sides, capacities)
    pad_groups = _assign_pads_to_sides(pads, allocations, config.sides)
    headers: list[HeaderPin] = []

    for side in config.sides:
        assigned_pads = _sort_pads_for_side(pad_groups[side], side)
        if not assigned_pads:
            continue
        positions = _positions_for_side(side, len(assigned_pads), config)
        for pad, (x_pos, y_pos) in zip(assigned_pads, positions):
            headers.append(
                HeaderPin(
                    name=pad.name,
                    x=x_pos,
                    y=y_pos,
                    net=pad.net or f"PAD_{pad.name}",
                    side=side,
                )
            )

    return headers


def _side_capacity(side: str, config: BreakoutConfig) -> int:
    minimum, maximum = config.header_position_limits(side)
    usable_span = maximum - minimum
    if usable_span < 0:
        return 0
    return int(usable_span // config.pitch_mm) + 1


def _allocate_counts(
    pin_count: int,
    sides: tuple[str, ...],
    capacities: dict[str, int],
) -> dict[str, int]:
    base_count = pin_count // len(sides)
    allocations = {
        side: min(base_count, capacities[side])
        for side in sides
    }
    remaining = pin_count - sum(allocations.values())

    while remaining > 0:
        progress = False
        for side in sides:
            if allocations[side] >= capacities[side]:
                continue
            allocations[side] += 1
            remaining -= 1
            progress = True
            if remaining == 0:
                break
        if not progress:
            raise ValueError("Unable to allocate header pins across the selected sides.")

    return allocations


def _assign_pads_to_sides(
    pads: list[Pad] | tuple[Pad, ...],
    allocations: dict[str, int],
    sides: tuple[str, ...],
) -> dict[str, list[Pad]]:
    remaining = list(pads)
    assignments = {side: [] for side in sides}
    active_sides = [side for side in sides if allocations[side] > 0]

    if not active_sides:
        return assignments

    for side in active_sides[:-1]:
        target_count = allocations[side]
        ranked = sorted(remaining, key=lambda pad: _side_affinity_key(pad, side))
        chosen = ranked[:target_count]
        assignments[side] = chosen
        chosen_names = {pad.name for pad in chosen}
        remaining = [pad for pad in remaining if pad.name not in chosen_names]

    assignments[active_sides[-1]] = list(remaining)
    return assignments


def _side_affinity_key(pad: Pad, side: str) -> tuple[float, float, float, str]:
    if side == "N":
        return (pad.y, abs(pad.x), pad.x, pad.name)
    if side == "S":
        return (-pad.y, abs(pad.x), pad.x, pad.name)
    if side == "E":
        return (-pad.x, abs(pad.y), pad.y, pad.name)
    return (pad.x, abs(pad.y), pad.y, pad.name)


def _sort_pads_for_side(pads: list[Pad], side: str) -> list[Pad]:
    if side in {"N", "S"}:
        return sorted(pads, key=lambda pad: (pad.x, pad.y, pad.name))
    return sorted(pads, key=lambda pad: (pad.y, pad.x, pad.name))


def _positions_for_side(
    side: str,
    count: int,
    config: BreakoutConfig,
) -> list[tuple[float, float]]:
    span = (count - 1) * config.pitch_mm
    positions: list[tuple[float, float]] = []

    if side in {"N", "S"}:
        minimum, maximum = config.header_position_limits(side)
        available_span = maximum - minimum
        if span > available_span:
            raise ValueError(
                f"Not enough width to place {count} header pins on the {side} side."
            )
        start = minimum + ((available_span - span) / 2.0)
        y_pos = (
            config.header_offset_mm
            if side == "N"
            else config.board_height_mm - config.header_offset_mm
        )
        for index in range(count):
            positions.append((start + (index * config.pitch_mm), y_pos))
        return positions

    minimum, maximum = config.header_position_limits(side)
    available_span = maximum - minimum
    if span > available_span:
        raise ValueError(
            f"Not enough height to place {count} header pins on the {side} side."
        )
    start = minimum + ((available_span - span) / 2.0)
    x_pos = (
        config.board_width_mm - config.header_offset_mm
        if side == "E"
        else config.header_offset_mm
    )
    for index in range(count):
        positions.append((x_pos, start + (index * config.pitch_mm)))
    return positions
