# EZProto Parametric Enclosure Generator Plan

## 1. Overview

Implement a parametric enclosure generation system that:

- Accepts a user-provided PCB STEP file
- Extracts geometric features (outline + optional mounting holes)
- Applies user-defined parameters
- Generates an enclosure around the PCB (Lid and Bottom Parts)
- Exports the result as a STEP file

---

## 2. Core Dependencies

- cadquery
- OCP (OpenCascade bindings via CadQuery)
- numpy (optional for geometry math)

---

## 3. High-Level Pipeline

1. Load PCB STEP file
2. Normalize geometry (orientation, origin)
3. Extract PCB reference geometry:
   - Board outline
   - Mounting holes (optional)
4. Apply user parameters
5. Generate enclosure geometry:
   - Base
   - Lid
   - Walls
   - Standoffs
6. Combine solids
7. Export STEP file

---

## 4. Module Structure

### 4.1 enclosure/
- `loader.py` → STEP import + normalization
- `extract.py` → geometry extraction
- `builder.py` → enclosure generation
- `features.py` → standoffs, bosses, cutouts
- `export.py` → STEP export
- `models.py` → parameter definitions

---

## 5. Data Models

```python
class EnclosureParams:
    wall_thickness: float
    floor_thickness: float
    enclosure_height: float
    pcb_offset: float
    standoff_height: float
    standoff_diameter: float
    hole_diameter: float | None
    hole_count: int | None
````

---

## 6. STEP Loading

### Goal:

Load PCB STEP and convert into a CadQuery object

### Implementation:

```python
import cadquery as cq

def load_step(path: str):
    return cq.importers.importStep(path)
```

### Notes:

* Validate file exists
* Ensure single solid or handle multiple bodies

---

## 7. Geometry Normalization

### Goal:

Ensure PCB lies flat on XY plane

### Steps:

* Compute bounding box
* Detect dominant planar face
* Align normal to Z-axis
* Translate bottom face to Z=0

---

## 8. PCB Outline Extraction

### Strategy (v1 - simple and robust):

Use bounding box

```python
def get_bbox_outline(shape):
    bb = shape.val().BoundingBox()
    return bb.xlen, bb.ylen
```

### Strategy (v2 - advanced):

* Find largest planar face
* Extract outer wire
* Convert to 2D profile

Fallback to bounding box if extraction fails

---

## 9. Mounting Hole Detection

### Strategy:

* Iterate faces
* Identify cylindrical faces
* Filter by:

  * Axis parallel to Z
  * Diameter within expected range

```python
def detect_holes(shape):
    # pseudo logic
    holes = []
    for face in shape.faces():
        if face.isCylinder():
            if is_valid_diameter(face):
                holes.append(face.center())
    return holes
```

### Fallback:

Board Edge offset method

---

## 10. Enclosure Generation

### 10.1 Base Plate

```python
def create_base(length, width, thickness):
    return cq.Workplane("XY").box(length, width, thickness)
```

---

### 10.2 Walls

* Offset outline by wall_thickness + pcb_offset
* Extrude upwards

```python
def create_walls(length, width, height, wall_thickness):
    outer = cq.Workplane("XY").rect(length, width)
    inner = cq.Workplane("XY").rect(
        length - 2 * wall_thickness,
        width - 2 * wall_thickness
    )
    return outer.extrude(height).cut(inner.extrude(height))
```

### 10.3 Lid

Create a removable lid that mates with the enclosure.

**Design Approach (MVP):**
* Flat plate that sits on top of walls
* Screw holes aligned with standoffs

**Implementation:**

```python
def create_lid(length, width, params):
    # Top plate
    lid = cq.Workplane("XY").rect(length, width).extrude(params.lid_thickness)

    # Lip (fits inside enclosure)
    lip_outer = cq.Workplane("XY").rect(
        length - 2 * params.lid_clearance,
        width - 2 * params.lid_clearance
    )

    lip_inner = cq.Workplane("XY").rect(
        length - 2 * (params.wall_thickness + params.lid_clearance),
        width - 2 * (params.wall_thickness + params.lid_clearance)
    )

    lip = lip_outer.extrude(-params.lid_lip_height).cut(
        lip_inner.extrude(-params.lid_lip_height)
    )

    return lid.union(lip)
```

**Screw Holes in Lid**

If standoffs are present:

```python
def add_lid_holes(lid, hole_positions, hole_diameter):
    wp = lid.faces(">Z").workplane()

    for (x, y) in hole_positions:
        wp = wp.pushPoints([(x, y)]).hole(hole_diameter)

    return wp
```

**Alignment Notes:**
* Lid should sit flush with wall top
* Lip should insert inside walls with:
* clearance ≈ 0.2–0.5 mm (3D printing tolerance)
* Lip height should be less than wall height

**Assembly Positioning:**
* Lid should be translated to sit on top of walls:
```lid = lid.translate((0, 0, enclosure_height))```

---

### 10.4 PCB Cavity

* Create inner cavity using PCB footprint + offset
* Subtract from enclosure

---

### 10.5 Standoffs

```python
def create_standoff(x, y, height, diameter, hole_dia):
    return (
        cq.Workplane("XY")
        .center(x, y)
        .circle(diameter / 2)
        .extrude(height)
        .faces(">Z")
        .hole(hole_dia)
    )
```

---

## 11. Assembly

```python
def build_enclosure(params, pcb_shape):
    base = create_base(...)
    walls = create_walls(...)
    standoffs = ...

    result = base.union(walls)

    for s in standoffs:
        result = result.union(s)

    return result
```

---

## 12. Export

```python
def export_step(shape, path):
    shape.export(path)
```

---

## 13. UI Integration (EZProto)

### Inputs:

* STEP file path
* Wall thickness
* Height
* Offset
* Hole settings (auto/manual)

### Outputs:

* Generated STEP file
* Optional preview (future)

---

## 14. Error Handling

* Invalid STEP file → fail early
* Geometry extraction failure → fallback to bounding box
* Boolean failure → retry or simplify geometry

---

## 15. MVP Scope (IMPORTANT)

Limit initial implementation to:

* Bounding box-based enclosure
* Manual or optional hole detection
* Simple rectangular enclosure
* No fillets/chamfers
* No connector cutouts

---

## 16. Future Enhancements

* True outline extraction from STEP
* Fillets and rounded edges
* Snap-fit lids
* Connector cutouts (USB, headers)
* Multi-part enclosures (top/bottom split)
* Visualization in TUI

---

## 17. Minimal Working Example Target

Codex should first implement:

1. Load STEP
2. Compute bounding box
3. Generate box enclosure around it
4. Export STEP

Only after this works:
→ Add hole detection
→ Add standoffs
→ Improve outline extraction

---

## 18. Acceptance Criteria

* User provides STEP file
* User inputs parameters
* App generates valid enclosure STEP
* Output opens correctly in CAD tools
* Geometry is watertight (no broken solids)

---
