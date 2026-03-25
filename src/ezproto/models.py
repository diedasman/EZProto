"""Core protoboard parameter and geometry models."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, pi, sin
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True, slots=True)
class BoardParameters:
    """User-defined dimensions for a protoboard."""

    columns: int
    rows: int
    pitch_mm: float
    pth_drill_mm: float
    pad_diameter_mm: float
    mounting_hole_diameter_mm: float
    edge_margin_mm: float
    rounded_corner_radius_mm: float = 0.0
    board_name: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "board_name", self._clean_board_name(self.board_name))
        self.validate()

    @staticmethod
    def _clean_board_name(name: str) -> str:
        cleaned = (name or "").strip().replace('"', "'")
        return cleaned or "Protoboard"

    @property
    def hole_count(self) -> int:
        return self.columns * self.rows

    @property
    def grid_width_mm(self) -> float:
        return (self.columns - 1) * self.pitch_mm

    @property
    def grid_height_mm(self) -> float:
        return (self.rows - 1) * self.pitch_mm

    @property
    def board_width_mm(self) -> float:
        return self.grid_width_mm + (2 * self.edge_margin_mm)

    @property
    def board_height_mm(self) -> float:
        return self.grid_height_mm + (2 * self.edge_margin_mm)

    @property
    def mounting_hole_inset_mm(self) -> float:
        return self.edge_margin_mm / 2.0

    @property
    def mounting_hole_count(self) -> int:
        return 4 if self.mounting_hole_diameter_mm > 0 else 0

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

    @property
    def has_rounded_corners(self) -> bool:
        return self.rounded_corner_radius_mm > 0

    def iter_pad_positions(self) -> Iterator[tuple[float, float]]:
        origin_x = self.edge_margin_mm
        origin_y = self.edge_margin_mm

        for row in range(self.rows):
            y_pos = origin_y + (row * self.pitch_mm)
            for column in range(self.columns):
                x_pos = origin_x + (column * self.pitch_mm)
                yield x_pos, y_pos

    def iter_mounting_hole_positions(self) -> Iterator[tuple[float, float]]:
        if self.mounting_hole_diameter_mm <= 0:
            return

        inset = self.mounting_hole_inset_mm
        max_x = self.board_width_mm - inset
        max_y = self.board_height_mm - inset

        yield inset, inset
        yield max_x, inset
        yield inset, max_y
        yield max_x, max_y

    def validate(self) -> None:
        if self.columns < 1:
            raise ValueError("Columns must be at least 1.")
        if self.rows < 1:
            raise ValueError("Rows must be at least 1.")
        if self.pitch_mm <= 0:
            raise ValueError("Pitch must be greater than 0 mm.")
        if self.pth_drill_mm <= 0:
            raise ValueError("PTH drill must be greater than 0 mm.")
        if self.pad_diameter_mm <= 0:
            raise ValueError("Pad diameter must be greater than 0 mm.")
        if self.pad_diameter_mm <= self.pth_drill_mm:
            raise ValueError("Pad diameter must be larger than the PTH drill.")
        if self.pad_diameter_mm == self.pitch_mm:
            raise ValueError("Pad diameter must be smaller than the pitch to avoid overlap.")
        if self.edge_margin_mm <= 0:
            raise ValueError("Edge margin must be greater than 0 mm.")
        if self.mounting_hole_diameter_mm < 0:
            raise ValueError("Mounting hole diameter cannot be negative.")
        if self.rounded_corner_radius_mm < 0:
            raise ValueError("Rounded corner radius cannot be negative.")
        if self.rounded_corner_radius_mm > min(self.board_width_mm, self.board_height_mm) / 2.0:
            raise ValueError("Rounded corner radius is too large for the board size.")

        if self.mounting_hole_diameter_mm == 0:
            self._validate_rounded_corners()
            return

        if self.mounting_hole_diameter_mm > self.edge_margin_mm:
            raise ValueError("Mounting hole diameter must fit inside the edge margin.")

        corner_distance = hypot(self.edge_margin_mm / 2.0, self.edge_margin_mm / 2.0)
        required_distance = (
            (self.mounting_hole_diameter_mm / 2.0)
            + (self.pad_diameter_mm / 2.0)
            + 0.2
        )
        if corner_distance < required_distance:
            raise ValueError(
                "Edge margin is too small to keep mounting holes clear of the pad grid."
            )

        self._validate_rounded_corners()

    def _validate_rounded_corners(self) -> None:
        if not self.has_rounded_corners:
            return

        clearance = 0.2
        self._validate_feature_against_rounded_corner(
            center_x=self.edge_margin_mm,
            center_y=self.edge_margin_mm,
            feature_radius=(self.pad_diameter_mm / 2.0) + clearance,
            feature_name="corner pad",
        )

        if self.mounting_hole_diameter_mm > 0:
            self._validate_feature_against_rounded_corner(
                center_x=self.mounting_hole_inset_mm,
                center_y=self.mounting_hole_inset_mm,
                feature_radius=(self.mounting_hole_diameter_mm / 2.0) + clearance,
                feature_name="mounting hole",
            )

    def _validate_feature_against_rounded_corner(
        self,
        *,
        center_x: float,
        center_y: float,
        feature_radius: float,
        feature_name: str,
    ) -> None:
        for point_x, point_y in _sample_circle(center_x, center_y, feature_radius):
            if not self._point_is_inside_outline(point_x, point_y):
                raise ValueError(
                    f"Rounded corners clip the {feature_name}; reduce the corner radius "
                    "or increase the clearances."
                )

    def _point_is_inside_outline(self, point_x: float, point_y: float) -> bool:
        if point_x < 0 or point_y < 0:
            return False
        if point_x > self.board_width_mm or point_y > self.board_height_mm:
            return False

        radius = self.rounded_corner_radius_mm
        if radius <= 0:
            return True

        width = self.board_width_mm
        height = self.board_height_mm

        if point_x < radius and point_y < radius:
            return hypot(point_x - radius, point_y - radius) <= radius
        if point_x > width - radius and point_y < radius:
            return hypot(point_x - (width - radius), point_y - radius) <= radius
        if point_x < radius and point_y > height - radius:
            return hypot(point_x - radius, point_y - (height - radius)) <= radius
        if point_x > width - radius and point_y > height - radius:
            return hypot(point_x - (width - radius), point_y - (height - radius)) <= radius
        return True


def _sample_circle(
    center_x: float,
    center_y: float,
    radius: float,
    *,
    steps: int = 32,
) -> Iterator[tuple[float, float]]:
    for step in range(steps):
        angle = (2 * pi * step) / steps
        yield center_x + (cos(angle) * radius), center_y + (sin(angle) * radius)
