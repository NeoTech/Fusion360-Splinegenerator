This project was created with the help of Qwen 3.8 Flash Next, 180B parameters on a DGX Spark running as bring your model into github copilot.
----

# Fusion 360 Spline Generator

A native **Fusion 360 Python add-in** that generates parameter-driven 3D models
of **internal (hub / sleeve)** and **external (shaft)** splines from industrial
standards — **DIN 5480**, **ANSI B92.1 / SAE**, and **SAE J499 / ISO 500**
(parallel-side tractor PTO) — or fully custom parametric input.

It builds a clean, fully parametric solid in a single undoable step: one tooth
profile is sketched, extruded, and circular-patterned across the tooth count.

---

## Features

- **Three standards families**
  - **DIN 5480** metric involute splines (module-driven, 30° pressure angle, profile shift).
  - **ANSI B92.1 / SAE** imperial involute splines (stub diametral-pitch series, 30° / 37.5° / 45°).
  - **SAE J499 / ISO 500 / DIN 9611** parallel-side (straight-sided) tractor PTO splines.
- **External shafts and internal hubs** (additive boss or subtractive bore).
- **Build modes**
  - **New Body** — a self-contained spline solid.
  - **Cut into Existing** — subtractively bores / grooves the spline into a
    premade part you select, with no separate blank body.
- **Target-face placement** — pick a planar end face or a cylindrical bore/shaft
  face and the spline is sketched on that surface and patterned about its axis
  (cylinder axis when available, otherwise the face normal).
- **Presets** — common sizes (PTO 6T/21T/20T, DIN 5480 W30/W40/W26, ANSI DP
  series) auto-fill the parameters; manual fields always override.
- **Performance-safe geometry** — a single tooth is patterned with a native
  `CircularPattern` feature (never sketch-level patterning), and each involute
  flank is drawn as one 3-point arc for tangent-continuous, non-faceted faces.
- **Parametric timeline integration** — all features are created inside the
  command's execute handler, so the whole build is one undo transaction.

---

## Installation

1. Copy (or symlink) the `Fusion360-Splinegenerator` folder into your Fusion 360
   add-ins directory:
   - **Windows:** `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
2. Restart Fusion 360 (or toggle the add-in in the **Add-Ins** dialog).
3. The command appears in the **Solid → Create** panel.

> The folder name, the `.manifest` file, and the main `.py` file must all share
> the exact same name (`Fusion360-Splinegenerator`), and the manifest must use
> `"type": "addin"` and `"autodeskProduct": "Fusion"`.

---

## Usage

Open the dialog and fill in the parameters:

| Field | Control | Notes |
| :-- | :-- | :-- |
| **Spline Type** | Dropdown | Selects the math engine and which parameters are shown. |
| **Gender** | Dropdown | External Shaft or Internal Hub. |
| **Build Mode** | Dropdown | New Body, or Cut into Existing (subtractive, needs a target face). |
| **Preset** | Dropdown | Auto-fills parameters; switch to *Custom* to edit freely. |
| **Teeth (z)** | Integer spinner | 4 – 120. |
| **Module (mm)** | Value input | Metric involute only. |
| **DP Series** | Dropdown | Imperial involute only (`12/24`, `16/32`, `24/48`, `32/64`). |
| **Pressure Angle** | Dropdown | 30° / 37.5° / 45° (involute only). |
| **Profile Shift (x)** | Value input | Dimensionless (involute only). |
| **Root Type** | Dropdown | Flat root / Fillet root (involute side-fit). |
| **Center Distance Offset** | Value input | Metric (DIN 5480) adjustment. |
| **Major / Minor Diameter, Tooth Width** | Value inputs | Parallel-side (PTO) only. |
| **Length** | Value input | Extrusion length. |
| **Lead-in Chamfer** | Value input | Optional chamfer on the end face(s). |
| **Target Face (optional)** | Selection | A face or plane to place the spline on. Leave empty for the XY plane. |

Irrelevant fields are hidden automatically for the selected standard, so the
dialog never shows contradictory parameters.

### Placing a spline on an existing part

1. Select the **Gender** and **Build Mode** you want.
2. Pick a **Target Face** on the premade part:
   - a **planar end face** → the spline is sketched on a coincident plane and
     patterned about the face normal;
   - a **cylindrical bore / shaft** → the spline is sketched on a plane
     perpendicular to the cylinder and patterned about the cylinder axis.
3. In **Cut into Existing** mode the cut is made symmetric about the sketch
   plane, so it always bites into the stock regardless of which way the face
   normal points — no direction to guess.

---

## Architecture

```text
Fusion360-Splinegenerator/
├── Fusion360-Splinegenerator.manifest   # add-in manifest
├── Fusion360-Splinegenerator.py         # entry point: run/stop, UI + event handlers
├── core/                                # pure math (no Fusion dependency), all in mm
│   ├── involute_math.py                 #   DIN 5480 / ANSI B92.1 involute flanks
│   ├── parallel_math.py                 #   SAE J499 straight-sided PTO teeth
│   └── presets.py                       #   standards lookup tables
├── cad/                                 # Fusion API layer
│   ├── sketch_builder.py                #   sketches, reference circles, tooth loops
│   ├── feature_builder.py               #   extrude / circular pattern / chamfer / target resolution
│   └── builder.py                       #   orchestrates params -> finished spline body
├── resources/                           # toolbar icon resources
└── tests/                               # stdlib unittest + a fake `adsk` stub
```

**Layering:** `core/` is dependency-free pure geometry (millimetres in,
millimetres out) and is unit-tested directly. `cad/` talks to the Fusion API and
converts mm → cm (`MM_TO_CM = 0.1`). The top-level `.py` only wires the UI and
delegates to `cad.builder.build_spline`.

### Geometry notes

- **Involute flank** (polar form): for a point at radius `r` with local pressure
  angle `α_r` (`cos α_r = r_b / r`), the polar angle from the tooth centre-line is
  `φ(r) = ψ_p + inv(α) − inv(α_r)`, where `inv(a) = tan(a) − a`. The opposite
  flank is the mirror about the tooth bisector. Each flank is emitted as a single
  3-point arc.
- **Base blank:** an external shaft starts from a cylinder at the root radius; an
  internal hub from a cylinder at the major radius, then bored to the crest
  radius so the space cuts open cleanly into the bore.
- **Pattern:** one tooth feature is circular-patterned `z` times about the
  resolved axis.

---

## Testing

The project ships a fake `adsk` module (`tests/adsk_stub.py`) so the CAD layer
and the add-in logic run headless under plain `unittest` (no Fusion, no pytest):

```bash
python -m unittest discover -s tests -t .
```

Coverage includes the pure math engines, presets, the UI parameter collection
and visibility logic, and end-to-end build sequences (feature order, body
counts, target-face placement, and cut-into-existing symmetric cuts).

---

## Requirements

- **Autodesk Fusion 360** with the Python 3 API (the embedded interpreter).
- No third-party Python packages — the add-in and its tests use only the
  standard library and the Fusion `adsk.core` / `adsk.fusion` APIs.

---

## License

See the repository for license details.