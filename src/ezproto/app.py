"""Textual user interface for the protoboard generator."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult # type: ignore
from textual.containers import Container, Horizontal, Vertical # type: ignore
from textual.widgets import ( # type: ignore
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from ezproto.fabrication import write_fabrication_archive, write_fabrication_package
from ezproto.kicad import write_kicad_pcb
from ezproto.models import BoardParameters
from ezproto.preview import render_board_preview
from ezproto.storage import (
    DEFAULT_THEME_NAME,
    UserProfile,
    current_timestamp,
    data_directory,
    list_user_profiles,
    load_app_state,
    load_user_profile,
    save_user_profile,
    update_app_state,
)

PITCH_PRESETS = {
    "pitch_1_00": "1.0",
    "pitch_2_00": "2.0",
    "pitch_2_54": "2.54",
    "pitch_5_08": "5.08",
}

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


class ProtoboardApp(App[None]):
    """A form-based app that exports protoboards and manages user settings."""

    CSS_PATH = "app.tcss"
    TITLE = "EZProto"
    SUB_TITLE = "Parametric PCB and enclosure generator"

    BINDINGS = [
        ("ctrl+g", "generate", "Generate"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.active_user: UserProfile | None = None
        self._syncing_controls = False

    # Board Properties and Controls Widget Rendering:
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="protoboard", id="main_tabs"):
            with TabPane("PROTOBOARD", id="protoboard"):
                with Container(id="protoboard_layout"):
                    with Vertical(id="parameters_panel", classes="panel"):
                        with Container(id="form"):
                            
                            yield Label("Board name", classes="field_label")
                            yield Input(placeholder="Protoboard", id="board_name")

                            yield Label("Columns", classes="field_label")
                            yield Input(id="columns", placeholder="Number of columns")

                            yield Label("Rows", classes="field_label")
                            yield Input(id="rows", placeholder="Number of rows")

                            yield Label("Pitch (mm)", classes="field_label")
                            
                            with Horizontal(id="pitch_controls"):
                                yield Input(id="pitch", placeholder="Custom")

                                yield Button("1 mm", id="pitch_1_00", classes="pitch_preset")
                                yield Button("2 mm", id="pitch_2_00", classes="pitch_preset")
                                yield Button("2.54 mm", id="pitch_2_54", classes="pitch_preset")
                                yield Button("5.08 mm", id="pitch_5_08", classes="pitch_preset")

                            yield Label("PTH drill (mm)", classes="field_label")
                            yield Input(id="pth_drill", placeholder="PTH drill diameter (mm)")

                            yield Label("Pad diameter (mm)", classes="field_label")
                            yield Input(id="pad_diameter", placeholder="Pad diameter (mm)")

                            yield Label("Mount hole (mm)", classes="field_label")
                            yield Input(id="mount_hole", placeholder="Mount hole diameter (mm)")

                            yield Label("Edge margin (mm)", classes="field_label")
                            yield Input(id="edge_margin", placeholder="Distance from board edge to pad edge (mm)")

                            yield Label("Rounded corners", classes="field_label")
                            yield Select[str](
                                [
                                    ("1 mm", "1"),
                                    ("2 mm", "2"),
                                    ("3 mm", "3"),
                                    ("4 mm", "4"),
                                    ("5 mm", "5"),
                                ],
                                prompt="Square corners",
                                id="rounded_corners",
                            )

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

                        with Horizontal(id="buttons", classes="button_row"):
                            yield Button("Generate PCB", variant="primary", id="generate")

                    with Vertical(id="summary_panel", classes="panel"):
                        yield Static(id="summary")
                        # yield Static(
                        #     "Tip: set mounting hole diameter to 0 to disable corner holes.",
                        #     id="hint",
                        # )
                        yield Static(id="board_preview")
                        yield Static(id="proto_status", classes="status_box")

            with TabPane("ENCLOSURE", id="enclosure"):
                pass

            with TabPane("SETTINGS", id="settings"):
                with Vertical(id="settings_layout"):
                    with Horizontal(id="settings_top"):
                        with Vertical(id="users_panel", classes="panel settings_panel"):
                            yield Label("Saved users", classes="settings_label")
                            yield Select[str](
                                [],
                                prompt="Select a user",
                                id="user_select",
                            )
                            with Horizontal(classes="button_row"):
                                yield Button("New User", id="show_create_user")
                                yield Button("Refresh", id="refresh_users")
                            yield Static(id="user_summary")

                        with Vertical(id="active_user_panel", classes="panel settings_panel"):
                            
                            yield Static("No active user selected", id="active_user_name")
                            with Container(id="active_user_form", classes="settings_form"):
                                
                                yield Label("Default output directory", classes="field_label")
                                yield Input(id="default_output_directory")
                                yield Label("Theme", classes="field_label")
                                yield Select[str](
                                    self._theme_options(),
                                    value=self._default_theme_name(),
                                    allow_blank=False,
                                    id="theme_select",
                                )
                            
                            with Horizontal(classes="button_row"):
                                yield Button("Save User Settings", id="save_user_settings")

                    with Vertical(id="create_user_panel", classes="panel settings_panel hidden"):
                        with Container(id="create_user_form", classes="settings_form"):
                            yield Label("User name", classes="field_label")
                            yield Input(id="new_user_name")
                            yield Label("Default output directory", classes="field_label")
                            yield Input(id="new_output_directory")
                        with Horizontal(classes="button_row"):
                            yield Button("Create User", variant="primary", id="create_user")
                            yield Button("Cancel", id="cancel_create_user")

                    yield Static(id="settings_status", classes="status_box")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#parameters_panel", Vertical).border_title = "Board Parameters"
        self.query_one("#summary_panel", Vertical).border_title = "Board Summary"
        self.query_one("#users_panel", Vertical).border_title = "Users"
        self.query_one("#active_user_panel", Vertical).border_title = "Active User"
        self.query_one("#create_user_panel", Vertical).border_title = "Create User"
        self.query_one("#board_preview", Static).border_title = "Board Preview"
        self.query_one("#summary", Static).border_title = "Board Details"
        self.query_one("#proto_status", Static).border_title = "Status"
        self.query_one("#include_drill", Checkbox).value = True
        self._set_dfm_option_controls_enabled(
            self.query_one("#generate_gerbers", Checkbox).value
        )
        self._set_active_user_controls_enabled(False)
        self._refresh_user_list()
        self._restore_last_user()
        self._refresh_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in PITCH_PRESETS:
            self._apply_pitch_preset(PITCH_PRESETS[event.button.id])
            return
        if event.button.id == "generate":
            self.action_generate()
            return
        if event.button.id == "show_create_user":
            self._toggle_create_user_form(True)
            return
        if event.button.id == "cancel_create_user":
            self._toggle_create_user_form(False)
            return
        if event.button.id == "create_user":
            self._create_user()
            return
        if event.button.id == "save_user_settings":
            self._save_active_user_settings()
            return
        if event.button.id == "refresh_users":
            self._refresh_user_list(selected_slug=self.active_user.slug if self.active_user else "")
            self._set_settings_status("User list refreshed.", error=False)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in PROTO_INPUT_IDS:
            self._refresh_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "generate_gerbers":
            self._set_dfm_option_controls_enabled(event.checkbox.value)
            self._refresh_preview()

    def on_select_changed(self, event: Select.Changed) -> None:
        if self._syncing_controls:
            return

        if event.select.id == "rounded_corners":
            self._refresh_preview()
            return

        if event.select.id == "user_select":
            if event.value == Select.BLANK:
                self._activate_user(None)
                return

            if self.active_user is not None and str(event.value) == self.active_user.slug:
                return

            profile = load_user_profile(str(event.value))
            if profile is None:
                self._set_settings_status("Unable to load the selected user profile.", error=True)
                self._activate_user(None)
                return

            self._activate_user(
                profile,
                persist_last_user=True,
                log_message=f"Loaded user '{profile.name}'.",
            )
            self._set_settings_status(f"Active user set to {profile.name}.", error=False)
            return

        if event.select.id == "theme_select" and self.active_user is not None:
            theme_name = self._coerce_theme_name(str(event.value))
            self.theme = theme_name

    def action_generate(self) -> None:
        try:
            parameters = self._read_parameters()
        except ValueError as error:
            self._set_proto_status(str(error), error=True)
            return

        if self.active_user is None:
            self._set_proto_status(
                "Select or create a user in SETTINGS before generating files.",
                error=True,
            )
            return

        try:
            written_file = write_kicad_pcb(
                parameters.output_path_for(self.active_user.default_output_directory),
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

        if self.active_user is None:
            active_user_name = "None"
            output_root = "No active user"
            output_path = "Select or create a user in SETTINGS."
            dfm_path = "Enable DFM export to create Gerbers and drill files."
            archive_output = "Enable DFM export to create a ZIP archive."
        else:
            active_user_name = self.active_user.name
            output_root = self.active_user.default_output_directory
            output_path = str(parameters.output_path_for(self.active_user.default_output_directory))
            dfm_path = str(
                parameters.output_path_for(self.active_user.default_output_directory).parent
                / f"{parameters.output_file_stem}_DFM"
            )
            archive_output = str(
                parameters.output_path_for(self.active_user.default_output_directory).parent
                / f"{parameters.output_file_stem}_DFM.zip"
            )

        summary.update(
            "\n".join(
                [
                    f"Active user: {active_user_name}",
                    f"Pads: {parameters.columns} columns x {parameters.rows} rows",
                    f"Hole count: {parameters.hole_count}",
                    (
                        "Board size: "
                        f"{parameters.board_width_mm:.2f} mm x {parameters.board_height_mm:.2f} mm"
                    ),
                    f"Pitch: {parameters.pitch_mm:.2f} mm",
                    (
                        "Pad / drill: "
                        f"{parameters.pad_diameter_mm:.2f} mm / {parameters.pth_drill_mm:.2f} mm"
                    ),
                    f"Mounting holes: {mounting_holes}",
                    f"Corners: {corner_style}",
                    f"Fabrication: {fabrication_label}",
                    f"Output root: {output_root}",
                    f"Board folder: {parameters.output_directory_name}",
                    f"Output file: {parameters.output_file_name}",
                    f"Resolved path: {output_path}",
                    f"DFM directory: {dfm_path}",
                    f"ZIP archive: {archive_output}",
                ]
            )
        )
        preview.update(render_board_preview(parameters))

    def _activate_user(
        self,
        profile: UserProfile | None,
        *,
        persist_last_user: bool = False,
        log_message: str | None = None,
    ) -> None:
        self.active_user = profile
        self._syncing_controls = True

        try:
            user_select = self.query_one("#user_select", Select)
            active_user_name = self.query_one("#active_user_name", Static)
            output_directory = self.query_one("#default_output_directory", Input)
            theme_select = self.query_one("#theme_select", Select)
            user_summary = self.query_one("#user_summary", Static)

            if profile is None:
                if user_select.value != Select.BLANK:
                    user_select.value = Select.BLANK
                active_user_name.update("No active user selected")
                if output_directory.value:
                    output_directory.value = ""
                if theme_select.value != self._default_theme_name():
                    theme_select.value = self._default_theme_name()
                user_summary.update(
                    "\n".join(
                        [
                            "No saved user selected.",
                            f"Local data: {data_directory()}",
                        ]
                    )
                )
                self._set_active_user_controls_enabled(False)
                self._refresh_preview()
                return

            theme_name = self._coerce_theme_name(profile.theme)
            if user_select.value != profile.slug:
                user_select.value = profile.slug
            active_user_name.update(profile.name)
            if output_directory.value != profile.default_output_directory:
                output_directory.value = profile.default_output_directory
            if theme_select.value != theme_name:
                theme_select.value = theme_name
            user_summary.update(
                "\n".join(
                    [
                        f"Name: {profile.name}",
                        f"Slug: {profile.slug}",
                        f"Output root: {profile.default_output_directory}",
                        f"Theme: {theme_name}",
                        f"Boards saved: {len(profile.boards)}",
                        f"Local data: {data_directory()}",
                        (
                            "Last board: "
                            f"{profile.last_generated_board_name or 'None'}"
                        ),
                    ]
                )
            )
            self.theme = theme_name
            self._set_active_user_controls_enabled(True)
        finally:
            self._syncing_controls = False

        if persist_last_user or log_message:
            update_app_state(
                last_user_slug=profile.slug if persist_last_user else None,
                message=log_message,
                user_slug=profile.slug,
            )

        self._refresh_preview()

    def _restore_last_user(self) -> None:
        state = load_app_state()
        if not state.last_user_slug:
            return

        profile = load_user_profile(state.last_user_slug)
        if profile is None:
            return

        self._activate_user(profile)
        self._set_settings_status(f"Restored last user: {profile.name}.", error=False)

    def _refresh_user_list(self, *, selected_slug: str = "") -> None:
        select = self.query_one("#user_select", Select)
        profiles = list_user_profiles()
        options = [(profile.name, profile.slug) for profile in profiles]
        target_value: str | object

        if selected_slug and any(profile.slug == selected_slug for profile in profiles):
            target_value = selected_slug
        elif self.active_user and any(profile.slug == self.active_user.slug for profile in profiles):
            target_value = self.active_user.slug
        else:
            target_value = Select.BLANK

        self._syncing_controls = True
        try:
            select.set_options(options)
            if select.value != target_value:
                select.value = target_value
        finally:
            self._syncing_controls = False

        if not profiles:
            self.query_one("#user_summary", Static).update(
                "\n".join(
                    [
                        "No saved users found yet.",
                        f"Local data: {data_directory()}",
                    ]
                )
            )

    def _toggle_create_user_form(self, visible: bool) -> None:
        panel = self.query_one("#create_user_panel", Vertical)
        if visible:
            panel.remove_class("hidden")
            if not self.query_one("#new_output_directory", Input).value.strip():
                default_directory = (
                    self.active_user.default_output_directory
                    if self.active_user is not None
                    else "."
                )
                self.query_one("#new_output_directory", Input).value = default_directory
            self.query_one("#new_user_name", Input).focus()
        else:
            panel.add_class("hidden")
            self.query_one("#new_user_name", Input).value = ""
            self.query_one("#new_output_directory", Input).value = ""

    def _create_user(self) -> None:
        try:
            profile = UserProfile(
                name=self._value("new_user_name"),
                default_output_directory=self._value("new_output_directory"),
                theme=self.theme or self._default_theme_name(),
            )
        except ValueError as error:
            self._set_settings_status(str(error), error=True)
            return

        existing = load_user_profile(profile.slug)
        if existing is not None:
            self._set_settings_status(
                f"A user named '{existing.name}' already exists.",
                error=True,
            )
            return

        try:
            save_user_profile(profile)
        except OSError as error:
            self._set_settings_status(f"Unable to save user profile: {error}", error=True)
            return

        self._refresh_user_list(selected_slug=profile.slug)
        self._toggle_create_user_form(False)
        self._activate_user(
            profile,
            persist_last_user=True,
            log_message=f"Created user '{profile.name}'.",
        )
        self._set_settings_status(f"Created user {profile.name}.", error=False)

    def _save_active_user_settings(self) -> None:
        if self.active_user is None:
            self._set_settings_status("Select a user before saving settings.", error=True)
            return

        try:
            updated_profile = UserProfile(
                name=self.active_user.name,
                default_output_directory=self._value("default_output_directory"),
                theme=self._coerce_theme_name(str(self.query_one("#theme_select", Select).value)),
                last_generated_board_name=self.active_user.last_generated_board_name,
                last_generated_board_details=dict(self.active_user.last_generated_board_details),
                boards=dict(self.active_user.boards),
            )
        except ValueError as error:
            self._set_settings_status(str(error), error=True)
            return

        try:
            save_user_profile(updated_profile)
        except OSError as error:
            self._set_settings_status(f"Unable to save user settings: {error}", error=True)
            return

        self._activate_user(
            updated_profile,
            persist_last_user=True,
            log_message=f"Saved settings for '{updated_profile.name}'.",
        )
        self._set_settings_status(f"Saved settings for {updated_profile.name}.", error=False)

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
        if self.active_user is None:
            return

        self.active_user.boards[board_name] = board_details
        self.active_user.last_generated_board_name = board_name
        self.active_user.last_generated_board_details = dict(board_details)
        save_user_profile(self.active_user)
        update_app_state(
            last_user_slug=self.active_user.slug,
            message=f"Generated board '{board_name}'.",
            user_slug=self.active_user.slug,
            board_name=board_name,
            details=board_details,
        )
        self._activate_user(self.active_user)

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

    def _set_active_user_controls_enabled(self, enabled: bool) -> None:
        self.query_one("#default_output_directory", Input).disabled = not enabled
        self.query_one("#theme_select", Select).disabled = not enabled
        self.query_one("#save_user_settings", Button).disabled = not enabled

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
