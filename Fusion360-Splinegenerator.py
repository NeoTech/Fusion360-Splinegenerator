"""
Fusion360-SplineGenerator.py
============================

Main entry point for the Fusion 360 Spline Generator add-in.

Implements:
* ``CommandCreatedHandler`` wiring an execute + input-changed handler.
* Dynamic UI: choosing a preset auto-fills and locks the parameter inputs.
* One-step undo: all features are created inside the command's ``execute``
  handler, which Fusion automatically groups into a single transaction.
* Clean ``stop()`` that tears down UI controls and event handlers.

All geometry handed to the CAD layer is in millimetres; conversion to Fusion's
internal centimetre base unit happens inside ``cad.sketch_builder`` /
``cad.feature_builder``.
"""

from __future__ import annotations

import os
import sys
import importlib
import traceback

import adsk.core as core
import adsk.fusion as fusion

# Ensure the add-in package root is importable when Fusion loads this file.
_addin_dir = os.path.dirname(os.path.abspath(__file__))
if _addin_dir not in sys.path:
    sys.path.insert(0, _addin_dir)

try:
    from cad import builder, sketch_builder, feature_builder  # noqa: E402
    from core import presets, involute_math, parallel_math  # noqa: E402

    # Fusion caches submodules in sys.modules across add-in reloads, so a
    # plain "from core import presets" can return a STALE module after we edit
    # presets.py (the top-level .py re-runs but the submodule does not). Force
    # every submodule to re-read from disk so new symbols are visible without
    # restarting Fusion. Order matters: reload the leaves first, then builder,
    # which re-imports them. (Missing a leaf is exactly how "module
    # 'cad.sketch_builder' has no attribute 'build_tooth_edges'" happens after
    # editing that file.) Safe: these modules are side-effect free.
    importlib.reload(involute_math)
    importlib.reload(parallel_math)
    importlib.reload(presets)
    importlib.reload(sketch_builder)
    importlib.reload(feature_builder)
    importlib.reload(builder)
except Exception:  # pragma: no cover - import-time diagnostics
    _log = os.path.join(_addin_dir, "splinegenerator_import_error.log")
    with open(_log, "w", encoding="utf-8") as _fh:
        _fh.write(traceback.format_exc())
    raise


_app: core.Application = None
_ui: core.UserInterface = None
# _handlers holds PERMANENT handlers (the CommandCreatedHandler) for the whole
# add-in lifetime. _cmd_handlers holds the PER-DIALOG handlers (execute /
# inputChanged / destroy) and is cleared when a dialog closes. Keeping them in
# separate lists is critical: if the destroy handler cleared _handlers it would
# drop the CreatedHandler reference, letting it be garbage-collected, so the
# next use of the command would never re-attach its handlers ("needs restart").
_handlers = []
_cmd_handlers = []
_ctrl = None  # toolbar control, kept for cleanup in stop()
_active_cmd = None  # the currently open dialog command, for inputChanged

_cmd_def_id = "SplineGeneratorDlg"
_panel_id = "SolidCreatePanel"
_reference_cmd = "Extrude"

# Input identifiers (must match the UI table in the project instructions).
ID_SPLINE_TYPE = "spline_type"
ID_GENDER = "gender"
ID_PRESET = "preset"
ID_TEETH = "teeth"
ID_MODULE_OR_DP = "module_or_dp"
ID_DP_SERIES = "dp_series"
ID_ROOT_TYPE = "root_type"
ID_CENTER_OFFSET = "center_distance_offset"
ID_PRESSURE_ANGLE = "pressure_angle"
ID_PROFILE_SHIFT = "profile_shift"
ID_MAJOR = "major_diameter"
ID_MINOR = "minor_diameter"
ID_TOOTH_WIDTH = "tooth_width"
ID_LENGTH = "length"
ID_CHAMFER = "chamfer"
ID_SLOP = "slop"
ID_TARGET = "target_face"
ID_BUILD_MODE = "build_mode"

