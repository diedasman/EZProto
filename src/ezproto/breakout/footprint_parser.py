"""KiCad footprint parsing helpers for breakout generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import TypeAlias

from .models import Bounds, Pad, ParsedFootprint


@dataclass(frozen=True, slots=True)
class Atom:
    """A KiCad S-expression atom."""

    value: str
    quoted: bool = False


SExpr: TypeAlias = Atom | list["SExpr"]


def load_footprint(path: Path | str) -> ParsedFootprint:
    """Load a KiCad footprint from a file path or single-footprint directory."""

    footprint_path = resolve_footprint_path(path)
    tree = parse_sexpr(footprint_path.read_text(encoding="utf-8"))
    if _head(tree) != "footprint":
        raise ValueError(f"{footprint_path} is not a KiCad footprint file.")

    footprint_name = _atom_value(tree[1]) if len(tree) > 1 and isinstance(tree[1], Atom) else footprint_path.stem
    physical_pads: list[tuple[str, float, float, float, float, int]] = []

    for child in tree[2:]:
        if _head(child) != "pad":
            continue
        name = _atom_value(child[1]) if len(child) > 1 and isinstance(child[1], Atom) else ""
        at_node = _find_child(child, "at")
        size_node = _find_child(child, "size")
        if at_node is None or len(at_node) < 3:
            continue
        x_pos = _float_value(at_node[1], "pad x coordinate")
        y_pos = _float_value(at_node[2], "pad y coordinate")
        width = _float_value(size_node[1], "pad width") if size_node and len(size_node) >= 3 else 0.0
        height = _float_value(size_node[2], "pad height") if size_node and len(size_node) >= 3 else width
        physical_pads.append((name, x_pos, y_pos, width, height, len(physical_pads)))

    if not physical_pads:
        raise ValueError(f"{footprint_path} does not contain any pads.")

    logical_pads: dict[str, tuple[float, float, float, float, int]] = {}
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    for name, x_pos, y_pos, width, height, index in physical_pads:
        if name not in logical_pads:
            logical_pads[name] = (x_pos, y_pos, width, height, index)
        half_width = width / 2.0
        half_height = height / 2.0
        min_x = min(min_x, x_pos - half_width)
        min_y = min(min_y, y_pos - half_height)
        max_x = max(max_x, x_pos + half_width)
        max_y = max(max_y, y_pos + half_height)

    pads = tuple(
        Pad(
            name=name,
            x=x_pos,
            y=y_pos,
            net=None,
            width_mm=width,
            height_mm=height,
        )
        for name, (x_pos, y_pos, width, height, order_index) in sorted(
            logical_pads.items(),
            key=lambda item: _pad_sort_key(item[0], item[1][4]),
        )
    )

    return ParsedFootprint(
        path=footprint_path,
        name=footprint_name,
        tree=tree,
        pads=pads,
        bounds=Bounds(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y),
        physical_pad_count=len(physical_pads),
    )


def resolve_footprint_path(path: Path | str) -> Path:
    """Resolve a path to a concrete `.kicad_mod` file."""

    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise ValueError(f"Footprint path does not exist: {candidate}")
    if candidate.is_file():
        if candidate.suffix.lower() != ".kicad_mod":
            raise ValueError("Footprint path must point to a .kicad_mod file.")
        return candidate.resolve()

    footprint_files = sorted(candidate.glob("*.kicad_mod"))
    if not footprint_files:
        raise ValueError(f"No .kicad_mod files found in {candidate}.")
    if len(footprint_files) > 1:
        raise ValueError(
            f"Found multiple .kicad_mod files in {candidate}; choose a single footprint file."
        )
    return footprint_files[0].resolve()


def parse_sexpr(text: str) -> list[SExpr]:
    """Parse a KiCad S-expression document."""

    tokens = _tokenize(text)
    node, next_index = _parse_node(tokens, 0)
    if next_index != len(tokens):
        raise ValueError("Unexpected tokens after the end of the footprint.")
    return node


def serialize_sexpr(node: SExpr, *, indent: int = 0) -> str:
    """Serialize a KiCad S-expression node back to text."""

    return _serialize_node(node, indent=indent)


def atom(value: str, *, quoted: bool = False) -> Atom:
    """Create a new S-expression atom."""

    return Atom(value=value, quoted=quoted)


def _tokenize(text: str) -> list[str | Atom]:
    tokens: list[str | Atom] = []
    index = 0

    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character == ";":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if character in "()":
            tokens.append(character)
            index += 1
            continue
        if character == '"':
            value: list[str] = []
            index += 1
            while index < len(text):
                character = text[index]
                if character == "\\" and index + 1 < len(text):
                    value.append(text[index + 1])
                    index += 2
                    continue
                if character == '"':
                    index += 1
                    break
                value.append(character)
                index += 1
            else:
                raise ValueError("Unterminated string in footprint file.")
            tokens.append(Atom("".join(value), quoted=True))
            continue

        start = index
        while index < len(text) and not text[index].isspace() and text[index] not in "()":
            index += 1
        tokens.append(Atom(text[start:index], quoted=False))

    return tokens


def _parse_node(tokens: list[str | Atom], index: int) -> tuple[list[SExpr], int]:
    if index >= len(tokens) or tokens[index] != "(":
        raise ValueError("Expected '(' while parsing footprint.")

    items: list[SExpr] = []
    index += 1
    while index < len(tokens):
        token = tokens[index]
        if token == ")":
            return items, index + 1
        if token == "(":
            child, index = _parse_node(tokens, index)
            items.append(child)
            continue
        items.append(token)
        index += 1

    raise ValueError("Unterminated S-expression in footprint file.")


def _serialize_node(node: SExpr, *, indent: int) -> str:
    prefix = " " * indent
    if isinstance(node, Atom):
        return prefix + _format_atom(node)

    if _can_inline(node):
        return prefix + "(" + " ".join(_inline_text(child) for child in node) + ")"

    lines = [prefix + "(" + _inline_text(node[0])]
    for child in node[1:]:
        lines.append(_serialize_node(child, indent=indent + 2))
    lines.append(prefix + ")")
    return "\n".join(lines)


def _can_inline(node: list[SExpr]) -> bool:
    return all(isinstance(child, Atom) for child in node)


def _inline_text(node: SExpr) -> str:
    if isinstance(node, Atom):
        return _format_atom(node)
    if _can_inline(node):
        return "(" + " ".join(_inline_text(child) for child in node) + ")"
    return _serialize_node(node, indent=0)


def _format_atom(value: Atom) -> str:
    if value.quoted or not re.fullmatch(r"[^()\s\"]+", value.value):
        escaped = value.value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value.value


def _head(node: SExpr) -> str:
    if not isinstance(node, list) or not node:
        return ""
    head = node[0]
    return head.value if isinstance(head, Atom) else ""


def _find_child(node: list[SExpr], head: str) -> list[SExpr] | None:
    for child in node:
        if isinstance(child, list) and _head(child) == head:
            return child
    return None


def _atom_value(node: SExpr) -> str:
    if isinstance(node, Atom):
        return node.value
    raise TypeError("Expected an S-expression atom.")


def _float_value(node: SExpr, label: str) -> float:
    try:
        return float(_atom_value(node))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label} in footprint file.") from error


def _pad_sort_key(name: str, index: int) -> tuple[int, int | str, int]:
    numeric_name = name.strip()
    if numeric_name.isdigit():
        return (0, int(numeric_name), index)
    return (1, numeric_name.lower(), index)
