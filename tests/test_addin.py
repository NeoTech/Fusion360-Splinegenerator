"""Smoke tests for the add-in entry point's UI / parameter logic.

Imports ``Fusion360-Splinegenerator`` against the fake adsk API and exercises
the pure helper functions (no command dialog needed): standard detection,
preset auto-fill, input visibility, and parameter collection.
"""

from __future__ import annotations

import importlib
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests import adsk_stub  # noqa: E402

adsk_stub.install()

import adsk.core as core  # noqa: E402

addin = importlib.import_module("Fusion360-Splinegenerator")


def _fresh_inputs():
    inputs = core.CommandInputs()
    st = inputs.addDropDownCommandInput(addin.ID_SPLINE_TYPE)
    for i, name in enumerate(addin._SPLINE_TYPES):
        st.listItems.add(name, i == 0)
    gd = inputs.addDropDownCommandInput(addin.ID_GENDER)
    for i, name in enumerate(addin._GENDERS):
        gd.listItems.add(name, i == 0)
    bm = inputs.addDropDownCommandInput(addin.ID_BUILD_MODE)
    for i, name in enumerate(addin._BUILD_MODES):
        bm.listItems.add(name, i == 0)
    pr = inputs.addDropDownCommandInput(addin.ID_PRESET)
    for i, name in enumerate(addin.presets.preset_names()):
        pr.listItems.add(name, i == 0)
    pa = inputs.addDropDownCommandInput(addin.ID_PRESSURE_ANGLE)
    for i, name in enumerate(addin._PRESSURE_ANGLES):
        pa.listItems.add(name, i == 1)
    dps = inputs.addDropDownCommandInput(addin.ID_DP_SERIES)
    for i, name in enumerate(addin._DP_SERIES):
        dps.listItems.add(name, i == 1)
    rt = inputs.addDropDownCommandInput(addin.ID_ROOT_TYPE)
    for i, name in enumerate(addin._ROOT_TYPES):
        rt.listItems.add(name, i == 0)
    inputs.addIntegerSpinnerCommandInput(addin.ID_TEETH, "z", 4, 120, 1, 14)
    # Dimensionless value inputs: raw number via createByReal.
    inputs.addValueInput(addin.ID_MODULE_OR_DP, "m", "", core.ValueInput.createByReal(2.0))
    inputs.addValueInput(addin.ID_PROFILE_SHIFT, "x", "", core.ValueInput.createByReal(0.0))
    # Linear: value stored in cm (mm expression parsed by the stub).
    for pid, mm in [
        (addin.ID_CENTER_OFFSET, 0.0),
        (addin.ID_MAJOR, 34.9254),
        (addin.ID_MINOR, 29.4132),
        (addin.ID_TOOTH_WIDTH, 8.73),
        (addin.ID_LENGTH, 40.0),
        (addin.ID_CHAMFER, 1.0),
    ]:
        inputs.addValueInput(pid, pid, "mm", core.ValueInput.createByString(f"{mm} mm"))
    return inputs


class TestStandardDetection(unittest.TestCase):
    def test_spline_type_index(self):
        self.assertEqual(addin._spline_type_index(_addin_name(0)), 0)
        self.assertEqual(addin._spline_type_index(_addin_name(1)), 1)
        self.assertEqual(addin._spline_type_index(_addin_name(2)), 2)

    def test_kind_for_spline_type(self):
        self.assertEqual(addin._kind_for_spline_type(_addin_name(0)), "metric")
        self.assertEqual(addin._kind_for_spline_type(_addin_name(1)), "imperial")
        self.assertEqual(addin._kind_for_spline_type(_addin_name(2)), "parallel")


def _addin_name(i):
    return addin._SPLINE_TYPES[i]


class TestVisibility(unittest.TestCase):
    def test_metric_shows_module_hides_diameters(self):
        inputs = _fresh_inputs()
        addin._apply_visibility(inputs, "metric")
        self.assertTrue(inputs.itemById(addin.ID_MODULE_OR_DP).isVisible)
        self.assertFalse(inputs.itemById(addin.ID_MAJOR).isVisible)
        self.assertFalse(inputs.itemById(addin.ID_MINOR).isVisible)

    def test_parallel_shows_diameters_hides_module(self):
        inputs = _fresh_inputs()
        addin._apply_visibility(inputs, "parallel")
        self.assertFalse(inputs.itemById(addin.ID_MODULE_OR_DP).isVisible)
        self.assertTrue(inputs.itemById(addin.ID_MAJOR).isVisible)
        self.assertTrue(inputs.itemById(addin.ID_MINOR).isVisible)


class TestPresetApply(unittest.TestCase):
    def test_pto_preset_fills_teeth_and_diameters(self):
        inputs = _fresh_inputs()
        name = 'Tractor PTO 1-3/8" 6T (540 RPM)'
        addin._apply_preset(inputs, name)
        self.assertEqual(inputs.itemById(addin.ID_TEETH).value, 6)
        # Linear inputs store cm internally; round-trip through _linear_mm.
        self.assertAlmostEqual(
            addin._linear_mm(inputs, addin.ID_MAJOR), 34.9254, places=4
        )
        # parallel -> module hidden, diameters visible
        self.assertFalse(inputs.itemById(addin.ID_MODULE_OR_DP).isVisible)
        self.assertTrue(inputs.itemById(addin.ID_MAJOR).isVisible)

    def test_din_preset_fills_module(self):
        inputs = _fresh_inputs()
        addin._apply_preset(inputs, "DIN 5480 W30x2x14")
        self.assertEqual(inputs.itemById(addin.ID_TEETH).value, 14)
        self.assertAlmostEqual(inputs.itemById(addin.ID_MODULE_OR_DP).value, 2.0, places=6)
        self.assertTrue(inputs.itemById(addin.ID_MODULE_OR_DP).isVisible)

    def test_custom_keeps_relevant_fields_visible(self):
        # Custom with metric standard selected: editable, but parallel-only
        # fields stay hidden (no contradictory parameters shown).
        inputs = _fresh_inputs()
        addin._apply_visibility(inputs, "metric")
        addin._apply_preset(inputs, "Custom")
        self.assertTrue(inputs.itemById(addin.ID_MODULE_OR_DP).isEnabled)
        self.assertFalse(inputs.itemById(addin.ID_MAJOR).isVisible)


