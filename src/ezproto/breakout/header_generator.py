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
    headers: list[HeaderPin] = []
    pad_index = 0

    for side in config.sides:
        count = allocations[side]
        if count == 0:
            continue
        positions = _positions_for_side(side, count, config)
        for offset in range(count):
            pad = pads[pad_index + offset]
            headers.append(
                HeaderPin(
                    name=pad.name,
                    x=positions[offset][0],
                    y=positions[offset][1],
                    net=pad.net or f"PAD_{pad.name}",
                    side=side,
                )
            )
        pad_index += count

    return headers


def _side_capacity(side: str, config: BreakoutConfig) -> int:
    usable_span = (
        config.board_width_mm - (2 * config.margin_mm)
        if side in {"N", "S"}
        else config.board_height_mm - (2 * config.margin_mm)
    )
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


def _positions_for_side(
    side: str,
    count: int,
    config: BreakoutConfig,
) -> list[tuple[float, float]]:
    span = (count - 1) * config.pitch_mm
    positions: list[tuple[float, float]] = []

    if side in {"N", "S"}:
        start = (config.board_width_mm / 2.0) - (span / 2.0)
        end = start + span
        if start < config.margin_mm or end > config.board_width_mm - config.margin_mm:
            raise ValueError(
                f"Not enough width to place {count} header pins on the {side} side."
            )
        y_pos = (
            config.header_offset_mm
            if side == "N"
            else config.board_height_mm - config.header_offset_mm
        )
        for index in range(count):
            positions.append((start + (index * config.pitch_mm), y_pos))
        return positions

    start = (config.board_height_mm / 2.0) - (span / 2.0)
    end = start + span
    if start < config.margin_mm or end > config.board_height_mm - config.margin_mm:
        raise ValueError(
            f"Not enough height to place {count} header pins on the {side} side."
        )
    x_pos = (
        config.board_width_mm - config.header_offset_mm
        if side == "E"
        else config.header_offset_mm
    )
    for index in range(count):
        positions.append((x_pos, start + (index * config.pitch_mm)))
    return positions
