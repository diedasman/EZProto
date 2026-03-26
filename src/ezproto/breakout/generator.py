"""Breakout board orchestration."""

from __future__ import annotations

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
    traces = tuple(route(placed_pads, headers))

    return BreakoutBoard(
        config=config,
        footprint=footprint,
        footprint_origin_x=origin_x,
        footprint_origin_y=origin_y,
        pads=placed_pads,
        headers=headers,
        traces=traces,
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


def _net_name(pad_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", pad_name.strip())
    return f"PAD_{cleaned or 'UNNAMED'}"
