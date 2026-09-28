## 1. PROJECT ROLE & OBJECTIVE
You are an expert Python CAD developer and mechanical engineer specializing in Fusion 360 API development and precision gearing/spline geometry. 
Your task is to build a native Fusion 360 Python Add-In named `Fusion360-SplineGenerator`. 

This add-in must generate parameter-driven 3D models for both **Internal (Hub/Sleeve)** and **External (Shaft)** splines based on industrial standard specifications (DIN 5480, ANSI B92.1, SAE J499 / ISO 500) and custom parametric user inputs.

---

## 2. REFERENCE ARCHITECTURE & REPOSITORIES
Study the structure, event handling, and UI parameter binding patterns from the following open-source projects:

1. **NeoTech/Fusion360-SprocketGenerator** (`https://github.com/NeoTech/Fusion360-SprocketGenerator`):
   - Use as the template for UI setup, `CommandCreatedHandler`, `CommandInputs`, unit parsing, and standard Fusion 360 execution loops (`run()` and `stop()`).
2. **Autodesk Fusion 360 Native Spur Gear Script** (Located in Fusion 360 Add-in samples directory):
   - Reference for native Fusion 360 `adsk.core` and `adsk.fusion` object usage, sketch creation, and parametric point-array interpolation for involute curves.
3. **pyGears / Gear-Involute Math Engines**:
   - Reference for exact parametric Cartesian coordinates for involute curves with profile shift and pressure angles.

---

## 3. DOMAIN STANDARDS & GEOMETRY REQUIREMENTS

### Standards Support
The add-in must support three primary standard families:

1. **DIN 5480 (Metric Involute Splines):**
   - Driven by Module ($m$), Number of Teeth ($z$), Pressure Angle ($\alpha = 30^\circ$), Pitch Diameter ($d = m \cdot z$), and Profile Shift Coefficient ($x$).
   - Fit Types: Flat root ($a_k$), Fillet root ($a_f$).

2. **ANSI B92.1 / SAE (Imperial Involute Splines):**
   - Driven by Diametral Pitch ($DP = P_d / P_s$, e.g., 16/32, 24/48, 32/64), Tooth Count ($z$), and Pressure Angle ($\alpha = 30^\circ$, $37.5^\circ$, or $45^\circ$).
   - Pitch Diameter $D = z / P_d$.

3. **SAE J499 / ISO 500 / DIN 9611 (Parallel-Side / Straight-Sided Splines):**
   - Used for Agricultural Tractor PTOs (e.g., 1-3/8" 6-spline @ 540 RPM, 1-3/8" 21-spline @ 1000 RPM, 1-3/4" 20-spline).
   - Driven by Major Diameter ($D$), Minor Diameter ($d$), Tooth Width ($w$), and Tooth Count ($z$). Straight parallel sidewalls rather than involute curves.

---

## 4. MATHEMATICAL FORMULATION FOR INVOLUTE PROFILES

For involute splines, calculate points along the involute flank using the standard parametric equation:

$$\begin{aligned} r_b &= \frac{d}{2} \cdot \cos(\alpha) \\ x(\theta) &= r_b \cdot (\cos(\theta) + \theta \cdot \sin(\theta)) \\ y(\theta) &= r_b \cdot (\sin(\theta) - \theta \cdot \cos(\theta)) \end{aligned}$$

Where:
- $r_b$ is the base circle radius.
- $\theta$ is the roll angle in radians, evaluated from the base circle or root radius ($r_r$) up to the major/tip radius ($r_a$).
- **Profile Shift ($x \cdot m$):** Shift the pitch point outward/inward to alter tooth thickness and root clearances:
  $$s = \frac{\pi \cdot m}{2} + 2 \cdot x \cdot m \cdot \tan(\alpha)$$

---

## 5. FUSION 360 PERFORMANCE BEST PRACTICES (CRITICAL)

1. **Feature-Based Patterning (Do NOT pattern in sketches):**
   - Draw **ONE** tooth space (for internal cuts) or **ONE** tooth body (for external bosses).
   - Perform the Extrude/Cut operation first.
   - Use `adsk.fusion.CircularPatternFeatures` to pattern the resulting feature across $z$ teeth. Sketch-level patterning destroys CAD performance on high tooth counts.
2. **Point Array Fitted Splines:**
   - Calculate 10–15 discrete points along the involute flank.
   - Create a smooth curve using `sketch.sketchCurves.sketchFittedSplines.add(pointCollection)`.
3. **Parametric Timeline Integration:**
   - Enclose operations inside a single design context (`design.activeComponent`).
   - Create a single parent sketch containing: Base Circle, Pitch Circle, Root Circle, Major Circle, and the Tooth Flank curves.

---

## 6. USER INTERFACE (UI) SPECIFICATION

The plugin UI must be created using `adsk.core.CommandInputs` with the following inputs:

| Input ID | Control Type | Options / Units | Description |
| :--- | :--- | :--- | :--- |
| `spline_type` | Dropdown | Involute (Metric DIN 5480), Involute (Imperial ANSI B92.1), Parallel-Side (PTO / SAE J499) | Selects math engine and parameter set |
| `gender` | Dropdown | External Shaft, Internal Hub | Toggles additive boss vs. subtractive cut |
| `preset` | Dropdown | Custom, Tractor PTO 1-3/8" 6T, Tractor PTO 1-3/8" 21T, DIN 5480 W30x2x14, DIN 5480 W40x2x18 | Auto-fills parameters from internal JSON tables |
| `teeth` | IntegerSpinner | Range: 4 to 120 | Number of teeth ($z$) |
| `module_or_dp` | ValueInput | mm or 1/in | Module ($m$) or Stub DP ($P_d$) depending on standard |
| `pressure_angle` | Dropdown | $30^\circ$, $37.5^\circ$, $45^\circ$ | Involute pressure angle ($\alpha$) |
| `profile_shift` | ValueInput | Dimensionless (e.g., $0.0$, $+0.5$, $-0.5$) | Profile shift factor ($x$) |
| `length` | ValueInput | mm or in | Extrusion length |
| `chamfer` | ValueInput | mm or in | Lead-in chamfer size at shaft/hub face |

---

## 7. TARGET FILE STRUCTURE

Generate the repository following this structure:

```text
Fusion360-SplineGenerator/
├── Fusion360-SplineGenerator.manifest
├── Fusion360-SplineGenerator.py       # Main entry point (run, stop, event handlers)
├── core/
│   ├── __init__.py
│   ├── involute_math.py               # Pure math engine for Cartesian point generation
│   ├── parallel_math.py               # Math engine for straight-sided PTO splines
│   └── presets.py                     # Standards lookup dictionaries (DIN, ANSI, SAE)
├── cad/
│   ├── __init__.py
│   ├── sketch_builder.py              # Fusion 360 API sketch construction
│   └── feature_builder.py             # Extrusion, circular pattern, chamfer features
└── resources/
    └── UI.png                         # Command icon resources