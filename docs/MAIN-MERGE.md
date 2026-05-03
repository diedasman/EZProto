# Main Merge Plan: Protoboard-Only Scope

EZProto `dev` currently contains the protoboard application plus experimental Breakout board and parametric enclosure work. The `main` branch should receive the production-ready protoboard tool and the shared application infrastructure, while Breakout and enclosure work stays on `dev` until it is ready.

## Scope Decision

Merge into `main`:

- Protoboard parameter model, validation, preview, KiCad PCB export, and optional Gerber/drill/ZIP fabrication export.
- Textual app shell needed to run the protoboard workflow.
- File handling, app state, user profile persistence, output directory settings, theme persistence, and legacy local-storage migration.
- CLI entry point, web serve mode, updater support, package metadata, assets needed by the protoboard app, and protoboard-focused tests.

Keep only on `dev`:

- `src/ezproto/breakout/`
- Breakout footprint parsing, header generation, routing, KiCad rendering, preview rendering, app view, app actions, tests, and fixture data.
- Enclosure UI/view stubs and any future enclosure generator modules.
- README sections, images, or screenshots that advertise Breakout/enclosure as available on `main`.

## Current Branch Shape

As of this plan, `main` contains only `README.md`. The `dev` branch adds the full Python package and test suite. A normal merge would bring in the experimental tools, so use a selective merge or a `--no-commit` merge followed by explicit pruning.

Recommended approach: create a merge branch from `main` and selectively restore vetted paths from `dev`. This keeps the `main` history clean and makes review easier.

```bash
git switch main
git pull --ff-only
git switch -c merge/protoboard-only
```

## File Intake Plan

Add from `dev` without feature pruning:

- `pyproject.toml`
- `src/ezproto/__init__.py`
- `src/ezproto/__main__.py`
- `src/ezproto/assets/logo.txt`
- `src/ezproto/models.py`
- `src/ezproto/storage.py`
- `src/ezproto/fabrication.py`
- `src/ezproto/updater.py`
- `src/ezproto/web.py`
- `users/.gitkeep`
- `.gitignore`, after reviewing the local uncommitted `.gitignore` change on `dev`

Add from `dev`, then edit to remove Breakout/enclosure references:

- `src/ezproto/app.py`
- `src/ezproto/app.tcss`
- `src/ezproto/kicad.py`
- `src/ezproto/preview.py`
- `README.md`

Add protoboard/shared tests from `dev`, then adjust any expectations that mention removed sections:

- `tests/test_app_generation.py`
- `tests/test_fabrication.py`
- `tests/test_kicad.py`
- `tests/test_main.py`
- `tests/test_storage.py`
- `tests/test_updater.py`
- `tests/test_welcome_tab.py`
- `tests/test_preview.py`

Do not add to `main`:

- `src/ezproto/breakout/`
- `tests/test_breakout.py`
- `tests/test_breakout_app.py`
- `tests/fixtures/simple_soic6.kicad_mod`
- Any future `src/ezproto/enclosure/` files if present on `dev`

Do not add as a tracked runtime state file:

- `app_state.json`

`app_state.json` should be generated in the per-user EZProto data directory at runtime, not versioned at the repository root.

## Required Code Pruning

### `src/ezproto/app.py`

Remove these imports:

- `BreakoutBoard`, `BreakoutConfig`, `generate_breakout`
- `load_footprint`
- `write_breakout_board`
- `render_breakout_preview`
- `render_footprint_preview`

Keep these imports:

- `write_fabrication_archive`, `write_fabrication_package`
- `write_kicad_pcb`
- `BoardParameters`
- `render_board_preview`
- storage helpers

Remove Breakout/enclosure constants:

- `BREAKOUT_PITCH_PRESETS`
- `BREAKOUT_TRACE_WIDTH_PRESETS`
- `BREAKOUT_INPUT_IDS`
- `BREAKOUT_CHECKBOX_IDS`
- `BREAKOUT_DFM_CHECKBOX_IDS`

Update navigation:

- `SECTION_BUTTON_TO_VIEW` should include only `nav_home`, `nav_protoboard`, and `nav_settings`.
- Remove `nav_breakout` and `nav_enclosure` buttons from the top nav.
- Update welcome copy so it lists only `HOME, PROTOBOARD, SETTINGS`.
- Keep `Ctrl+G` generating the protoboard form.

Remove UI sections:

- Entire `#breakout` container.
- Entire `#enclosure` container.
- Breakout/enclosure border titles and startup default values in `on_mount`.
- Breakout/enclosure button, input, checkbox, and select event handling.
- `_reset_breakout_form`
- `action_generate_breakout`
- `_read_breakout_config`
- `_refresh_breakout_preview`
- Breakout pitch/trace preset helpers.
- `_selected_breakout_sides`
- `_build_breakout_board_details`
- `_set_breakout_status`
- `_set_breakout_dfm_option_controls_enabled`

Keep protoboard equivalents:

- `_reset_protoboard_form`
- `action_generate`
- `_read_board_parameters`
- `_refresh_preview`
- `_build_board_details`
- `_save_board_record`
- `_save_workspace_settings`
- `_load_workspace_settings`
- `_set_proto_status`
- `_set_settings_status`
- DFM checkbox behavior for protoboard generation