_SPLINE_TYPES = [
    "Involute (Metric DIN 5480)",
    "Involute (Imperial ANSI B92.1)",
    "Parallel-Side (PTO / SAE J499)",
]
_GENDERS = ["External Shaft", "Internal Hub"]
# New Body builds a standalone spline; Cut into Existing subtractively bores /
# grooves the spline into the body the selected target face belongs to.
_BUILD_MODES = ["New Body", "Cut into Existing"]
_PRESSURE_ANGLES = ["30", "37.5", "45"]
# ANSI B92.1 stub diametral-pitch series (major/minor DP), from the presets.
_DP_SERIES = list(presets.DP_SERIES)
# ANSI side-fit root forms shown in the UI, mapped to the math engine keys.
_ROOT_TYPES = ["Flat root", "Fillet root"]


def _root_type_value(value: str) -> str:
    return "fillet" if value.startswith("Fillet") else "flat"


def _spline_type_index(value: str) -> int:
    if value.startswith("Involute (Imperial"):
        return 1
    if value.startswith("Parallel"):
        return 2
    return 0


def _kind_for_spline_type(value: str) -> str:
    idx = _spline_type_index(value)
    return ("metric", "imperial", "parallel")[idx]


# ---------------------------------------------------------------------------
# Command creation
# ---------------------------------------------------------------------------
class _CommandCreatedHandler(core.CommandCreatedEventHandler):
    def notify(self, args: core.CommandCreatedEventArgs):
        try:
            cmd = core.Command.cast(args.command)
            cmd.isExecutedWhenPreEmpted = False
            global _active_cmd
            _active_cmd = cmd
            inputs = cmd.commandInputs

            # --- dropdowns -------------------------------------------------
            st = inputs.addDropDownCommandInput(
                ID_SPLINE_TYPE, "Spline Standard",
                core.DropDownStyles.TextListDropDownStyle,
            )
            for i, name in enumerate(_SPLINE_TYPES):
                st.listItems.add(name, i == 0)

            gd = inputs.addDropDownCommandInput(
                ID_GENDER, "Gender", core.DropDownStyles.TextListDropDownStyle
            )
            for i, name in enumerate(_GENDERS):
                gd.listItems.add(name, i == 0)

            bm = inputs.addDropDownCommandInput(
                ID_BUILD_MODE, "Build Mode", core.DropDownStyles.TextListDropDownStyle
            )
            for i, name in enumerate(_BUILD_MODES):
                bm.listItems.add(name, i == 0)

            pr = inputs.addDropDownCommandInput(
                ID_PRESET, "Preset", core.DropDownStyles.TextListDropDownStyle
            )
            for i, name in enumerate(presets.preset_names()):
                pr.listItems.add(name, i == 0)

            pa = inputs.addDropDownCommandInput(
                ID_PRESSURE_ANGLE, "Pressure Angle (deg)",
                core.DropDownStyles.TextListDropDownStyle,
            )
            for i, name in enumerate(_PRESSURE_ANGLES):
                pa.listItems.add(name, i == 1)

            # ANSI B92.1 stub diametral-pitch series (imperial involute only).
            dps = inputs.addDropDownCommandInput(
                ID_DP_SERIES, "DP Series (ANSI stub)",
                core.DropDownStyles.TextListDropDownStyle,
            )
            for i, name in enumerate(_DP_SERIES):
                dps.listItems.add(name, i == 1)

            # ANSI side-fit root form (imperial involute only).
            rt = inputs.addDropDownCommandInput(
                ID_ROOT_TYPE, "Root Type (side fit)",
                core.DropDownStyles.TextListDropDownStyle,
            )
            for i, name in enumerate(_ROOT_TYPES):
                rt.listItems.add(name, i == 0)

            # --- numeric inputs ---------------------------------------------
            inputs.addIntegerSpinnerCommandInput(
                ID_TEETH, "Number of Teeth (z)", 4, 120, 1, 14
            )

            # Module (metric involute only; imperial uses the DP Series
            # dropdown). Empty unit string = dimensionless so .value is the raw
            # number (no cm/mm conversion).
            inputs.addValueInput(
                ID_MODULE_OR_DP, "Module (mm)",
                "", core.ValueInput.createByReal(2.0),
            )

            inputs.addValueInput(
                ID_PROFILE_SHIFT, "Profile Shift (x)",
                "", core.ValueInput.createByReal(0.0),
            )

            # Metric centre-distance offset (radial), a linear dimension.
            _add_linear(inputs, ID_CENTER_OFFSET, "Center Distance Offset", 0.0)

            # Linear dimensions: value is in the internal unit (cm).
            _add_linear(inputs, ID_MAJOR, "Major Diameter", 34.9254)
            _add_linear(inputs, ID_MINOR, "Minor Diameter", 29.4132)
            _add_linear(inputs, ID_TOOTH_WIDTH, "Tooth Width", 8.73)
            _add_linear(inputs, ID_LENGTH, "Length", 40.0)
            _add_linear(inputs, ID_CHAMFER, "Lead-in Chamfer", 1.0)

            # Radial fit allowance (interference / clearance).  Positive grows
            # an internal hub and shrinks an external shaft so a mating pair is
            # not an exact line-to-line fit.  Applies to every standard.
            _add_linear(inputs, ID_SLOP, "Slop / Fit Allowance", 0.0)

            # Optional target surface: pick a face (planar end face or a bore /
            # shaft cylinder) or a construction plane to place the spline on.
            # Left empty -> builds on the XY plane about the origin Z axis.
            tgt = inputs.addSelectionInput(
                ID_TARGET, "Target Face (optional)",
                "Select a face or plane to place the spline on (leave empty for XY plane).",
            )
            tgt.setSelectionLimits(0, 1)

            # Events. These are per-dialog: keep them in _cmd_handlers (NOT
            # _handlers) so the destroy handler can release them without
            # dropping the permanent CreatedHandler reference.
            _cmd_handlers.clear()
            on_exec = _CommandExecuteHandler()
            on_change = _CommandInputChangedHandler()
            on_destroy = _CommandDestroyedHandler()
            cmd.execute.add(on_exec)
            cmd.inputChanged.add(on_change)
            cmd.destroy.add(on_destroy)
            _cmd_handlers.extend([on_exec, on_change, on_destroy])

            _apply_visibility(inputs, "metric")
        except Exception:
            if _ui:
                _ui.messageBox("Dialog error:\n" + traceback.format_exc())


