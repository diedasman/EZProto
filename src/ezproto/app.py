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

from ezproto.breakout import BreakoutBoard, BreakoutConfig, generate_breakout
from ezproto.breakout.footprint_parser import load_footprint
from ezproto.fabrication import write_fabrication_archive, write_fabrication_package
from ezproto.kicad import write_breakout_board, write_kicad_pcb
from ezproto.models import BoardParameters
from ezproto.preview import (
    render_board_preview,
    render_breakout_preview,
    render_footprint_preview,
)
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

WELCOME_ART_PATH = Path(__file__).resolve().parent / "welcome_art.txt"

PITCH_PRESETS = {
    "pitch_1_00": "1.0",
    "pitch_2_00": "2.0",
    "pitch_2_54": "2.54",
    "pitch_5_08": "5.08",
}

BREAKOUT_PITCH_PRESETS = {
    "breakout_pitch_1_00": "1.0",
    "breakout_pitch_2_00": "2.0",
    "breakout_pitch_2_54": "2.54",
    "breakout_pitch_5_08": "5.08",
}

BREAKOUT_TRACE_WIDTH_PRESETS = {
    "breakout_trace_0_20": "0.20",
    "breakout_trace_0_25": "0.25",
    "breakout_trace_0_30": "0.30",
    "breakout_trace_0_50": "0.50",
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

BREAKOUT_INPUT_IDS = {
    "breakout_board_name",
    "breakout_footprint_path",
    "breakout_board_width",
    "breakout_board_height",
    "breakout_pitch",
    "breakout_trace_width",
    "breakout_header_offset",
    "breakout_margin",
}

BREAKOUT_CHECKBOX_IDS = {
    "breakout_side_n",
    "breakout_side_e",
    "breakout_side_s",
    "breakout_side_w",
}

BREAKOUT_DFM_CHECKBOX_IDS = {
    "breakout_generate_gerbers",
    "breakout_include_drill",
    "breakout_zip_output",
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
        with TabbedContent(initial="welcome", id="main_tabs"):

            with TabPane("WELCOME", id="welcome"):
                with Container(id="welcome_layout"):
                    with Horizontal(id="welcome_panel"):

                        welcome_art = WELCOME_ART_PATH.read_text(encoding="utf-8")

                        with Vertical(id="welcome_logo_column"):
                            yield Static(welcome_art, id="welcome_art")

                        with Vertical(id="welcome_message_column"):
                            yield Static(
                                (
                                    "EZProto is a keyboard-friendly workspace for protoboards, "
                                    "breakouts, and fabrication exports."
                                ),
                                id="welcome_intro",
                            )

                            yield Static(
                                (
                                    "+---------------+\n"
                                    "|      Tab      |\n"
                                    "|   (+ Shift)   |\n"
                                    "+---------------+\n\n"
                                    "Press Tab to cycle through the main sections of the app: PROTOBOARD, BREAKOUT, KEYBOARD, ENCLOSURE, and SETTINGS.\n"
                                    "Press Shift+Tab to cycle backwards."
                                ),
                                id="welcome_navigation",
                            )

                            yield Static(
                                (
                                    "+-------+   +-------+\n"
                                    "| Left  |   | Right |\n"
                                    "|  <-   |   |  ->   |\n"
                                    "+-------+   +-------+\n\n"
                                    "Press the Left and Right arrow keys to move between tabs."
                                ),
                                id="welcome_tab_navigation",
                            )

                            yield Static(
                                (
                                    "Open SETTINGS first to choose the active user and output folder.\n"
                                    "Use PROTOBOARD or BREAKOUT to define a board.\n"
                                    "Press Ctrl+G when you are ready to generate files."
                                ),
                                id="welcome_getting_started",
                            )

                            yield Static(
                                (
                                    "Ctrl+G  Generate the current board\n"
                                    "Ctrl+Q  Quit EZProto\n"
                                    "Tab labels at the top show the current workspace."
                                ),
                                id="welcome_shortcuts",
                            )


            with TabPane("PROTOBOARD", id="protoboard"):
                with Container(id="protoboard_layout"):
                    with Vertical(id="parameters_panel", classes="panel"):
                        with Container(id="form"):
                            
                            yield Label("Board name", classes="field_label")
                            yield Input(placeholder="Protoboard", id="board_name")

                            yield Label("Columns", classes="field_label")
                            with Horizontal(id="dimensions_row"):
                                # yield Label("Columns", classes="field_label")
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
                                ROUNDED_CORNER_OPTIONS,
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

            with TabPane("BREAKOUT", id="breakout"):
                with Container(id="breakout_layout"):
                    with Vertical(id="breakout_parameters_panel", classes="panel"):
                        with Container(id="breakout_form"):
                            
                            with Horizontal(id="breakout_footprint_row"):
                                yield Label("Footprint path", classes="field_label")
                                yield Input(
                                    id="breakout_footprint_path",
                                    placeholder="Path to a .kicad_mod file or folder",
                                )
                            
                            with Horizontal(id="breakout_dimensions_row"):
                                yield Label("Board width", classes="field_label")
                                yield Input(id="breakout_board_width", placeholder="Width (mm)")
                                yield Label("Board height", classes="field_label")
                                yield Input(id="breakout_board_height", placeholder="Height (mm)")

                            with Horizontal(id="breakout_pitch_row"):
                                yield Label("Pitch (mm)", classes="field_label")

                                with Horizontal(id="breakout_pitch_controls"):
                                    yield Input(id="breakout_pitch", placeholder="Custom")

                                    yield Button("1 mm", id="breakout_pitch_1_00", classes="pitch_preset")
                                    yield Button("2 mm", id="breakout_pitch_2_00", classes="pitch_preset")
                                    yield Button("2.54 mm", id="breakout_pitch_2_54", classes="pitch_preset")
                                    yield Button("5.08 mm", id="breakout_pitch_5_08", classes="pitch_preset")

                            
                            with Horizontal(id="breakout_trace_width_row"):
                                yield Label("Trace width (mm)", classes="field_label")

                                with Horizontal(id="breakout_trace_width_controls"):

                                    yield Input(id="breakout_trace_width", placeholder="Custom")
                                    yield Button("0.20 mm", id="breakout_trace_0_20", classes="trace_preset")
                                    yield Button("0.25 mm", id="breakout_trace_0_25", classes="trace_preset")
                                    yield Button("0.30 mm", id="breakout_trace_0_30", classes="trace_preset")
                                    yield Button("0.50 mm", id="breakout_trace_0_50", classes="trace_preset")

                            with Horizontal(id="breakout_offsets_row"):
                                yield Label("Header", classes="field_label")
                                yield Input(
                                    id="breakout_header_offset",
                                    placeholder="Offset (mm)",
                                )
                                yield Label("Side margin", classes="field_label")
                                yield Input(
                                    id="breakout_margin",
                                    placeholder="Margin (mm)",
                                )

                            with Horizontal(id="breakout_sides_row"):
                                yield Label("Header sides", classes="field_label")

                                with Horizontal(id="breakout_side_controls"):
                                    yield Checkbox("North", id="breakout_side_n", value=True)
                                    yield Checkbox("East", id="breakout_side_e")
                                    yield Checkbox("South", id="breakout_side_s", value=True)
                                    yield Checkbox("West", id="breakout_side_w")

                            with Horizontal(id="breakout_rounded_corners_row"):
                                yield Label("Rounded corners", classes="field_label")
                                yield Select[str](
                                    ROUNDED_CORNER_OPTIONS,
                                    prompt="Square corners",
                                    id="breakout_rounded_corners",
                                )

                            with Horizontal(id="breakout_dfm_options_row"):
                                yield Label("DFM export", classes="field_label")
                                with Horizontal(id="breakout_dfm_options"):
                                    yield Checkbox("Generate Gerbers", id="breakout_generate_gerbers")
                                    yield Checkbox(
                                        "Include drill file",
                                        id="breakout_include_drill",
                                        classes="dfm_option",
                                    )
                                    yield Checkbox(
                                        ".ZIP archive",
                                        id="breakout_zip_output",
                                        classes="dfm_option",
                                    )
                            
                            with Horizontal(id="output_controls_row"):
                                yield Label("Board name", classes="field_label")
                                with Horizontal(id="breakout_output_controls"):
                                    yield Input(
                                        id="breakout_board_name",
                                        placeholder="Defaults to the footprint name",
                                    )
                                    yield Button(
                                        "Generate Breakout",
                                        variant="primary",
                                        id="generate_breakout",
                                    )

                    with Vertical(id="breakout_summary_panel", classes="panel"):
                        yield Static(id="breakout_summary")
                        yield Static(id="breakout_footprint_summary")
                        with Horizontal(id="breakout_preview_row"):
                            yield Static(id="breakout_footprint_preview")
                            yield Static(id="breakout_preview")
                        yield Static(id="breakout_status", classes="status_box")

            with TabPane("KEYBOARD", id="keyboard"):
                with Container(id="keyboard_layout"):
                    with Vertical(id="keyboard_panel", classes="panel"):
                        
                        yield Label("Board name", classes="field_label")
                        yield Input(placeholder="Keyboard Board", id="keyboard_board_name")
                        yield Static("Keyboard layout generation coming soon!", id="keyboard_placeholder")

                    with Vertical(id="keyboard_summary_panel", classes="panel"):
                        yield Static(id="keyboard_summary")


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
        self.query_one("#breakout_parameters_panel", Vertical).border_title = "Breakout Inputs"
        self.query_one("#breakout_summary_panel", Vertical).border_title = "Breakout Summary"
        self.query_one("#users_panel", Vertical).border_title = "Users"
        self.query_one("#active_user_panel", Vertical).border_title = "Active User"
        self.query_one("#create_user_panel", Vertical).border_title = "Create User"
        self.query_one("#welcome_intro", Static).border_title = "Welcome"
        self.query_one("#welcome_navigation", Static).border_title = "Tab Navigation"
        self.query_one("#welcome_getting_started", Static).border_title = "Getting Started"
        self.query_one("#welcome_shortcuts", Static).border_title = "Quick Keys"
        self.query_one("#board_preview", Static).border_title = "Board Preview"
        self.query_one("#breakout_summary", Static).border_title = "Breakout Details"
        self.query_one("#breakout_footprint_summary", Static).border_title = "Footprint Details"
        self.query_one("#breakout_footprint_preview", Static).border_title = "Footprint Preview"
        self.query_one("#breakout_preview", Static).border_title = "Breakout Preview"
        self.query_one("#summary", Static).border_title = "Board Details"
        self.query_one("#proto_status", Static).border_title = "Status"
        self.query_one("#breakout_status", Static).border_title = "Status"
        self.query_one("#include_drill", Checkbox).value = True
        self.query_one("#breakout_include_drill", Checkbox).value = True
        self.query_one("#breakout_trace_width", Input).value = "0.25"
        self._set_dfm_option_controls_enabled(
            self.query_one("#generate_gerbers", Checkbox).value
        )
        self._set_breakout_dfm_option_controls_enabled(
            self.query_one("#breakout_generate_gerbers", Checkbox).value
        )
        self._set_active_user_controls_enabled(False)
        self._refresh_user_list()
        self._restore_last_user()
        self._sync_breakout_trace_width_preset_state()
        self._refresh_preview()
        self._refresh_breakout_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in PITCH_PRESETS:
            self._apply_pitch_preset(PITCH_PRESETS[event.button.id])
            return
        if event.button.id in BREAKOUT_PITCH_PRESETS:
            self._apply_breakout_pitch_preset(BREAKOUT_PITCH_PRESETS[event.button.id])
            return
        if event.button.id in BREAKOUT_TRACE_WIDTH_PRESETS:
            self._apply_breakout_trace_width_preset(
                BREAKOUT_TRACE_WIDTH_PRESETS[event.button.id]
            )
            return
        if event.button.id == "generate":
            self.action_generate()
            return
        if event.button.id == "generate_breakout":
            self.action_generate_breakout()
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
            return
        if event.input.id in BREAKOUT_INPUT_IDS:
            if event.input.id == "breakout_trace_width":
                self._sync_breakout_trace_width_preset_state()
            self._refresh_breakout_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "generate_gerbers":
            self._set_dfm_option_controls_enabled(event.checkbox.value)
            self._refresh_preview()
            return
        if event.checkbox.id == "breakout_generate_gerbers":
            self._set_breakout_dfm_option_controls_enabled(event.checkbox.value)
            self._refresh_breakout_preview()
            return
        if event.checkbox.id in BREAKOUT_CHECKBOX_IDS:
            self._refresh_breakout_preview()
            return
        if event.checkbox.id in BREAKOUT_DFM_CHECKBOX_IDS:
            self._refresh_breakout_preview()

    def on_select_changed(self, event: Select.Changed) -> None:
        if self._syncing_controls:
            return

        if event.select.id == "rounded_corners":
            self._refresh_preview()
            return

        if event.select.id == "breakout_rounded_corners":
            self._refresh_breakout_preview()
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

    def action_generate_breakout(self) -> None:
        try:
            config = self._read_breakout_config()
            board = generate_breakout(config)
        except ValueError as error:
            self._set_breakout_status(str(error), error=True)
            return

        if self.active_user is None:
            self._set_breakout_status(
                "Select or create a user in SETTINGS before generating files.",
                error=True,
            )
            return

        try:
            written_file = write_breakout_board(
                config.output_path_for(self.active_user.default_output_directory),
                board,
            )
        except OSError as error:
            self._set_breakout_status(f"Unable to write PCB file: {error}", error=True)
            return

        generate_gerbers = self.query_one("#breakout_generate_gerbers", Checkbox).value
        include_drill = (
            generate_gerbers
            and self.query_one("#breakout_include_drill", Checkbox).value
        )
        zip_output = (
            generate_gerbers
            and self.query_one("#breakout_zip_output", Checkbox).value
        )
        dfm_directory = written_file.parent / f"{config.output_file_stem}_DFM"
        archive_path = written_file.parent / f"{config.output_file_stem}_DFM.zip"

        fabrication_files: list[Path] = []
        written_archive: Path | None = None
        fabrication_error: OSError | None = None
        archive_error: OSError | None = None

        if generate_gerbers:
            try:
                fabrication_files = write_fabrication_package(
                    dfm_directory,
                    config,
                    include_drill=include_drill,
                    pcb_path=written_file,
                )
            except OSError as error:
                fabrication_error = error

            if zip_output and fabrication_error is None:
                try:
                    written_archive = write_fabrication_archive(
                        archive_path,
                        fabrication_files,
                        root_directory_name=dfm_directory.name,
                    )
                except OSError as error:
                    archive_error = error

        board_details = self._build_breakout_board_details(
            board,
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
            self._record_generated_board(board.config.board_name, board_details)
        except OSError as error:
            metadata_error = error

        self._refresh_breakout_preview()

        if fabrication_error is not None:
            self._set_breakout_status(
                f"PCB written to {written_file}, but DFM export failed: {fabrication_error}",
                error=True,
            )
            return

        if archive_error is not None:
            self._set_breakout_status(
                f"PCB written to {written_file}; DFM files written to {dfm_directory}, "
                f"but ZIP archive failed: {archive_error}",
                error=True,
            )
            return

        if metadata_error is not None:
            self._set_breakout_status(
                f"PCB written to {written_file}, but metadata update failed: {metadata_error}",
                error=True,
            )
            return

        if generate_gerbers:
            output_messages = [f"DFM files written to {dfm_directory}"]
            if written_archive is not None:
                output_messages.append(f"ZIP archive written to {written_archive}")
            self._set_breakout_status(
                f"PCB written to {written_file}; " + "; ".join(output_messages),
                error=False,
            )
            return

        self._set_breakout_status(f"PCB written to {written_file}", error=False)

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

    def _read_breakout_config(self) -> BreakoutConfig:
        footprint_path = self._value("breakout_footprint_path").strip()
        if not footprint_path:
            raise ValueError("Footprint path is required.")

        return BreakoutConfig(
            board_name=self._value("breakout_board_name"),
            footprint_path=Path(footprint_path),
            board_width_mm=self._parse_float(
                "Board width",
                self._value("breakout_board_width"),
            ),
            board_height_mm=self._parse_float(
                "Board height",
                self._value("breakout_board_height"),
            ),
            pitch_mm=self._parse_float("Pitch", self._value("breakout_pitch")),
            sides=self._selected_breakout_sides(),
            header_offset_mm=self._parse_optional_float(
                "Header offset",
                self._value("breakout_header_offset"),
                default=2.0,
            ),
            margin_mm=self._parse_optional_float(
                "Side margin",
                self._value("breakout_margin"),
                default=2.0,
            ),
            trace_width_mm=self._parse_optional_float(
                "Trace width",
                self._value("breakout_trace_width"),
                default=0.25,
            ),
            rounded_corner_radius_mm=self._read_breakout_rounded_corner_radius(),
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

    def _refresh_breakout_preview(self) -> None:
        footprint_preview = self.query_one("#breakout_footprint_preview", Static)
        footprint_summary = self.query_one("#breakout_footprint_summary", Static)
        summary = self.query_one("#breakout_summary", Static)
        preview = self.query_one("#breakout_preview", Static)
        status = self.query_one("#breakout_status", Static)

        footprint_path = self._value("breakout_footprint_path").strip()
        footprint = None

        if not footprint_path:
            footprint_preview.update("Select a footprint to preview its pads and bounds.")
            footprint_summary.update("Waiting for valid footprint input.\n\nFootprint path is required.")
        else:
            try:
                footprint = load_footprint(Path(footprint_path))
            except ValueError as error:
                footprint_preview.update(f"Waiting for a valid footprint.\n\n{error}")
                footprint_summary.update(f"Waiting for valid footprint input.\n\n{error}")
            else:
                footprint_preview.update(render_footprint_preview(footprint))
                footprint_summary.update(
                    "\n".join(
                        [
                            f"Footprint: {footprint.path}",
                            f"Footprint name: {footprint.name}",
                            f"Logical pads: {len(footprint.pads)}",
                            f"Physical pads: {footprint.physical_pad_count}",
                            f"NPTH ignored: {footprint.npth_pad_count}",
                            (
                                "Footprint bounds: "
                                f"{footprint.bounds.width_mm:.2f} mm x {footprint.bounds.height_mm:.2f} mm"
                            ),
                        ]
                    )
                )

        try:
            config = self._read_breakout_config()
            board = generate_breakout(config)
        except ValueError as error:
            summary.update(f"Waiting for valid breakout inputs.\n\n{error}")
            preview.update("...")
            status.remove_class("success")
            status.remove_class("error")
            status.update("...")
            return

        footprint = board.footprint
        side_label = ", ".join(config.sides)
        corner_style = (
            f"{config.rounded_corner_radius_mm:.2f} mm radius"
            if config.has_rounded_corners
            else "Square corners"
        )
        if self.query_one("#breakout_generate_gerbers", Checkbox).value:
            fabrication_parts = ["Gerbers"]
            if self.query_one("#breakout_include_drill", Checkbox).value:
                fabrication_parts.append("drill")
            if self.query_one("#breakout_zip_output", Checkbox).value:
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
            output_path = str(config.output_path_for(self.active_user.default_output_directory))
            dfm_path = str(
                config.output_path_for(self.active_user.default_output_directory).parent
                / f"{config.output_file_stem}_DFM"
            )
            archive_output = str(
                config.output_path_for(self.active_user.default_output_directory).parent
                / f"{config.output_file_stem}_DFM.zip"
            )

        summary.update(
            "\n".join(
                [
                    f"Active user: {active_user_name}",
                    (
                        "Board size: "
                        f"{config.board_width_mm:.2f} mm x {config.board_height_mm:.2f} mm"
                    ),
                    f"Pitch: {config.pitch_mm:.2f} mm",
                    f"Trace width: {config.trace_width_mm:.2f} mm",
                    f"Sides: {side_label}",
                    f"Header offset: {config.header_offset_mm:.2f} mm",
                    f"Side margin: {config.margin_mm:.2f} mm",
                    f"Corners: {corner_style}",
                    f"Headers: {len(board.headers)}",
                    f"Trace segments: {len(board.traces)}",
                    f"Fabrication: {fabrication_label}",
                    f"Output root: {output_root}",
                    f"Board folder: {config.output_directory_name}",
                    f"Output file: {config.output_file_name}",
                    f"Resolved path: {output_path}",
                    f"DFM directory: {dfm_path}",
                    f"ZIP archive: {archive_output}",
                ]
            )
        )
        preview.update(render_breakout_preview(board))

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
                self._refresh_breakout_preview()
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
        self._refresh_breakout_preview()

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

    def _apply_breakout_pitch_preset(self, value: str) -> None:
        pitch_input = self.query_one("#breakout_pitch", Input)
        pitch_input.value = value
        self._refresh_breakout_preview()

    def _apply_breakout_trace_width_preset(self, value: str) -> None:
        trace_input = self.query_one("#breakout_trace_width", Input)
        trace_input.value = value
        self._sync_breakout_trace_width_preset_state()
        self._refresh_breakout_preview()

    def _read_rounded_corner_radius(self) -> float:
        value = self.query_one("#rounded_corners", Select).value
        if value == Select.BLANK:
            return 0.0
        return float(value)

    def _read_breakout_rounded_corner_radius(self) -> float:
        value = self.query_one("#breakout_rounded_corners", Select).value
        if value == Select.BLANK:
            return 0.0
        return float(value)

    def _sync_breakout_trace_width_preset_state(self) -> None:
        raw_value = self.query_one("#breakout_trace_width", Input).value.strip()
        for button_id, preset in BREAKOUT_TRACE_WIDTH_PRESETS.items():
            button = self.query_one(f"#{button_id}", Button)
            if self._numeric_strings_match(raw_value, preset):
                button.add_class("preset_active")
            else:
                button.remove_class("preset_active")

    @staticmethod
    def _numeric_strings_match(raw_value: str, preset: str) -> bool:
        if not raw_value:
            return False
        try:
            return abs(float(raw_value) - float(preset)) < 1e-9
        except ValueError:
            return False

    def _selected_breakout_sides(self) -> tuple[str, ...]:
        sides: list[str] = []
        if self.query_one("#breakout_side_n", Checkbox).value:
            sides.append("N")
        if self.query_one("#breakout_side_e", Checkbox).value:
            sides.append("E")
        if self.query_one("#breakout_side_s", Checkbox).value:
            sides.append("S")
        if self.query_one("#breakout_side_w", Checkbox).value:
            sides.append("W")
        return tuple(sides)

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

    def _build_breakout_board_details(
        self,
        board: BreakoutBoard,
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
        side_label = ",".join(board.config.sides)
        summary = (
            f"{board.footprint.name}, "
            f"{len(board.pads)} logical pads, "
            f"{board.config.pitch_mm:.2f} mm pitch, "
            f"{board.config.board_width_mm:.2f} mm x {board.config.board_height_mm:.2f} mm board"
        )
        return {
            "board_name": board.config.board_name,
            "board_type": "breakout",
            "summary": summary,
            "footprint_name": board.footprint.name,
            "footprint_file": str(board.footprint.path),
            "logical_pad_count": len(board.pads),
            "physical_pad_count": board.footprint.physical_pad_count,
            "npth_pad_count": board.footprint.npth_pad_count,
            "header_count": len(board.headers),
            "trace_segment_count": len(board.traces),
            "board_width_mm": board.config.board_width_mm,
            "board_height_mm": board.config.board_height_mm,
            "pitch_mm": board.config.pitch_mm,
            "trace_width_mm": board.config.trace_width_mm,
            "header_offset_mm": board.config.header_offset_mm,
            "margin_mm": board.config.margin_mm,
            "rounded_corner_radius_mm": board.config.rounded_corner_radius_mm,
            "sides": list(board.config.sides),
            "sides_label": side_label,
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

    def _set_breakout_status(self, message: str, *, error: bool) -> None:
        self._update_status_widget(
            self.query_one("#breakout_status", Static),
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
    def _parse_optional_float(label: str, raw_value: str, *, default: float) -> float:
        value = raw_value.strip()
        if not value:
            return default
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

    def _set_breakout_dfm_option_controls_enabled(self, enabled: bool) -> None:
        self.query_one("#breakout_include_drill", Checkbox).disabled = not enabled
        self.query_one("#breakout_zip_output", Checkbox).disabled = not enabled

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