After pruning, run `rg -n "breakout|enclosure" src/ezproto/app.py` and expect no production references.

### `src/ezproto/app.tcss`

Remove selectors that style removed UI:

- `#breakout_*`
- `#breakout`
- `#breakout_layout`
- `#enclosure_*`
- `#enclosure`
- `#enclosure_layout`

Keep shared selectors used by home, protoboard, settings, buttons, status boxes, and DFM options.

After pruning, run `rg -n "breakout|enclosure" src/ezproto/app.tcss` and expect no matches.

### `src/ezproto/kicad.py`

Remove Breakout-specific imports and renderer functions:

- `from copy import deepcopy`
- `from typing import Any`, unless still needed after pruning
- `from ezproto.breakout.footprint_parser import Atom, atom, serialize_sexpr`
- `from ezproto.breakout.models import BreakoutBoard`
- `render_breakout_board`
- `write_breakout_board`
- `_render_imported_footprint`
- `_render_breakout_headers`
- `_render_breakout_mounting_holes`
- `_render_breakout_segments`
- `_remove_children`
- `_upsert_footprint_at`
- `_upsert_footprint_library_link`
- `_upsert_pad_net`
- `_find_child`
- `_node_head`
- `_atom_value`

Keep shared/protoboard helpers:

- `render_kicad_pcb`
- `write_kicad_pcb`
- `_render_pads`
- `_render_mounting_holes`
- `_render_board_outline`
- `_render_outline`
- `_render_rect_outline`
- `_render_line`
- `_render_arc`
- `_mm`
- `_escape_text`

After pruning, run `rg -n "breakout|Breakout|footprint_parser" src/ezproto/kicad.py` and expect no matches.

### `src/ezproto/preview.py`

Remove Breakout/footprint preview imports and functions:

- `BreakoutBoard`
- `ParsedFootprint`
- `render_footprint_preview`
- `render_breakout_preview`
- Breakout canvas helper functions

Keep:

- `render_board_preview`
- protoboard row rendering helpers
- `_corner_label`

After pruning, run `rg -n "breakout|footprint|Breakout" src/ezproto/preview.py` and expect no matches.

### `README.md`

Rewrite the intro and feature list so `main` presents EZProto as a protoboard generator only. Keep setup, run, update, storage, KiCad export, fabrication export, and persistence instructions. Remove or reword:

- Breakout board claims.
- Footprint parser claims.
- Enclosure claims.
- Screenshots that imply unavailable views.
- Any instructions for `.kicad_mod` input.

## Suggested Command Sequence

From `merge/protoboard-only`:

```bash
git checkout dev -- \
  .gitignore \
  pyproject.toml \
  README.md \
  src \
  tests \
  users/.gitkeep
```

Then remove excluded paths before committing:

```bash
rm -rf src/ezproto/breakout
rm -f tests/test_breakout.py tests/test_breakout_app.py
rm -rf tests/fixtures
rm -f app_state.json
```

Then perform the manual pruning described above in `app.py`, `app.tcss`, `kicad.py`, `preview.py`, `README.md`, and affected tests.

Because `.gitignore` is currently modified on `dev`, inspect it before using it as the merge source:

```bash
git diff -- .gitignore
```

Preserve any ignore rules needed for generated output and local user state:

- `output/`
- `app_state.json`
- `users/*.json`
- `!users/.gitkeep`
- Python cache/build/test artifacts

## Test Plan

Run fast checks first:

```bash
python -m pytest \
  tests/test_main.py \
  tests/test_storage.py \
  tests/test_kicad.py \
  tests/test_preview.py \
  tests/test_welcome_tab.py \
  tests/test_updater.py
```

Run fabrication tests where KiCad CLI is available:

```bash
python -m pytest tests/test_fabrication.py tests/test_app_generation.py
```

Run repository-wide checks:

```bash
python -m pytest
rg -n "breakout|Breakout|enclosure|Enclosure|footprint_parser|\\.kicad_mod" src tests README.md
git status --short
```

Expected final search result: no production references to Breakout/enclosure. README may mention that those tools remain on `dev` only if the wording is explicit and does not present them as available in `main`.

## Acceptance Checklist

- `ezproto` launches a Textual app with only Home, Protoboard, and Settings.
- `ezproto --web` serves the same protoboard-only app.
- `ezproto update` still works.
- Protoboard `.kicad_pcb` export works.
- Optional Gerber/drill/ZIP generation works when KiCad CLI is available.
- Workspace settings persist through `EZPROTO_DATA_DIR` or the platform app-data directory.
- Legacy repository-root user data migration remains covered by tests.
- No Breakout/enclosure source modules are tracked on `main`.
- No Breakout/enclosure tests are tracked on `main`.
- `app_state.json` is ignored and not tracked on `main`.
- README accurately describes the `main` branch scope.

## Merge Review Notes

Before opening the PR to `main`, include a short reviewer note:

- This PR intentionally excludes Breakout and enclosure functionality from `main`.
- Shared infrastructure from `dev` is included because it is required by the protoboard workflow.
- Experimental tools remain available on `dev` for continued tuning.