def _add_linear(inputs: core.CommandInputs, input_id: str, name: str, default_mm: float):
    """Add a linear value input (mm display) with a millimetre default.

    ``.value`` on a ValueCommandInput is always in internal units (cm), so the
    reader multiplies by 10 to obtain millimetres.
    """
    return inputs.addValueInput(
        input_id, name, "mm",
        core.ValueInput.createByString(f"{default_mm} mm"),
    )


# ---------------------------------------------------------------------------
# Dynamic UI
# ---------------------------------------------------------------------------
def _apply_visibility(inputs: core.CommandInputs, kind: str):
    """Show only the inputs that apply to the active standard.

    Irrelevant fields are hidden (not just greyed) so the dialog never shows
    contradictory parameters -- e.g. an imperial spline no longer displays the
    metric module box, the parallel-side diameters, or the metric centre-distance
    offset at the same time.
    """
    involute = kind in ("metric", "imperial")
    # Module value box is metric-only; imperial DP comes from the series dropdown.
    _show(inputs, ID_MODULE_OR_DP, kind == "metric")
    _show(inputs, ID_DP_SERIES, kind == "imperial")
    _show(inputs, ID_PRESSURE_ANGLE, involute)
    _show(inputs, ID_PROFILE_SHIFT, involute)
    # Flat/fillet root side-fit applies to both involute families
    # (ANSI B92.1 and DIN 5480 a_k / a_f).
    _show(inputs, ID_ROOT_TYPE, involute)
    # Centre-distance offset is a metric (DIN 5480) adjustment.
    _show(inputs, ID_CENTER_OFFSET, kind == "metric")
    # Parallel-side (PTO) rectangular-tooth parameters.
    _show(inputs, ID_MAJOR, kind == "parallel")
    _show(inputs, ID_MINOR, kind == "parallel")
    _show(inputs, ID_TOOTH_WIDTH, kind == "parallel")


