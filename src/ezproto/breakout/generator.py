"""Breakout board orchestration."""

from __future__ import annotations

from math import cos, hypot, pi, sin
import re

from .footprint_parser import load_footprint
from .header_generator import generate_headers
from .models import BreakoutBoard, BreakoutConfig, Pad
from .router import route


def generate_breakout(config: BreakoutConfig) -> BreakoutBoard:
    """Generate a breakout board from a KiCad footprint."""

    footprint = load_footprint(config.footprint_path)
    origin_x = config.board_width_mm / 2.0
    origin_y = config.board_height_mm / 2.0
    _validate_footprint_fits(footprint, config, origin_x, origin_y)

    placed_pads = tuple(
        Pad(
            name=pad.name,
            x=origin_x + pad.x,
            y=origin_y + pad.y,
            net=_net_name(pad.name),
            width_mm=pad.width_mm,
            height_mm=pad.height_mm,
        )
        for pad in footprint.pads
    )
    headers = tuple(generate_headers(placed_pads, config))
    routing_warnings: list[str] = []
    routing_debug_svg: list[str] = []
    traces = tuple(
        route(
            placed_pads,
            headers,
            config=config,
            warnings=routing_warnings,
            debug_svg=routing_debug_svg if config.debug_routing else None,
        )
    )
    _validate_generated_geometry(
        config=config,
        pads=placed_pads,
        headers=headers,
        traces=traces,
    )

    return BreakoutBoard(
        config=config,
        footprint=footprint,
        footprint_origin_x=origin_x,
        footprint_origin_y=origin_y,
        pads=placed_pads,
        headers=headers,
        traces=traces,
        routing_warnings=tuple(routing_warnings),
        routing_debug_svg=routing_debug_svg[0] if routing_debug_svg else None,
    )


def _validate_footprint_fits(
    footprint,
    config: BreakoutConfig,
    origin_x: float,
    origin_y: float,
) -> None:
    min_x = origin_x + footprint.bounds.min_x
    max_x = origin_x + footprint.bounds.max_x
    min_y = origin_y + footprint.bounds.min_y
    max_y = origin_y + footprint.bounds.max_y

    if min_x < config.margin_mm or max_x > config.board_width_mm - config.margin_mm:
        raise ValueError(
            "Board width is too small to place the footprint with the requested margin."
        )
    if min_y < config.margin_mm or max_y > config.board_height_mm - config.margin_mm:
        raise ValueError(
            "Board height is too small to place the footprint with the requested margin."
        )
    for point_x, point_y in (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    ):
        if not config.point_is_inside_outline(point_x, point_y):
            raise ValueError(
                "Rounded corners clip the footprint; reduce the corner radius "
                "or increase the board dimensions."
            )


def _net_name(pad_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", pad_name.strip())
    return f"PAD_{cleaned or 'UNNAMED'}"


def _validate_generated_geometry(
    *,
    config: BreakoutConfig,
    pads: tuple[Pad, ...],
    headers,
    traces,
) -> None:
    for pad in pads:
        half_width = pad.width_mm / 2.0
        half_height = pad.height_mm / 2.0
        for point_x, point_y in (
            (pad.x - half_width, pad.y - half_height),
            (pad.x + half_width, pad.y - half_height),
            (pad.x + half_width, pad.y + half_height),
            (pad.x - half_width, pad.y + half_height),
        ):
            if not config.point_is_inside_outline(point_x, point_y):
                raise ValueError(
                    f"Rounded corners clip footprint pad '{pad.name}'."
                )

    header_radius = config.header_pad_diameter_mm / 2.0
    for header in headers:
        for point_x, point_y in _sample_circle(header.x, header.y, header_radius):
            if not config.point_is_inside_outline(point_x, point_y):
                raise ValueError(
                    f"Rounded corners clip header pad '{header.name}'."
                )

    mounting_hole_radius = config.mounting_hole_diameter_mm / 2.0
    if mounting_hole_radius > 0:
        clearance = 0.2
        for hole_x, hole_y in config.iter_mounting_hole_positions():
            for point_x, point_y in _sample_circle(
                hole_x,
                hole_y,
                mounting_hole_radius + clearance,
            ):
                if not config.point_is_inside_outline(point_x, point_y):
                    raise ValueError(
                        "Rounded corners clip the mounting hole; reduce the corner radius "
                        "or increase the clearances."
                    )

            for pad in pads:
                if _circle_intersects_pad(
                    center_x=hole_x,
                    center_y=hole_y,
                    radius=mounting_hole_radius + clearance,
                    pad=pad,
                ):
                    raise ValueError(
                        f"Mounting hole overlaps footprint pad '{pad.name}'."
                    )

            for header in headers:
                if _circles_overlap(
                    first_x=hole_x,
                    first_y=hole_y,
                    first_radius=mounting_hole_radius + clearance,
                    second_x=header.x,
                    second_y=header.y,
                    second_radius=header_radius,
                ):
                    raise ValueError(
                        f"Mounting hole overlaps header pad '{header.name}'."
                    )

    for trace in traces:
        for point_x, point_y in _sample_trace(trace):
            if not config.point_is_inside_outline(point_x, point_y):
                raise ValueError(
                    f"Trace '{trace.net}' extends beyond the board outline."
                )


def _sample_circle(
    center_x: float,
    center_y: float,
    radius: float,
    *,
    steps: int = 24,
) -> list[tuple[float, float]]:
    return [
        (
            center_x + (cos((2 * pi * step) / steps) * radius),
            center_y + (sin((2 * pi * step) / steps) * radius),
        )
        for step in range(steps)
    ]


def _sample_trace(trace, *, step_mm: float = 0.2) -> list[tuple[float, float]]:
    length = max(abs(trace.end_x - trace.start_x), abs(trace.end_y - trace.start_y))
    steps = max(int(length / step_mm), 1)
    return [
        (
            trace.start_x + ((trace.end_x - trace.start_x) * (step / steps)),
            trace.start_y + ((trace.end_y - trace.start_y) * (step / steps)),
        )
        for step in range(steps + 1)
    ]


def _circle_intersects_pad(
    *,
    center_x: float,
    center_y: float,
    radius: float,
    pad: Pad,
) -> bool:
    half_width = pad.width_mm / 2.0
    half_height = pad.height_mm / 2.0
    nearest_x = min(max(center_x, pad.x - half_width), pad.x + half_width)
    nearest_y = min(max(center_y, pad.y - half_height), pad.y + half_height)
    return hypot(center_x - nearest_x, center_y - nearest_y) < radius


def _circles_overlap(
    *,
    first_x: float,
    first_y: float,
    first_radius: float,
    second_x: float,
    second_y: float,
    second_radius: float,
) -> bool:
    return hypot(first_x - second_x, first_y - second_y) < (first_radius + second_radius)
