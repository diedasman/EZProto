"""Textual user interface for the protoboard generator."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from rich.markup import escape
from textual.app import App, ComposeResult # type: ignore
from textual.containers import Container, Horizontal, Vertical, VerticalScroll # type: ignore
from textual.screen import ModalScreen # type: ignore
from textual.widgets import ( # type: ignore
    Button,
    Checkbox,
    # Header,
    Input,
    Label,
    Select,
    Static,
)

from ezproto.fabrication import write_fabrication_archive, write_fabrication_package
from ezproto.kicad import write_kicad_pcb
from ezproto.models import BoardParameters
from ezproto.preview import render_board_preview
from ezproto.storage import (
    DEFAULT_THEME_NAME,
    current_timestamp,
    default_output_directory,
    load_app_state,
    machine_user_slug,
    update_app_state,
)

WELCOME_ART_RESOURCE = files("ezproto").joinpath("assets/logo.txt")

PITCH_PRESETS = {
    "pitch_1_00": "1.0",
    "pitch_2_00": "2.0",
    "pitch_2_54": "2.54",
    "pitch_5_08": "5.08",
}

ROUNDED_CORNER_OPTIONS = [
    ("1 mm", "1"),
    ("2 mm", "2"),
    ("3 mm", "3"),
    ("4 mm", "4"),
    ("5 mm", "5"),
]

PROTO_INPUT_IDS = {
    "board_name",
    "columns",
    "rows",
    "pitch",
    "pth_drill",
    "pad_diameter",
    "mount_hole",
    "edge_margin",
}

PCBWAY_ORDER_URL = "https://www.pcbway.com/QuickOrderOnline.aspx;"

SECTION_BUTTON_TO_VIEW = {
    "nav_home": "welcome",
    "nav_protoboard": "protoboard",
    "nav_settings": "settings",
}

SECTION_VIEW_TO_BUTTON = {
    view_id: button_id for button_id, view_id in SECTION_BUTTON_TO_VIEW.items()
}

class ResetFormConfirmationScreen(ModalScreen[bool]):
    """Modal confirmation screen shown before clearing the protoboard form."""

    def compose(self) -> ComposeResult:
        with Container(id="reset_form_overlay"):
            with Vertical(id="reset_form_dialog"):
                yield Static("Reset board form?", id="reset_form_dialog_title")
                yield Static(
                    (
                        "Your current board values will stay untouched unless you "
                        "confirm. Saved settings and generated files will not be deleted."
                    ),
                    id="reset_form_dialog_message",
                )
                with Horizontal(id="reset_form_dialog_actions", classes="button_row"):
                    yield Button("Cancel", id="cancel_reset_form")
                    yield Button("Reset Form", variant="error", id="confirm_reset_form")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm_reset_form":
            self.dismiss(True)
            return
        if event.button.id == "cancel_reset_form":
            self.dismiss(False)


class ProtoboardApp(App[None]):
    """A form-based app that exports protoboards and manages workspace settings."""

    CSS_PATH = "app.tcss"
    TITLE = "EZProto"
    SUB_TITLE = "Parametric protoboard generator"

    BINDINGS = [
        ("ctrl+g", "generate", "Generate"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._app_state = load_app_state()
        self._machine_user_slug = machine_user_slug()
        self._active_section = "welcome"
        self._syncing_controls = False

    # Board Properties and Controls Widget Rendering:
    def compose(self) -> ComposeResult:
        # yield Header()
        with Vertical(id="app_shell"):
            with Horizontal(id="section_nav", classes="nav_buttons"):
                yield Button("HOME", id="nav_home", classes="section_button")
                yield Button("PROTOBOARD", id="nav_protoboard", classes="section_button")
                yield Button("SETTINGS", id="nav_settings", classes="section_button")

            with Container(id="section_host"):
                with Container(id="welcome", classes="section_view"):
                    with Container(id="welcome_layout"):
                        with Horizontal(id="welcome_panel"):
                            welcome_art = WELCOME_ART_RESOURCE.read_text(encoding="utf-8")

                            with Vertical(id="welcome_logo_column"):
                                yield Static(welcome_art, id="welcome_art")

                            with Vertical(id="welcome_message_column"):
                                yield Static(
                                    (
                                        "EZProto is a keyboard-friendly workspace for protoboards "
                                        "and fabrication exports."
                                    ),
                                    id="welcome_intro",
                                )

                                with Horizontal(id="welcome_navigation_frame"):
                                    yield Static(
                                        (
                                            "HOME, PROTOBOARD, SETTINGS\n"
                                            "Use the section buttons above the workspace to switch views.\n"
                                        ),
                                        id="welcome_navigation",
                                    )

                                    yield Static(
                                        (
                                            "Press Tab and Shift+Tab to move focus between controls.\n"
                                            "Press Enter or Space to open the focused section button.\n"
                                        ),
                                        id="arrow_navigation",
                                    )

                                yield Static(
                                    (
                                        "Open SETTINGS to review the output folder and theme.\n"
                                        "Use PROTOBOARD to create a board.\n"
                                        "Use the Generate buttons when you are ready to write files."
                                    ),
                                    id="welcome_getting_started",
                                )

                                yield Static(
                                    (
                                        "Ctrl+G  Generate the protoboard form\n"
                                        "Ctrl+Q  Quit EZProto"
                                    ),
                                    id="welcome_shortcuts",
                                )

                with Container(id="protoboard", classes="section_view hidden"):
                    with Container(id="protoboard_layout"):
                        with Vertical(id="protoboard_inputs_column", classes="input_column"):
                            with VerticalScroll(id="parameters_panel", classes="panel"):
                                with Container(id="form"):
                                    with Horizontal(id="board_name_row"):
                                        yield Label("Board name", classes="field_label")
                                        yield Input(placeholder="Protoboard", id="board_name")

                                    with Horizontal(id="dimensions_row"):
                                        yield Label("Columns", classes="field_label")
                                        yield Input(id="columns", placeholder="Number of columns")
                                        yield Label("Rows", classes="field_label")
                                        yield Input(id="rows", placeholder="Number of rows")

                                    with Horizontal(id="pitch_row"):
                                        yield Label("Pitch (mm)", classes="field_label")
                                        with Horizontal(id="pitch_controls"):
                                            yield Input(id="pitch", placeholder="Custom")
                                            yield Button("1 mm", id="pitch_1_00", classes="pitch_preset")
                                            yield Button("2 mm", id="pitch_2_00", classes="pitch_preset")
                                            yield Button("2.54 mm", id="pitch_2_54", classes="pitch_preset")
                                            yield Button("5.08 mm", id="pitch_5_08", classes="pitch_preset")

                                    with Horizontal(id="pth_drill_row"):
                                        yield Label("PTH drill (mm)", classes="field_label")
                                        yield Input(id="pth_drill", placeholder="PTH drill diameter (mm)")

                                    with Horizontal(id="pad_diameter_row"):
                                        yield Label("Pad diameter (mm)", classes="field_label")
                                        yield Input(id="pad_diameter", placeholder="Pad diameter (mm)")

                                    with Horizontal(id="mount_hole_row"):
                                        yield Label("Mount hole (mm)", classes="field_label")
                                        yield Input(id="mount_hole", placeholder="Mount hole diameter (mm)")

                                    with Horizontal(id="edge_margin_row"):
                                        yield Label("Edge margin (mm)", classes="field_label")
                                        yield Input(
                                            id="edge_margin",
                                            placeholder="Distance from board edge to pad edge (mm)",
                                        )

                                    with Horizontal(id="rounded_corners_row"):
                                        yield Label("Rounded corners", classes="field_label")
                                        yield Select[str](
                                            ROUNDED_CORNER_OPTIONS,
                                            prompt="Square corners",
                                            id="rounded_corners",
                                        )

                                    with Horizontal(id="dfm_options_row"):
                                        yield Label("DFM export", classes="field_label")
                                        with Horizontal(id="dfm_options"):
                                            yield Checkbox("Generate Gerbers", id="generate_gerbers")
                                            yield Checkbox(
                                                "Include drill file",
                                                id="include_drill",
                                                classes="dfm_option",
                                            )
                                            yield Checkbox(
                                                ".ZIP archive",
                                                id="zip_output",
                                                classes="dfm_option",
                                            )

                            with Vertical(id="protoboard_actions_panel", classes="action_panel"):
                                with Horizontal(id="buttons", classes="button_row"):
                                    yield Button("Generate PCB", variant="primary", id="generate")
                                    yield Button("Make it with PCBWay!", variant="success", id="pcbway")
                                    yield Button("Reset form", variant="error", id="reset_form")

                        with Vertical(id="summary_panel", classes="panel"):
                            yield Static(id="summary")
                            yield Static(id="board_preview")
                            yield Static(id="proto_status", classes="status_box")

                with Container(id="settings", classes="section_view hidden"):
                    with Vertical(id="settings_layout"):
                        with Vertical(id="settings_panel", classes="panel settings_panel"):
                            with Container(id="settings_form", classes="settings_form"):
                                yield Label("Output directory", classes="field_label")
                                yield Input(
                                    id="default_output_directory",
                                    placeholder=str(self._default_output_directory_path()),
                                )
                                yield Label("Theme", classes="field_label")
                                yield Select[str](
                                    self._theme_options(),
                                    value=self._default_theme_name(),
                                    allow_blank=False,
                                    id="theme_select",
                                )
                            with Horizontal(classes="button_row"):
                                yield Button("Save Settings", id="save_settings")
                        yield Static(id="settings_status", classes="status_box")
        # yield Footer()

    def on_mount(self) -> None:
        self.query_one("#parameters_panel", VerticalScroll).border_title = "Board Parameters"
        self.query_one("#protoboard_actions_panel", Vertical).border_title = " Actions "
        self.query_one("#summary_panel", Vertical).border_title = "Board Summary"
        self.query_one("#settings_panel", Vertical).border_title = "Settings"
        self.query_one("#welcome_intro", Static).border_title = "Welcome"
        self.query_one("#welcome_navigation_frame", Horizontal).border_title = "Workspace Navigation"
        self.query_one("#welcome_getting_started", Static).border_title = "Getting Started"
        self.query_one("#welcome_shortcuts", Static).border_title = "Quick Keys"
        self.query_one("#board_preview", Static).border_title = "Board Preview"
        self.query_one("#summary", Static).border_title = "Board Details"
        self.query_one("#proto_status", Static).border_title = "Status"
        self.query_one("#include_drill", Checkbox).value = True

        self._set_dfm_option_controls_enabled(
            self.query_one("#generate_gerbers", Checkbox).value
        )
        self._load_workspace_settings()
        self._refresh_preview()
        self._set_active_section("welcome")
        self.query_one("#nav_home", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in SECTION_BUTTON_TO_VIEW:
            self._set_active_section(SECTION_BUTTON_TO_VIEW[event.button.id])
            return
        if event.button.id in PITCH_PRESETS:
            self._apply_pitch_preset(PITCH_PRESETS[event.button.id])
            return
        if event.button.id == "generate":
            self.action_generate()
            return
        if event.button.id == "pcbway":
            self._open_pcbway_quick_quote()
            return
        if event.button.id == "reset_form":
            self.push_screen(
                ResetFormConfirmationScreen(),
                self._handle_reset_form_confirmation,
            )
            return
        if event.button.id == "save_settings":
            self._save_workspace_settings()
            return

    def _set_active_section(self, section_id: str) -> None:
        self._active_section = section_id

        for view_id, button_id in SECTION_VIEW_TO_BUTTON.items():
            section = self.query_one(f"#{view_id}", Container)
            button = self.query_one(f"#{button_id}", Button)
            if view_id == section_id:
                section.remove_class("hidden")
                button.add_class("section_button_active")
                continue

            section.add_class("hidden")
            button.remove_class("section_button_active")

    def _handle_reset_form_confirmation(self, confirmed: bool) -> None:
        if not confirmed:
            self._set_proto_status(
                "Reset cancelled. Your board inputs are still in place.",
                error=False,
            )
            return
        
        self._reset_protoboard_form()

    def _reset_protoboard_form(self) -> None:
        for widget_id in PROTO_INPUT_IDS:
            self.query_one(f"#{widget_id}", Input).value = ""

        rounded_corners = self.query_one("#rounded_corners", Select)
        if rounded_corners.value != Select.BLANK:
            rounded_corners.value = Select.BLANK

        self.query_one("#generate_gerbers", Checkbox).value = False
        self.query_one("#include_drill", Checkbox).value = True
        self.query_one("#zip_output", Checkbox).value = False
        self._set_dfm_option_controls_enabled(False)
        self._refresh_preview()
        self.query_one("#board_name", Input).focus()
        self._set_proto_status("Protoboard form reset.", error=False)

    def _open_pcbway_quick_quote(self) -> None:
        self.open_url(PCBWAY_ORDER_URL)
        self._set_proto_status("Opened PCBWay Quick Quote in your browser.", error=False)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in PROTO_INPUT_IDS:
            self._refresh_preview()
            return
        if event.input.id == "default_output_directory":
            self._refresh_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "generate_gerbers":
            self._set_dfm_option_controls_enabled(event.checkbox.value)
            self._refresh_preview()
            return

    def on_select_changed(self, event: Select.Changed) -> None:
        if self._syncing_controls:
            return

        if event.select.id == "rounded_corners":
            self._refresh_preview()
            return

        if event.select.id == "theme_select":
            self.theme = self._coerce_theme_name(str(event.value))

    def action_generate(self) -> None:
        try:
            parameters = self._read_parameters()
        except ValueError as error:
            self._set_proto_status(str(error), error=True)
            return

        output_root = self._resolved_output_directory()
        try:
            written_file = write_kicad_pcb(
                parameters.output_path_for(output_root),
                parameters,
            )
        except OSError as error:
            self._set_proto_status(f"Unable to write PCB file: {error}", error=True)
            return

        generate_gerbers = self.query_one("#generate_gerbers", Checkbox).value
        include_drill = generate_gerbers and self.query_one("#include_drill", Checkbox).value
        zip_output = generate_gerbers and self.query_one("#zip_output", Checkbox).value
        dfm_directory = written_file.parent / f"{parameters.output_file_stem}_DFM"
        archive_path = written_file.parent / f"{parameters.output_file_stem}_DFM.zip"
        fabrication_files: list[Path] = []
        fabrication_error: OSError | None = None
        archive_error: OSError | None = None
        written_archive: Path | None = None

        if generate_gerbers:
            try:
                fabrication_files = write_fabrication_package(
                    dfm_directory,
                    parameters,
                    include_drill=include_drill,
                    pcb_path=written_file,
                )
            except OSError as error:
                fabrication_error = error
            else:
                if zip_output:
                    try:
                        written_archive = write_fabrication_archive(
                            archive_path,
                            fabrication_files,
                            root_directory_name=dfm_directory.name,
                        )
                    except OSError as error:
                        archive_error = error

        board_details = self._build_board_details(
            parameters,
            pcb_path=written_file,
            gerbers_requested=generate_gerbers,
            gerbers_generated=generate_gerbers and fabrication_error is None,
            dfm_directory=dfm_directory if generate_gerbers else None,
            fabrication_files=[str(path) for path in fabrication_files],
            drill_included=include_drill,
            zip_requested=zip_output,
            zip_generated=zip_output and fabrication_error is None and archive_error is None,
            zip_archive=written_archive,
        )

        metadata_error: OSError | None = None
        try:
            self._record_generated_board(parameters.board_name, board_details)
        except OSError as error:
            metadata_error = error

        self._refresh_preview()

        if fabrication_error is not None:
            self._set_proto_status(
                f"PCB written to {written_file}, but DFM export failed: {fabrication_error}",
                error=True,
            )
            return

        if archive_error is not None:
            self._set_proto_status(
                f"PCB written to {written_file}; DFM files written to {dfm_directory}, "
                f"but ZIP archive failed: {archive_error}",
                error=True,
            )
            return

        if metadata_error is not None:
            self._set_proto_status(
                f"PCB written to {written_file}, but metadata update failed: {metadata_error}",
                error=True,
            )
            return

        if generate_gerbers:
            output_messages = [f"DFM files written to {dfm_directory}"]
            if written_archive is not None:
                output_messages.append(f"ZIP archive written to {written_archive}")
            self._set_proto_status(
                f"PCB written to {written_file}; " + "; ".join(output_messages),
                error=False,
            )
            return

        self._set_proto_status(f"PCB written to {written_file}", error=False)

    def _read_parameters(self) -> BoardParameters:
        return BoardParameters(
            board_name=self._value("board_name") or "Protoboard",
            columns=self._parse_int("Columns", self._value("columns")),
            rows=self._parse_int("Rows", self._value("rows")),
            pitch_mm=self._parse_float("Pitch", self._value("pitch")),
            pth_drill_mm=self._parse_float("PTH drill", self._value("pth_drill")),
            pad_diameter_mm=self._parse_float("Pad diameter", self._value("pad_diameter")),
            mounting_hole_diameter_mm=self._parse_float(
                "Mounting hole diameter",
                self._value("mount_hole"),
            ),
            edge_margin_mm=self._parse_float("Edge margin", self._value("edge_margin")),
            rounded_corner_radius_mm=self._read_rounded_corner_radius(),
        )

    def _refresh_preview(self) -> None:
        summary = self.query_one("#summary", Static)
        preview = self.query_one("#board_preview", Static)
        status = self.query_one("#proto_status", Static)

        try:
            parameters = self._read_parameters()
        except ValueError as error:
            message = f"Waiting for valid parameters.\n\n{error}"
            idle_message =f"..."
            summary.update(message)
            preview.update(idle_message)
            status.update(idle_message)
            return

        mounting_holes = (
            f"{parameters.mounting_hole_count} x {parameters.mounting_hole_diameter_mm:.2f} mm"
            if parameters.mounting_hole_count
            else "Disabled"
        )
        corner_style = (
            f"{parameters.rounded_corner_radius_mm:.2f} mm radius"
            if parameters.has_rounded_corners
            else "Square corners"
        )
        if self.query_one("#generate_gerbers", Checkbox).value:
            fabrication_parts = ["Gerbers"]
            if self.query_one("#include_drill", Checkbox).value:
                fabrication_parts.append("drill")
            if self.query_one("#zip_output", Checkbox).value:
                fabrication_parts.append("zip")
            fabrication_label = " + ".join(fabrication_parts)
        else:
            fabrication_label = "PCB only"

        output_root = self._resolved_output_directory()
        output_path = str(parameters.output_path_for(output_root))
        dfm_path = str(
            parameters.output_path_for(output_root).parent
            / f"{parameters.output_file_stem}_DFM"
        )
        archive_output = str(
            parameters.output_path_for(output_root).parent
            / f"{parameters.output_file_stem}_DFM.zip"
        )

        summary.update(
            "\n".join(
                [
                    self._detail_line(
                        "Pads",
                        f"{parameters.columns} columns x {parameters.rows} rows",
                    ),
                    self._detail_line("Hole count", parameters.hole_count, style="bold bright_yellow"),
                    self._detail_line(
                        "Board size",
                        f"{parameters.board_width_mm:.2f} mm x {parameters.board_height_mm:.2f} mm",
                    ),
                    self._detail_line("Pitch", f"{parameters.pitch_mm:.2f} mm"),
                    self._detail_line(
                        "Pad / drill",
                        f"{parameters.pad_diameter_mm:.2f} mm / {parameters.pth_drill_mm:.2f} mm",
                    ),
                    self._detail_line("Mounting holes", mounting_holes, style="bold bright_yellow"),
                    self._detail_line("Corners", corner_style, style="bold bright_white"),
                    self._detail_line("Fabrication", fabrication_label, style="bold bright_magenta"),
                    self._detail_line("Output root", output_root, style="bold bright_green"),
                    self._detail_line("Board folder", parameters.output_directory_name, style="bold bright_green"),
                    self._detail_line("Output file", parameters.output_file_name, style="bold bright_green"),
                    self._detail_line("Resolved path", output_path, style="bold bright_green"),
                    self._detail_line("DFM directory", dfm_path, style="bold bright_green"),
                    self._detail_line("ZIP archive", archive_output, style="bold bright_green"),
                ]
            )
        )
        preview.update(render_board_preview(parameters))

    @staticmethod
    def _detail_line(label: str, value: object, *, style: str = "bold bright_cyan") -> str:
        escaped_label = escape(label)
        escaped_value = escape(str(value))
        return f"[dim]{escaped_label}:[/] [{style}]{escaped_value}[/]"

    def _load_workspace_settings(self) -> None:
        self._app_state = load_app_state()
        output_directory = self.query_one("#default_output_directory", Input)
        theme_select = self.query_one("#theme_select", Select)
        theme_name = self._coerce_theme_name(self._app_state.theme)

        self._syncing_controls = True
        try:
            output_directory.placeholder = str(self._default_output_directory_path())
            if output_directory.value != self._app_state.default_output_directory:
                output_directory.value = self._app_state.default_output_directory
            if theme_select.value != theme_name:
                theme_select.value = theme_name
        finally:
            self._syncing_controls = False

        self.theme = theme_name

    def _save_workspace_settings(self) -> None:
        theme_name = self._coerce_theme_name(str(self.query_one("#theme_select", Select).value))

        try:
            self._app_state = update_app_state(
                default_output_directory=self._configured_output_directory(),
                theme=theme_name,
                boards=dict(self._app_state.boards),
                message="Saved workspace settings.",
                user_slug=self._machine_user_slug,
            )
        except OSError as error:
            self._set_settings_status(f"Unable to save settings: {error}", error=True)
            return

        self._load_workspace_settings()
        self._refresh_preview()
        self._set_settings_status(
            f"Settings saved. Output directory: {self._resolved_output_directory()}",
            error=False,
        )

    def _apply_pitch_preset(self, value: str) -> None:
        pitch_input = self.query_one("#pitch", Input)
        pitch_input.value = value
        self._refresh_preview()

    def _read_rounded_corner_radius(self) -> float:
        value = self.query_one("#rounded_corners", Select).value
        if value == Select.BLANK:
            return 0.0
        return float(value)

    def _build_board_details(
        self,
        parameters: BoardParameters,
        *,
        pcb_path: Path,
        gerbers_requested: bool,
        gerbers_generated: bool,
        dfm_directory: Path | None,
        fabrication_files: list[str],
        drill_included: bool,
        zip_requested: bool,
        zip_generated: bool,
        zip_archive: Path | None,
    ) -> dict[str, object]:
        summary = (
            f"{parameters.columns} x {parameters.rows} grid, "
            f"{parameters.pitch_mm:.2f} mm pitch, "
            f"{parameters.board_width_mm:.2f} mm x {parameters.board_height_mm:.2f} mm board"
        )
        return {
            "board_name": parameters.board_name,
            "summary": summary,
            "columns": parameters.columns,
            "rows": parameters.rows,
            "pitch_mm": parameters.pitch_mm,
            "pth_drill_mm": parameters.pth_drill_mm,
            "pad_diameter_mm": parameters.pad_diameter_mm,
            "mounting_hole_diameter_mm": parameters.mounting_hole_diameter_mm,
            "mounting_hole_count": parameters.mounting_hole_count,
            "edge_margin_mm": parameters.edge_margin_mm,
            "rounded_corner_radius_mm": parameters.rounded_corner_radius_mm,
            "board_width_mm": parameters.board_width_mm,
            "board_height_mm": parameters.board_height_mm,
            "hole_count": parameters.hole_count,
            "output_file": str(pcb_path),
            "gerbers_requested": gerbers_requested,
            "gerbers_generated": gerbers_generated,
            "dfm_directory": str(dfm_directory) if dfm_directory is not None else "",
            "fabrication_files": fabrication_files,
            "drill_included": drill_included,
            "zip_requested": zip_requested,
            "zip_generated": zip_generated,
            "zip_archive": str(zip_archive) if zip_archive is not None else "",
            "generated_at": current_timestamp(),
        }

    def _record_generated_board(
        self,
        board_name: str,
        board_details: dict[str, object],
    ) -> None:
        boards = dict(self._app_state.boards)
        boards[board_name] = board_details
        self._app_state = update_app_state(
            default_output_directory=self._configured_output_directory(),
            theme=self._coerce_theme_name(self.theme or self._default_theme_name()),
            boards=boards,
            message=f"Generated board '{board_name}'.",
            user_slug=self._machine_user_slug,
            board_name=board_name,
            details=board_details,
        )
        self._load_workspace_settings()

    def _set_proto_status(self, message: str, *, error: bool) -> None:
        self._update_status_widget(
            self.query_one("#proto_status", Static),
            message,
            error=error,
        )

    def _set_settings_status(self, message: str, *, error: bool) -> None:
        self._update_status_widget(
            self.query_one("#settings_status", Static),
            message,
            error=error,
        )

    @staticmethod
    def _update_status_widget(status: Static, message: str, *, error: bool) -> None:
        status.remove_class("success")
        status.remove_class("error")
        status.update(message)
        status.add_class("error" if error else "success")

    def _value(self, widget_id: str) -> str:
        return self.query_one(f"#{widget_id}", Input).value

    @staticmethod
    def _parse_int(label: str, raw_value: str) -> int:
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{label} is required.")
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a whole number.") from error

    @staticmethod
    def _parse_float(label: str, raw_value: str) -> float:
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{label} is required.")
        try:
            return float(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a number.") from error

    @staticmethod
    def _normalized_output_directory(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        return str(Path(cleaned).expanduser())

    def _default_output_directory_path(self) -> Path:
        return default_output_directory()

    def _configured_output_directory(self) -> str:
        configured = self._normalized_output_directory(
            self.query_one("#default_output_directory", Input).value
        )
        default_path = str(self._default_output_directory_path())
        return "" if configured == default_path else configured

    def _resolved_output_directory(self) -> str:
        return self._configured_output_directory() or str(self._default_output_directory_path())

    def _set_dfm_option_controls_enabled(self, enabled: bool) -> None:
        self.query_one("#include_drill", Checkbox).disabled = not enabled
        self.query_one("#zip_output", Checkbox).disabled = not enabled

    def _theme_options(self) -> list[tuple[str, str]]:
        return [(name, name) for name in sorted(self.available_themes.keys())]

    def _default_theme_name(self) -> str:
        available = {name for name, _ in self._theme_options()}
        if DEFAULT_THEME_NAME in available:
            return DEFAULT_THEME_NAME
        return next(iter(sorted(available)), DEFAULT_THEME_NAME)

    def _coerce_theme_name(self, theme_name: str) -> str:
        available = {name for name, _ in self._theme_options()}
        return theme_name if theme_name in available else self._default_theme_name()