def _show(inputs: core.CommandInputs, input_id: str, visible: bool):
    """Toggle an input's visibility and (matching) enabled state."""
    inp = inputs.itemById(input_id)
    if inp is None:
        return
    try:
        inp.isVisible = visible
        inp.isEnabled = visible
    except Exception:
        pass


def _set_linear_mm(inputs: core.CommandInputs, input_id: str, value_mm: float):
    """Set a linear input from a millimetre value (stored internally in cm)."""
    inp = inputs.itemById(input_id)
    if inp is not None:
        try:
            inp.expression = f"{value_mm} mm"
        except Exception:
            inp.value = value_mm / 10.0


def _apply_preset(inputs: core.CommandInputs, preset_name: str):
    """Auto-fill parameters from a preset (manual fields still override)."""
    p = presets.apply_preset(preset_name)
    if p.get("kind") == "custom":
        # Custom: leave every field editable but keep visibility consistent
        # with the currently-selected standard (don't re-show hidden fields).
        kind = _kind_for_spline_type(_dropdown_value(inputs.itemById(ID_SPLINE_TYPE)))
        for inp in inputs:
            try:
                inp.isEnabled = True
            except Exception:
                pass
        _apply_visibility(inputs, kind)
        return

    if "spline_type" in p:
        _select_dropdown(inputs, ID_SPLINE_TYPE, _spline_type_for(p["spline_type"]))
    if "gender" in p:
        _select_dropdown(inputs, ID_GENDER, 1 if p["gender"] == "internal" else 0)
    if "teeth" in p:
        inputs.itemById(ID_TEETH).value = p["teeth"]
    if "module_mm" in p:
        inputs.itemById(ID_MODULE_OR_DP).value = p["module_mm"]
    if "dp_series" in p:
        _select_dropdown(inputs, ID_DP_SERIES, _dp_series_index(p["dp_series"]))
    if "root_type" in p:
        _select_dropdown(inputs, ID_ROOT_TYPE, 1 if p["root_type"] == "fillet" else 0)
    if "pressure_angle_deg" in p:
        _select_dropdown(inputs, ID_PRESSURE_ANGLE,
                         _pressure_angle_index(p["pressure_angle_deg"]))
    if "profile_shift" in p:
        inputs.itemById(ID_PROFILE_SHIFT).value = p["profile_shift"]
    if "major_diameter_mm" in p:
        _set_linear_mm(inputs, ID_MAJOR, p["major_diameter_mm"])
    if "minor_diameter_mm" in p:
        _set_linear_mm(inputs, ID_MINOR, p["minor_diameter_mm"])
    if "tooth_width_mm" in p:
        _set_linear_mm(inputs, ID_TOOTH_WIDTH, p["tooth_width_mm"])
    if "length_mm" in p:
        _set_linear_mm(inputs, ID_LENGTH, p["length_mm"])

    _apply_visibility(inputs, p.get("spline_type", "metric"))


def _spline_type_for(kind: str) -> int:
    return {"metric": 0, "imperial": 1, "parallel": 2}.get(kind, 0)


def _pressure_angle_index(value) -> int:
    target = float(value)
    for i, name in enumerate(_PRESSURE_ANGLES):
        if abs(float(name) - target) < 1e-6:
            return i
    return 0


def _dp_series_index(series: str) -> int:
    for i, name in enumerate(_DP_SERIES):
        if name == series:
            return i
    return 0


