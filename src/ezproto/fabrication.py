"""Gerber and drill generation utilities backed by KiCad CLI."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Protocol
import zipfile

from ezproto.kicad import write_kicad_pcb
from ezproto.models import BoardParameters

KICAD_CLI_ENV_VAR = "EZPROTO_KICAD_CLI"
KICAD_WINDOWS_GLOB = "*/bin/kicad-cli.exe"
GERBER_LAYER_SPECS: tuple[tuple[str, str], ...] = (
    ("F.Cu", "F_Cu"),
    ("B.Cu", "B_Cu"),
    ("F.Mask", "F_Mask"),
    ("B.Mask", "B_Mask"),
    ("F.Paste", "F_Paste"),
    ("B.Paste", "B_Paste"),
    ("F.SilkS", "F_Silkscreen"),
    ("B.SilkS", "B_Silkscreen"),
    ("Edge.Cuts", "Edge_Cuts"),
)


class _FabricationBoardSpec(Protocol):
    @property
    def output_file_stem(self) -> str: ...

    @property
    def output_file_name(self) -> str: ...


def write_fabrication_package(
    destination_directory: Path | str,
    parameters: BoardParameters | _FabricationBoardSpec,
    *,
    include_drill: bool = True,
    pcb_path: Path | str | None = None,
    kicad_cli_path: Path | str | None = None,
) -> list[Path]:
    """Generate Gerbers and an optional drill file using KiCad CLI."""

    output_directory = Path(destination_directory).expanduser()
    output_directory.mkdir(parents=True, exist_ok=True)

    source_pcb, temporary_source_directory = _resolve_source_board_path(
        output_directory=output_directory,
        parameters=parameters,
        pcb_path=pcb_path,
    )
    cli_path = _resolve_kicad_cli(kicad_cli_path)

    stem = parameters.output_file_stem
    _remove_stale_outputs(output_directory, stem=stem)

    gerber_layers = ",".join(layer_name for layer_name, _ in GERBER_LAYER_SPECS)
    try:
        _run_kicad_cli(
            cli_path,
            [
                "pcb",
                "export",
                "gerbers",
                "--output",
                str(output_directory),
                "--layers",
                gerber_layers,
                "--no-protel-ext",
            ],
            source_pcb=source_pcb,
        )

        if include_drill:
            _run_kicad_cli(
                cli_path,
                [
                    "pcb",
                    "export",
                    "drill",
                    "--output",
                    str(output_directory),
                    "--format",
                    "excellon",
                    "--drill-origin",
                    "absolute",
                    "--excellon-units",
                    "mm",
                ],
                source_pcb=source_pcb,
            )

        return _collect_outputs(
            output_directory,
            stem=stem,
            include_drill=include_drill,
        )
    finally:
        if (
            temporary_source_directory is not None
            and temporary_source_directory.exists()
        ):
            shutil.rmtree(temporary_source_directory, ignore_errors=True)


def write_fabrication_archive(
    destination_archive: Path | str,
    fabrication_files: list[Path],
    *,
    root_directory_name: str,
) -> Path:
    """Write a ZIP archive for a fabrication package."""

    archive_path = Path(destination_archive).expanduser()
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for file_path in fabrication_files:
            archive.write(
                file_path,
                arcname=str(Path(root_directory_name) / file_path.name),
            )

    return archive_path.resolve()

def _resolve_source_board_path(
    *,
    output_directory: Path,
    parameters: BoardParameters | _FabricationBoardSpec,
    pcb_path: Path | str | None,
) -> tuple[Path, Path | None]:
    if pcb_path is None:
        if not isinstance(parameters, BoardParameters):
            raise OSError(
                "A PCB source path is required when exporting fabrication files for this board type."
            )
        temporary_directory = Path(
            tempfile.mkdtemp(
                prefix=f"{parameters.output_file_stem}_",
                dir=output_directory,
            )
        )
        generated_path = temporary_directory / parameters.output_file_name
        return write_kicad_pcb(generated_path, parameters), temporary_directory

    resolved = Path(pcb_path).expanduser().resolve()
    if not resolved.exists():
        raise OSError(f"PCB source file does not exist: {resolved}")
    return resolved, None


def _resolve_kicad_cli(explicit_path: Path | str | None) -> Path:
    candidates: list[Path] = []

    if explicit_path is not None:
        candidates.append(Path(explicit_path).expanduser())

    if env_path := os.environ.get(KICAD_CLI_ENV_VAR, "").strip():
        candidates.append(Path(env_path).expanduser())

    for executable in ("kicad-cli", "kicad-cli.exe"):
        discovered = shutil.which(executable)
        if discovered:
            candidates.append(Path(discovered))

    program_files = os.environ.get("ProgramFiles", "").strip()
    if program_files:
        kicad_root = Path(program_files) / "KiCad"
        if kicad_root.exists():
            versioned_candidates = sorted(
                kicad_root.glob(KICAD_WINDOWS_GLOB),
                key=_kicad_install_sort_key,
                reverse=True,
            )
            candidates.extend(versioned_candidates)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved

    raise OSError(
        "Unable to find KiCad CLI executable. Install KiCad, add `kicad-cli` to PATH, "
        f"or set `{KICAD_CLI_ENV_VAR}`."
    )


def _kicad_install_sort_key(path: Path) -> tuple[int, ...]:
    # Expected shape: .../KiCad/<version>/bin/kicad-cli.exe
    try:
        version_text = path.parent.parent.name
    except IndexError:
        return (0,)
    parts: list[int] = []
    for part in version_text.split("."):
        if not part.isdigit():
            break
        parts.append(int(part))
    return tuple(parts) or (0,)


def _remove_stale_outputs(
    output_directory: Path,
    *,
    stem: str,
) -> None:
    for _, layer_suffix in GERBER_LAYER_SPECS:
        for stale_path in (
            output_directory / f"{stem}_{layer_suffix}.gbr",
            output_directory / f"{stem}-{layer_suffix}.gbr",
        ):
            if stale_path.exists():
                stale_path.unlink()

    drill_path = output_directory / f"{stem}.drl"
    if drill_path.exists():
        drill_path.unlink()

    for job_path in (
        output_directory / f"{stem}-job.gbrjob",
        output_directory / f"{stem}_job.gbrjob",
    ):
        if job_path.exists():
            job_path.unlink()


def _run_kicad_cli(cli_path: Path, arguments: list[str], *, source_pcb: Path) -> None:
    command = [str(cli_path), *arguments, str(source_pcb)]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return

    details = result.stderr.strip() or result.stdout.strip() or "unknown error"
    raise OSError(
        "KiCad CLI command failed: "
        f"{' '.join(arguments)} ({details})"
    )


def _collect_outputs(
    output_directory: Path,
    *,
    stem: str,
    include_drill: bool,
) -> list[Path]:
    written_files: list[Path] = []
    missing_files: list[str] = []

    for _, layer_suffix in GERBER_LAYER_SPECS:
        renamed_file = output_directory / f"{stem}_{layer_suffix}.gbr"
        source_file = output_directory / f"{stem}-{layer_suffix}.gbr"

        if source_file.exists():
            source_file.replace(renamed_file)

        if renamed_file.exists():
            written_files.append(renamed_file.resolve())
            continue

        missing_files.append(renamed_file.name)

    if include_drill:
        drill_file = output_directory / f"{stem}.drl"
        if drill_file.exists():
            written_files.append(drill_file.resolve())
        else:
            missing_files.append(drill_file.name)

    for job_path in (
        output_directory / f"{stem}-job.gbrjob",
        output_directory / f"{stem}_job.gbrjob",
    ):
        if job_path.exists():
            job_path.unlink()

    if missing_files:
        missing_text = ", ".join(sorted(missing_files))
        raise OSError(f"KiCad CLI did not produce expected fabrication files: {missing_text}")

    return written_files
