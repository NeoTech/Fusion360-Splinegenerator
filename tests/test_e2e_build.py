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


def _params(gender="external"):
    return {
        "spline_type": "metric",
        "gender": gender,
        "teeth": 14,
        "module_mm": 2.0,
        "pressure_angle_deg": 30.0,
        "profile_shift": 0.0,
        "length_mm": 40.0,
        "chamfer_mm": 0.0,
    }


def _pattern_feature(comp):
    for kind, feat in comp.features_log:
        if kind == "circular_pattern":
            return feat
    return None


class TestTargetFacePlacement(unittest.TestCase):
    """The optional ``target`` argument places sketches on a chosen surface and
    patterns about its axis instead of the XY plane / origin Z."""

    def test_no_target_uses_xy_plane_and_origin_z(self):
        comp, plane = _new_component()
        builder.build_spline(comp, plane, _params())
        # Every sketch sits on the supplied XY plane.
        for sk in comp.sketches_list:
            self.assertIs(sk.plane, plane)
        # Pattern runs about the origin Z axis.
        self.assertIs(_pattern_feature(comp).axis, comp.zConstructionAxis)
        # No construction geometry was derived.
        self.assertEqual(comp.construction_axes_log, [])
        self.assertEqual(comp.construction_planes_log, [])

    def test_cylindrical_target_uses_perp_plane_and_cylinder_axis(self):
        comp, plane = _new_component()
        bore = adsk_stub._Face(
            0.0, 40.0, geometry=adsk_stub._CylindricalGeometry(axis=(0.0, 0.0, 1.0))
        )
        builder.build_spline(comp, plane, _params("internal"), target=bore)
        # A perpendicular construction plane was created and used for sketches.
        self.assertEqual(len(comp.construction_planes_log), 1)
        derived_plane = comp.construction_planes_log[0][2]
        for sk in comp.sketches_list:
            self.assertIs(sk.plane, derived_plane)
        # A construction axis from the circular face drives the pattern.
        self.assertEqual(len(comp.construction_axes_log), 1)
        derived_axis = comp.construction_axes_log[0][2]
        self.assertIs(_pattern_feature(comp).axis, derived_axis)
        self.assertIsNot(_pattern_feature(comp).axis, comp.zConstructionAxis)

    def test_planar_target_with_circular_edge_uses_face_and_normal_axis(self):
        comp, plane = _new_component()
        end_face = adsk_stub._Face(
            40.0,
            40.0,
            geometry=adsk_stub._PlanarGeometry(normal=(0.0, 0.0, 1.0)),
            edges=[adsk_stub._Edge("circle")],
        )
        builder.build_spline(comp, plane, _params("external"), target=end_face)
        # A coincident construction plane is created and used for sketches so
        # the face's projected outline never pollutes the profile list.
        self.assertEqual(len(comp.construction_planes_log), 1)
        self.assertEqual(comp.construction_planes_log[0][0], "offset")
        derived_plane = comp.construction_planes_log[0][2]
        for sk in comp.sketches_list:
            self.assertIs(sk.plane, derived_plane)
            self.assertIsNot(sk.plane, end_face)
        # Pattern axis is a derived normal-to-face axis.
        self.assertEqual(len(comp.construction_axes_log), 1)
        derived_axis = comp.construction_axes_log[0][2]
        self.assertIs(_pattern_feature(comp).axis, derived_axis)

    def test_planar_target_without_edge_falls_back_to_origin_z(self):
        comp, plane = _new_component()
        face = adsk_stub._Face(
            40.0,
            40.0,
            geometry=adsk_stub._PlanarGeometry(normal=(0.0, 0.0, 1.0)),
            edges=[],  # no circular edge to anchor a normal axis
        )
        builder.build_spline(comp, plane, _params("external"), target=face)
        # Still sketched on a coincident plane, not the raw face.
        derived_plane = comp.construction_planes_log[0][2]
        for sk in comp.sketches_list:
            self.assertIs(sk.plane, derived_plane)
            self.assertIsNot(sk.plane, face)
        # No circular edge -> pattern axis falls back to origin Z.
        self.assertIs(_pattern_feature(comp).axis, comp.zConstructionAxis)

    def test_construction_plane_target_sketches_on_it_origin_z(self):
        comp, plane = _new_component()
        offset = adsk_stub._Plane("OFFSET")  # no .geometry -> treated as a plane
        builder.build_spline(comp, plane, _params("external"), target=offset)
        for sk in comp.sketches_list:
            self.assertIs(sk.plane, offset)
        self.assertIs(_pattern_feature(comp).axis, comp.zConstructionAxis)


if __name__ == "__main__":
    unittest.main()