def _select_dropdown(inputs: core.CommandInputs, input_id: str, index: int):
    inp = inputs.itemById(input_id)
    if inp is not None and hasattr(inp, "listItems"):
        for i, item in enumerate(inp.listItems):
            item.isSelected = i == index


# ---------------------------------------------------------------------------
# Input-changed handler
# ---------------------------------------------------------------------------
class _CommandInputChangedHandler(core.InputChangedEventHandler):
    def notify(self, args: core.InputChangedEventArgs):
        try:
            changed = args.input
            # InputChangedEventArgs exposes neither .command nor does every
            # CommandInput expose .parent; read the inputs off the command we
            # captured when the dialog was created.
            if _active_cmd is None:
                return
            inputs = _active_cmd.commandInputs
            if changed.id == ID_PRESET:
                name = _dropdown_value(changed)
                _apply_preset(inputs, name)
            elif changed.id == ID_SPLINE_TYPE:
                _apply_visibility(inputs, _kind_for_spline_type(_dropdown_value(changed)))
        except Exception:
            if _ui:
                _ui.messageBox("Input error:\n" + traceback.format_exc())


def _dropdown_value(inp) -> str:
    for item in inp.listItems:
        if item.isSelected:
            return item.name
    return ""


def _selected_target(inputs: core.CommandInputs):
    """Return the entity the user picked in the Target Face input, or None.

    A SelectionCommandInput holds zero or more selections; we allow at most one
    and return its ``entity`` (a BRepFace or ConstructionPlane).
    """
    inp = inputs.itemById(ID_TARGET)
    if inp is None:
        return None
    try:
        if inp.selectionCount > 0:
            return inp.selection(0).entity
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Execute handler
# ---------------------------------------------------------------------------
class _CommandExecuteHandler(core.CommandEventHandler):
    def notify(self, args: core.CommandEventArgs):
        try:
            design = fusion.Design.cast(_app.activeProduct)
            if not design:
                _ui.messageBox("Please open a Fusion 360 design first.")
                return

            inputs = args.command.commandInputs
            params = _collect_params(inputs)

            comp = design.rootComponent
            plane = comp.xYConstructionPlane

            # Optional user-selected target surface (face or plane). When set,
            # the builder places every sketch on it and patterns about its
            # axis; when empty the spline is built on the XY plane.
            target = _selected_target(inputs)

            # Building all features inside the command's execute handler is
            # automatically grouped by Fusion into a single undo transaction.
            builder.build_spline(comp, plane, params, target)
        except Exception:
            if _ui:
                _ui.messageBox("Build error:\n" + traceback.format_exc())


def _collect_params(inputs: core.CommandInputs) -> dict:
    spline_type_val = _dropdown_value(inputs.itemById(ID_SPLINE_TYPE))
    kind = _kind_for_spline_type(spline_type_val)
    gender_val = _dropdown_value(inputs.itemById(ID_GENDER))
    gender = "internal" if gender_val.startswith("Internal") else "external"
    mode_val = _dropdown_value(inputs.itemById(ID_BUILD_MODE))
    build_mode = "cut" if mode_val.startswith("Cut") else "new"

    params = {
        "spline_type": kind,
        "gender": gender,
        "build_mode": build_mode,
        "teeth": int(inputs.itemById(ID_TEETH).value),
        "length_mm": _linear_mm(inputs, ID_LENGTH),
        "chamfer_mm": _linear_mm(inputs, ID_CHAMFER),
        "slop_mm": _linear_mm(inputs, ID_SLOP),
    }

    if kind in ("metric", "imperial"):
        if kind == "metric":
            params["module_mm"] = inputs.itemById(ID_MODULE_OR_DP).value
        else:
            # Imperial: the major diametral pitch comes ONLY from the ANSI stub
            # DP-series dropdown (e.g. "16/32" -> 16). The metric module box is
            # hidden for imperial, so there is a single source of truth.
            series = _dropdown_value(inputs.itemById(ID_DP_SERIES))
            params["dp"] = presets.dp_series_to_major_dp(series)
        params["pressure_angle_deg"] = float(
            _dropdown_value(inputs.itemById(ID_PRESSURE_ANGLE))
        )
        params["profile_shift"] = float(inputs.itemById(ID_PROFILE_SHIFT).value)
        params["root_type"] = _root_type_value(
            _dropdown_value(inputs.itemById(ID_ROOT_TYPE))
        )
        if kind == "metric":
            params["center_distance_offset_mm"] = _linear_mm(inputs, ID_CENTER_OFFSET)
    else:  # parallel
        params["major_diameter_mm"] = _linear_mm(inputs, ID_MAJOR)
        params["minor_diameter_mm"] = _linear_mm(inputs, ID_MINOR)
        params["tooth_width_mm"] = _linear_mm(inputs, ID_TOOTH_WIDTH)

    return params


