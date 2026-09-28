"""Smoke tests for the CAD layer using the fake adsk API (tests.adsk_stub)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests import adsk_stub  # noqa: E402

adsk_stub.install()  # must run before importing cad.*

import adsk.core as core  # noqa: E402
from cad import sketch_builder, feature_builder  # noqa: E402


def _new_component():
    core.Application.reset()
    design = core.Application.get().ActiveProduct.designs[0]
    return design.activeComponent, design.origin.xyPlane


class TestSketchBuilder(unittest.TestCase):
    def test_add_circle_converts_mm_to_cm(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        c = sketch_builder.add_circle(sk, 20.0)  # 20 mm
        self.assertAlmostEqual(c.radius, 2.0, places=9)  # 2 cm

    def test_closed_spline_records_points(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        pts = [(10.0, 0.0), (5.0, 5.0), (0.0, 10.0)]
        sp = sketch_builder.add_closed_spline(sk, pts, closed=True)
        self.assertTrue(sp.isClosed)
        self.assertEqual(len(sp.points), 3)
        # First point converted to cm.
        self.assertAlmostEqual(sp.points[0].x, 1.0, places=9)

    def test_polyline_closes(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        pts = [(10.0, 0.0), (0.0, 10.0), (-10.0, 0.0)]
        lines = sketch_builder.add_closed_polyline(sk, pts)
        self.assertEqual(len(lines), 3)  # n edges for n vertices (closed)

    def test_reference_circles_count(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        cs = sketch_builder.build_reference_circles(sk, [5.0, 10.0, 15.0])
        self.assertEqual(len(cs), 3)


class TestFeatureBuilder(unittest.TestCase):
    def test_extrude_boss_uses_new_body(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        profile = sk.profiles.item(0)
        f = feature_builder.extrude_profile(profile, 40.0, cut=False)
        self.assertEqual(
            f.operation,
            feature_builder.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        self.assertAlmostEqual(f.distance, 4.0, places=9)  # 40mm -> 4cm

    def test_extrude_cut_uses_cut_type(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        profile = sk.profiles.item(0)
        f = feature_builder.extrude_profile(profile, 40.0, cut=True)
        self.assertEqual(
            f.operation,
            feature_builder.fusion.FeatureOperations.CutFeatureOperation,
        )

    def test_circular_pattern_count(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        profile = sk.profiles.item(0)
        extrude = feature_builder.extrude_profile(profile, 40.0)
        pat = feature_builder.circular_pattern(
            extrude, 14, feature_builder.z_axis(comp)
        )
        self.assertEqual(pat.count, 14)

    def test_collect_end_faces(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        profile = sk.profiles.item(0)
        feature_builder.extrude_profile(profile, 40.0)
        body = comp.bodies.item(0)
        faces = feature_builder.collect_end_faces(body, 40.0)
        self.assertEqual(len(faces), 1)  # only the far end face at z=4cm

    def test_chamfer_faces(self):
        comp, plane = _new_component()
        sk = sketch_builder.find_or_create_sketch_on(comp, plane)
        profile = sk.profiles.item(0)
        feature_builder.extrude_profile(profile, 40.0)
        body = comp.bodies.item(0)
        faces = feature_builder.collect_end_faces(body, 40.0)
        ch = feature_builder.chamfer_faces(comp, faces, 1.0)
        self.assertAlmostEqual(ch.distance1, 0.1, places=9)  # 1mm -> 0.1cm

    def test_chamfer_no_faces_returns_none(self):
        comp, plane = _new_component()
        self.assertIsNone(feature_builder.chamfer_faces(comp, [], 1.0))


if __name__ == "__main__":
    unittest.main()
