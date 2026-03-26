The tool is becoming quite powerful. I also want to add a Breakout Board generator. The scope is that the user supplies a footprint in kiCAD format (directory to file), the PCB size (only rectangular selection for now, width, height), breakout pitch and breakout header locations; NESW of the user's footprint.

# 📦 Breakout Board Generator — Project Plan

## 1. 🎯 Goal

Add a new “Breakout Generator” tab to the existing Textual-based UI that:

* Accepts a KiCad footprint (.kicad_mod or folder)
* Lets user define:
    - Board size (W × H)
    - Breakout pitch (e.g. 2.54 mm)
    - Header placement (North, East, South, West)
* Automatically:
    * Places the footprint centered (or configurable origin)
    * Extracts footprint pads
    * Generates breakout headers
    * Routes pads → headers
* Outputs:
    * .kicad_pcb
    * (optional) gerbers via existing pipeline

## 2. 🧠 Data Models (core/breakout/models.py)

Codex should define clean dataclasses:

```python
@dataclass
class BreakoutConfig:
    footprint_path: Path
    board_width_mm: float
    board_height_mm: float
    pitch_mm: float
    sides: list[str]  # ["N", "E", "S", "W"]
    header_offset_mm: float = 2.0
    margin_mm: float = 2.0


@dataclass
class Pad:
    name: str
    x: float
    y: float
    net: str | None


@dataclass
class HeaderPin:
    x: float
    y: float
    net: str


@dataclass
class BreakoutBoard:
    pads: list[Pad]
    headers: list[HeaderPin]
    traces: list[tuple]  # simple segments for now

```

## 3. ⚙️ Core Logic

### 3.1 Footprint Parsing (footprint_parser.py)

**Goal:** Extract pads from KiCad footprint

Approach:

* Parse ```.kicad_mod``` (S-expression format)
* Extract:
    * ```(pad "1" smd rect (at x y) ...)```

**Output:**
```
def load_footprint(path: Path) -> list[Pad]
```

### 3.2 Header Generation (header_generator.py)

**Goal:** Place header pins along selected edges

Rules:

* Evenly distribute pins along chosen edge
* Align count with number of pads
* Maintain pitch spacing

Example:
```
def generate_headers(pads: list[Pad], config: BreakoutConfig) -> list[HeaderPin]
```

**Placement logic:**

| Side | Axis       | Direction    |
|------|------------|--------------|
| N    | top edge   | left → right |
| S    | bottom     | left → right |
| E    | right      | top → bottom |
| W    | left       | top → bottom |

### 3.3 Net Mapping

Simple mapping:

```
pad[i] → header[i]
```

### 3.4 Routing Engine (router.py)

**V1: VERY SIMPLE**

* Straight-line routing:
```python
def route(pads, headers) -> list[segments]
```

Each route:

* 1 or 2 segments (Manhattan optional)
* No collision avoidance initially

### 4.5 Generator Orchestrator (generator.py)

Main entry point:
```python

def generate_breakout(config: BreakoutConfig) -> BreakoutBoard:
    pads = load_footprint(config.footprint_path)
    headers = generate_headers(pads, config)
    traces = route(pads, headers)

    return BreakoutBoard(
        pads=pads,
        headers=headers,
        traces=traces
    )
```
## 3. 🧾 KiCad PCB Writer Integration

Extend existing writer:

```
def write_breakout_board(board: BreakoutBoard, output_path: Path)
```

Responsibilities:

* Create board outline (rectangle)
* Place:
    * footprint
    * header pads (through-hole)
    * Add nets
    * Draw tracks

## 4. 🖥️ UI: Breakout Tab (Textual)
File: ui/tabs/breakout_tab.py
Layout
```
+--------------------------------------------------+
| Breakout Generator                               |
+----------------------+---------------------------+
| Inputs               | Preview (future)          |
|                      |                           |
| Footprint path       |                           |
| Board Width          |                           |
| Board Height         |                           |
| Pitch                |                           |
| Sides (checkboxes)   |                           |
|                      |                           |
| [ Generate ]         |                           |
+----------------------+---------------------------+
| Status / Logs                                    |
+--------------------------------------------------+
```

**Widget Breakdown**
```python
class BreakoutTab(Container):

    def compose(self):
        yield Input(placeholder="Footprint path")
        yield Input(placeholder="Width (mm)")
        yield Input(placeholder="Height (mm)")
        yield Input(placeholder="Pitch (mm)")

        yield Checkbox("North")
        yield Checkbox("East")
        yield Checkbox("South")
        yield Checkbox("West")

        yield Button("Generate", id="generate")
        yield Static(id="status")
```
**Event Handling**
```python
@on(Button.Pressed, "#generate")
def generate_board(self):
    config = self._collect_inputs()
    
    board = generate_breakout(config)

    write_breakout_board(board, output_path)

    self.query_one("#status").update("Done!")
```

## 5. 🔌 Integration Into Existing App

Modify main UI

Where tabs are defined:
```python
TabPane("Breakout", BreakoutTab())
```

## 6. 🧪 Testing Plan

**Unit Tests**

* Footprint parsing:
    * Loads pads correctly
* Header generation:
    * Correct count & spacing
* Routing:
    * Produces valid segments

**Integration Test**

* Input: known footprint
* Output: valid .kicad_pcb
* Open in KiCad → visually verify