def _linear_mm(inputs: core.CommandInputs, input_id: str) -> float:
    """Return a linear input's value converted to millimetres.

    Fusion's ``value`` property is always in the document's internal unit
    (centimetres), so multiply by 10 to obtain millimetres regardless of the
    user's display units.
    """
    return inputs.itemById(input_id).value * 10.0


# ---------------------------------------------------------------------------
# Destroyed handler
# ---------------------------------------------------------------------------
class _CommandDestroyedHandler(core.CommandEventHandler):
    def notify(self, args):
        global _active_cmd
        _active_cmd = None
        try:
            args.command.execute.removeNone()
            args.command.inputChanged.removeNone()
            args.command.destroy.removeNone()
        except Exception:
            pass
        # Release ONLY the per-dialog handlers. Never clear _handlers here: it
        # holds the permanent CreatedHandler and clearing it breaks the next use.
        _cmd_handlers.clear()


# ---------------------------------------------------------------------------
# Add-in lifecycle.  Fusion's add-in loader calls run()/stop() (NOT start()).
# ---------------------------------------------------------------------------
def run(context: str):
    global _app, _ui, _ctrl
    _app = core.Application.get()
    _ui = _app.userInterface

    try:
        # Remove any leftover command definition AND toolbar control from a
        # previous (possibly failed) load.  A stale control with the same id
        # makes addCommand raise "InternalValidationError : res".
        panel = _ui.allToolbarPanels.itemById(_panel_id)
        if panel:
            for i in range(panel.controls.count - 1, -1, -1):
                try:
                    if panel.controls.item(i).id == _cmd_def_id:
                        panel.controls.item(i).deleteMe()
                except Exception:
                    pass

        cmd_defs = _ui.commandDefinitions
        existing = cmd_defs.itemById(_cmd_def_id)
        if existing:
            existing.deleteMe()

        cmd_def = cmd_defs.addButtonDefinition(
            _cmd_def_id,
            "Spline Generator",
            "Generate parameter-driven involute / parallel-side splines "
            "(DIN 5480, ANSI B92.1, SAE J499)",
            os.path.join(_addin_dir, "resources", ""),
        )

        on_create = _CommandCreatedHandler()
        cmd_def.commandCreated.add(on_create)
        _handlers.append(on_create)

        if panel:
            _ctrl = panel.controls.addCommand(cmd_def, _reference_cmd, False)
            _ctrl.isPromotedByDefault = True
        return True
    except Exception:
        if _ui:
            _ui.messageBox("Startup error:\n" + traceback.format_exc())
        return False


def stop(context: str):
    """Cleanly remove UI controls and handlers to avoid leaks on restart."""
    global _ctrl, _handlers, _cmd_handlers
    try:
        if _ctrl and _ctrl.isValid:
            _ctrl.deleteMe()
        _ctrl = None

        ui = core.Application.get().userInterface
        cmd_defs = ui.commandDefinitions
        existing = cmd_defs.itemById(_cmd_def_id)
        if existing:
            existing.deleteMe()
        _handlers = []
        _cmd_handlers = []
    except Exception:
        if _ui:
            _ui.messageBox("Stop error:\n" + traceback.format_exc())