class TestCollectParams(unittest.TestCase):
    def test_metric_external(self):
        inputs = _fresh_inputs()
        params = addin._collect_params(inputs)
        self.assertEqual(params["spline_type"], "metric")
        self.assertEqual(params["gender"], "external")
        self.assertEqual(params["teeth"], 14)
        self.assertAlmostEqual(params["module_mm"], 2.0, places=6)
        self.assertEqual(params["pressure_angle_deg"], 37.5)
        # length default 40 mm stored as 4 cm internally -> *10 = 40 mm
        self.assertAlmostEqual(params["length_mm"], 40.0, places=6)

    def test_parallel_via_dropdown(self):
        inputs = _fresh_inputs()
        addin._select_dropdown(inputs, addin.ID_SPLINE_TYPE, 2)
        params = addin._collect_params(inputs)
        self.assertEqual(params["spline_type"], "parallel")
        self.assertIn("major_diameter_mm", params)
        self.assertIn("tooth_width_mm", params)

    def test_internal_gender(self):
        inputs = _fresh_inputs()
        addin._select_dropdown(inputs, addin.ID_GENDER, 1)
        params = addin._collect_params(inputs)
        self.assertEqual(params["gender"], "internal")

    def test_imperial_dp_from_series(self):
        inputs = _fresh_inputs()
        addin._select_dropdown(inputs, addin.ID_SPLINE_TYPE, 1)
        # "24/48" series -> major DP 24.
        addin._select_dropdown(inputs, addin.ID_DP_SERIES, 2)
        params = addin._collect_params(inputs)
        self.assertEqual(params["spline_type"], "imperial")
        self.assertAlmostEqual(params["dp"], 24.0, places=6)
        self.assertEqual(params["root_type"], "flat")

    def test_imperial_fillet_root(self):
        inputs = _fresh_inputs()
        addin._select_dropdown(inputs, addin.ID_SPLINE_TYPE, 1)
        addin._select_dropdown(inputs, addin.ID_ROOT_TYPE, 1)
        params = addin._collect_params(inputs)
        self.assertEqual(params["root_type"], "fillet")

    def test_metric_center_offset(self):
        inputs = _fresh_inputs()
        addin._set_linear_mm(inputs, addin.ID_CENTER_OFFSET, 0.5)
        params = addin._collect_params(inputs)
        self.assertAlmostEqual(params["center_distance_offset_mm"], 0.5, places=6)


class TestVisibilityNew(unittest.TestCase):
    def test_imperial_shows_dp_series_hides_center_offset(self):
        inputs = _fresh_inputs()
        addin._apply_visibility(inputs, "imperial")
        self.assertTrue(inputs.itemById(addin.ID_DP_SERIES).isVisible)
        self.assertTrue(inputs.itemById(addin.ID_ROOT_TYPE).isVisible)
        self.assertFalse(inputs.itemById(addin.ID_CENTER_OFFSET).isVisible)
        # module value input is metric-only now.
        self.assertFalse(inputs.itemById(addin.ID_MODULE_OR_DP).isVisible)
        # parallel-side diameters must not show for imperial.
        self.assertFalse(inputs.itemById(addin.ID_MAJOR).isVisible)

    def test_metric_shows_center_offset_hides_dp_series(self):
        inputs = _fresh_inputs()
        addin._apply_visibility(inputs, "metric")
        self.assertTrue(inputs.itemById(addin.ID_CENTER_OFFSET).isVisible)
        self.assertFalse(inputs.itemById(addin.ID_DP_SERIES).isVisible)
        self.assertTrue(inputs.itemById(addin.ID_MODULE_OR_DP).isVisible)


class TestPresetApplyNew(unittest.TestCase):
    def test_imperial_fillet_preset_sets_series_and_root(self):
        inputs = _fresh_inputs()
        name = "ANSI B92.1 16/32 DP 30T 30deg (Fillet)"
        addin._apply_preset(inputs, name)
        self.assertEqual(addin._dropdown_value(inputs.itemById(addin.ID_DP_SERIES)), "16/32")
        self.assertEqual(addin._dropdown_value(inputs.itemById(addin.ID_ROOT_TYPE)), "Fillet root")

    def test_dp_series_index(self):
        self.assertEqual(addin._dp_series_index("16/32"), 1)
        self.assertEqual(addin._dp_series_index("nope"), 0)

    def test_root_type_value(self):
        self.assertEqual(addin._root_type_value("Fillet root"), "fillet")
        self.assertEqual(addin._root_type_value("Flat root"), "flat")


class TestLifecycle(unittest.TestCase):
    def test_stop_is_safe_without_start(self):
        # stop() must not raise even if the command was never created.
        addin.stop("test")


if __name__ == "__main__":
    unittest.main()
