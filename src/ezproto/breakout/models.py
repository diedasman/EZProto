"""Data models for breakout-board generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SIDE_ORDER = ("N", "E", "S", "W")


@dataclass(frozen=True, slots=True)
class BreakoutConfig:
    """User-defined breakout board dimensions and placement rules."""

    footprint_path: Path
    board_width_mm: float
    board_height_mm: float
    pitch_mm: float
    sides: tuple[str, ...]
    header_offset_mm: float = 2.0
    margin_mm: float = 2.0
    board_name: str = ""
    header_drill_mm: float = 1.0
    header_pad_diameter_mm: float = 1.8
    trace_width_mm: float = 0.25

    def __post_init__(self) -> None:
        footprint_path = Path(self.footprint_path).expanduser()
        object.__setattr__(self, "footprint_path", footprint_path)
        object.__setattr__(
            self,
            "board_name",
            self._clean_board_name(self.board_name, footprint_path),
        )
        object.__setattr__(self, "sides", self._clean_sides(self.sides))
        self.validate()

    @staticmethod
    def _clean_board_name(name: str, footprint_path: Path) -> str:
        cleaned = (name or "").strip().replace('"', "'")
        if cleaned:
            return cleaned
        if footprint_path.suffix.lower() == ".kicad_mod":
            source_name = footprint_path.stem
        else:
            source_name = footprint_path.name
        source_name = source_name.replace("_", " ").strip()
        return source_name or "Breakout Board"

    @staticmethod
    def _clean_sides(sides: Iterable[str]) -> tuple[str, ...]:
        normalized: list[str] = []
        for side in sides:
            value = str(side).strip().upper()
            if value in SIDE_ORDER and value not in normalized:
                normalized.append(value)
        ordered = [side for side in SIDE_ORDER if side in normalized]
        return tuple(ordered)

    @property
    def output_directory_name(self) -> str:
        return self.board_name

    @property
    def output_file_stem(self) -> str:
        return self.board_name.replace(" ", "_")

    @property
    def output_file_name(self) -> str:
        return f"{self.output_file_stem}.kicad_pcb"

    @property
    def output_path(self) -> Path:
        return Path(self.output_directory_name) / self.output_file_name

    def output_path_for(self, base_directory: Path | str) -> Path:
        return Path(base_directory).expanduser() / self.output_path

    def validate(self) -> None:
        if self.board_width_mm <= 0:
            raise ValueError("Board width must be greater than 0 mm.")
        if self.board_height_mm <= 0:
            raise ValueError("Board height must be greater than 0 mm.")
        if self.pitch_mm <= 0:
            raise ValueError("Pitch must be greater than 0 mm.")
        if not self.sides:
            raise ValueError("Select at least one header side.")
        if self.header_offset_mm <= 0:
            raise ValueError("Header offset must be greater than 0 mm.")
        if self.margin_mm < 0:
            raise ValueError("Margin cannot be negative.")
        if self.header_drill_mm <= 0:
            raise ValueError("Header drill must be greater than 0 mm.")
        if self.header_pad_diameter_mm <= self.header_drill_mm:
            raise ValueError("Header pad diameter must be larger than the drill size.")
        if self.trace_width_mm <= 0:
            raise ValueError("Trace width must be greater than 0 mm.")
        if self.board_width_mm <= 2 * self.header_offset_mm:
            raise ValueError("Board width must leave room for the header offset.")
        if self.board_height_mm <= 2 * self.header_offset_mm:
            raise ValueError("Board height must leave room for the header offset.")
        if self.board_width_mm <= 2 * self.margin_mm:
            raise ValueError("Board width must leave room for the side margin.")
        if self.board_height_mm <= 2 * self.margin_mm:
            raise ValueError("Board height must leave room for the side margin.")
        if self.header_offset_mm <= self.header_pad_diameter_mm / 2.0:
            raise ValueError(
                "Header offset must be large enough to keep the header holes on the board."
            )


@dataclass(frozen=True, slots=True)
class Pad:
    """A logical pad used for routing and header generation."""

    name: str
    x: float
    y: float
    net: str | None
    width_mm: float = 0.0
    height_mm: float = 0.0


@dataclass(frozen=True, slots=True)
class HeaderPin:
    """A generated breakout header pin."""

    name: str
    x: float
    y: float
    net: str
    side: str


@dataclass(frozen=True, slots=True)
class TraceSegment:
    """A simple routed copper segment."""

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    net: str


@dataclass(frozen=True, slots=True)
class Bounds:
    """Axis-aligned bounds for the imported footprint."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width_mm(self) -> float:
        return self.max_x - self.min_x

    @property
    def height_mm(self) -> float:
        return self.max_y - self.min_y


@dataclass(frozen=True, slots=True)
class ParsedFootprint:
    """The parsed KiCad footprint definition and its logical pads."""

    path: Path
    name: str
    tree: Any
    pads: tuple[Pad, ...]
    bounds: Bounds
    physical_pad_count: int


@dataclass(frozen=True, slots=True)
class BreakoutBoard:
    """A generated breakout board ready to render into KiCad."""

    config: BreakoutConfig
    footprint: ParsedFootprint
    footprint_origin_x: float
    footprint_origin_y: float
    pads: tuple[Pad, ...]
    headers: tuple[HeaderPin, ...]
    traces: tuple[TraceSegment, ...]

    @property
    def net_names(self) -> tuple[str, ...]:
        seen: list[str] = []
        for pad in self.pads:
            if pad.net and pad.net not in seen:
                seen.append(pad.net)
        return tuple(seen)
