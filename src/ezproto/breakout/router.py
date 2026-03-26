"""Simple breakout routing helpers."""

from __future__ import annotations

from .models import HeaderPin, Pad, TraceSegment


def route(
    pads: list[Pad] | tuple[Pad, ...],
    headers: list[HeaderPin] | tuple[HeaderPin, ...],
) -> list[TraceSegment]:
    """Route logical pads to generated header pins with simple Manhattan segments."""

    if len(pads) != len(headers):
        raise ValueError("Pad and header counts must match for routing.")

    traces: list[TraceSegment] = []
    for pad, header in zip(pads, headers):
        if header.side in {"N", "S"}:
            waypoint = (header.x, pad.y)
        else:
            waypoint = (pad.x, header.y)

        if not _same_point(pad.x, pad.y, waypoint[0], waypoint[1]):
            traces.append(
                TraceSegment(
                    start_x=pad.x,
                    start_y=pad.y,
                    end_x=waypoint[0],
                    end_y=waypoint[1],
                    net=header.net,
                )
            )
        if not _same_point(waypoint[0], waypoint[1], header.x, header.y):
            traces.append(
                TraceSegment(
                    start_x=waypoint[0],
                    start_y=waypoint[1],
                    end_x=header.x,
                    end_y=header.y,
                    net=header.net,
                )
            )
    return traces


def _same_point(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> bool:
    return abs(start_x - end_x) < 1e-9 and abs(start_y - end_y) < 1e-9
