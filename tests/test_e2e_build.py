"""End-to-end smoke test: parameters -> full spline body via cad.builder.

Runs the complete orchestration (math -> sketch -> extrude -> pattern ->
chamfer) against the fake adsk API and asserts the right features were
created with the right parameters.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests import adsk_stub  # noqa: E402

adsk_stub.install()

import adsk.core as core  # noqa: E402
from cad import builder  # noqa: E402
from core import presets  # noqa: E402


def _new_component():
    core.Application.reset()
    design = core.Application.get().ActiveProduct.designs[0]
    return design.activeComponent, design.origin.xyPlane


def _feature_kinds(comp):
    return [k for (k, _f) in comp.features_log]


class TestBuildMetricExternal(unittest.TestCase):
    def setUp(self):
        self.comp, self.plane = _new_component()
        self.pattern = builder.build_spline(
            self.comp,
            self.plane,
            {
                "spline_type": "metric",
                "gender": "external",
                "teeth": 14,
                "module_mm": 2.0,
                "pressure_angle_deg": 30.0,
                "profile_shift": 0.0,
                "length_mm": 40.0,
                "chamfer_mm": 1.0,
            },
        )

    def test_feature_sequence(self):
        kinds = _feature_kinds(self.comp)
        # base blank extrude, tooth extrude, pattern, join-combine, chamfer
        self.assertEqual(
            kinds,
            ["extrude", "extrude", "circular_pattern", "combine", "chamfer"],
        )

    def test_pattern_count_matches_teeth(self):
        self.assertEqual(self.pattern.count, 14)

    def test_extrude_length(self):
        extrude = self.comp.features_log[1][1]
        self.assertAlmostEqual(extrude.distance, 4.0, places=9)  # 40mm -> 4cm

    def test_extrude_is_boss(self):
        import adsk.fusion as fusion
        extrude = self.comp.features_log[1][1]
        self.assertEqual(
            extrude.operation, fusion.FeatureOperations.NewBodyFeatureOperation
        )

    def test_sketch_has_arcs_and_circles(self):
        # Involute teeth are drawn as 3-point arcs (one per flank) plus a
        # straight root line, so expect arcs and no fitted splines.
        sk = self.comp.sketches_list[-1]
        self.assertEqual(len(sk.sketchCurves.sketchFittedSplines.created), 0)
        self.assertGreater(len(sk.sketchCurves.sketchArcs.created), 0)
        self.assertGreater(len(sk.sketchCurves.sketchLines.created), 0)
        self.assertEqual(len(sk.sketchCurves.sketchCircles.created), 4)


class TestBuildInternalCut(unittest.TestCase):
    def test_uses_cut_type(self):
        comp, plane = _new_component()
        builder.build_spline(
            comp,
            plane,
            {
                "spline_type": "metric",
                "gender": "internal",
                "teeth": 18,
                "module_mm": 2.0,
                "pressure_angle_deg": 30.0,
                "length_mm": 30.0,
                "chamfer_mm": 0.0,
            },
        )
        import adsk.fusion as fusion
        # base blank, bore cut, space cut, pattern
        kinds = _feature_kinds(comp)
        self.assertEqual(
            kinds, ["extrude", "extrude", "extrude", "circular_pattern"]
        )
        space_cut = comp.features_log[2][1]
        self.assertEqual(
            space_cut.operation, fusion.FeatureOperations.CutFeatureOperation
        )
        # chamfer disabled
        self.assertNotIn("chamfer", kinds)


class TestBuildParallel(unittest.TestCase):
    def test_parallel_uses_polyline(self):
        comp, plane = _new_component()
        builder.build_spline(
            comp,
            plane,
            {
                "spline_type": "parallel",
                "gender": "external",
                "teeth": 6,
                "major_diameter_mm": 34.9254,
                "minor_diameter_mm": 29.4132,
                "tooth_width_mm": 8.73,
                "length_mm": 60.0,
                "chamfer_mm": 1.5,
            },
        )
        sk = comp.sketches_list[-1]
        # parallel teeth are straight-sided -> lines, not a fitted spline
        self.assertEqual(len(sk.sketchCurves.sketchFittedSplines.created), 0)
        self.assertEqual(len(sk.sketchCurves.sketchLines.created), 4)
        self.assertEqual(
            _feature_kinds(comp),
            ["extrude", "extrude", "circular_pattern", "combine", "chamfer"],
        )


class TestBuildImperial(unittest.TestCase):
    def test_dp_converted_to_module(self):
        comp, plane = _new_component()
        builder.build_spline(
            comp,
            plane,
            {
                "spline_type": "imperial",
                "gender": "external",
                "teeth": 30,
                "dp": 16.0,
                "pressure_angle_deg": 30.0,
                "length_mm": 40.0,
                "chamfer_mm": 0.0,
            },
        )
        self.assertEqual(
            _feature_kinds(comp),
            ["extrude", "extrude", "circular_pattern", "combine"],
        )
        self.assertEqual(comp.features_log[2][1].count, 30)


class TestBuildAllPresets(unittest.TestCase):
    def test_every_non_custom_preset_builds(self):
        for name, p in presets.PRESETS.items():
            if p.get("kind") == "custom":
                continue
            comp, plane = _new_component()
            params = dict(p)
            params.setdefault("chamfer_mm", 0.0)
            params.setdefault("length_mm", 40.0)
            feature = builder.build_spline(comp, plane, params)
            self.assertIsNotNone(feature, name)
            self.assertIn("circular_pattern", _feature_kinds(comp), name)


class TestBuildErrors(unittest.TestCase):
    def test_unknown_type_raises(self):
        comp, plane = _new_component()
        with self.assertRaises(ValueError):
            builder.build_spline(
                comp, plane, {"spline_type": "bogus", "teeth": 10, "length_mm": 10}
            )


if __name__ == "__main__":
    unittest.main()
