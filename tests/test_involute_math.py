"""Smoke tests for core.involute_math (pure, no Fusion required)."""

from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import involute_math as im  # noqa: E402
from tests.geom_util import (  # noqa: E402
    is_simple_polygon,
    max_radius,
    min_radius,
)


class TestRadii(unittest.TestCase):
    def test_basic_metric(self):
        g = im.compute_radii(module_mm=2.0, teeth=14, pressure_angle_deg=30.0)
        self.assertAlmostEqual(g["pitch_diameter"], 28.0, places=6)
        self.assertAlmostEqual(
            g["base_radius"], g["pitch_radius"] * math.cos(math.radians(30)), places=6
        )
        self.assertLess(g["base_radius"], g["pitch_radius"])
        self.assertLess(g["root_radius"], g["major_radius"])

    def test_internal_inverts_major_root(self):
        ext = im.compute_radii(2.0, 14, 30.0, internal=False)
        int_ = im.compute_radii(2.0, 14, 30.0, internal=True)
        # For an internal spline the hub crest radius is smaller than the root.
        self.assertLess(int_["root_radius"], int_["major_radius"])
        self.assertGreater(int_["major_radius"], ext["pitch_radius"])

    def test_profile_shift_grows_teeth(self):
        base = im.compute_radii(2.0, 20, 30.0, profile_shift=0.0)
        shifted = im.compute_radii(2.0, 20, 30.0, profile_shift=0.5)
        self.assertGreater(shifted["major_radius"], base["major_radius"])

    def test_min_teeth_guard(self):
        with self.assertRaises(ValueError):
            im.compute_radii(2.0, 1, 30.0)


class TestInvoluteFunction(unittest.TestCase):
    def test_zero(self):
        self.assertAlmostEqual(im.involute_func(0.0), 0.0, places=12)

    def test_known(self):
        a = math.radians(30)
        self.assertAlmostEqual(
            im.involute_func(a), math.tan(a) - a, places=12
        )


class TestFlankPoints(unittest.TestCase):
    def test_monotonic_radius(self):
        pts = im.involute_flank_points(
            r_start=11.5, r_end=16.0, r_base=12.12, psi_p=0.11, alpha_rad=math.radians(30)
        )
        radii = [math.hypot(x, y) for (x, y) in pts]
        for a, b in zip(radii, radii[1:]):
            self.assertLessEqual(a - 1e-9, b)

    def test_all_within_bounds(self):
        pts = im.involute_flank_points(11.5, 16.0, 12.12, 0.11, math.radians(30))
        self.assertGreaterEqual(min_radius(pts), 11.5 - 1e-6)
        self.assertLessEqual(max_radius(pts), 16.0 + 1e-6)


class TestExternalToothProfile(unittest.TestCase):
    def test_simple_polygon(self):
        prof = im.external_tooth_profile(2.0, 14, 30.0)
        self.assertTrue(is_simple_polygon(prof), "tooth profile self-intersects")

    def test_radius_bounds(self):
        g = im.compute_radii(2.0, 14, 30.0)
        prof = im.external_tooth_profile(2.0, 14, 30.0)
        self.assertAlmostEqual(max_radius(prof), g["major_radius"], places=3)
        self.assertAlmostEqual(min_radius(prof), g["root_radius"], places=3)

    def test_symmetric_about_x(self):
        prof = im.external_tooth_profile(2.0, 16, 30.0)
        ys = sorted(round(y, 6) for (_x, y) in prof)
        # For every +y there should be a matching -y.
        for y in ys:
            self.assertIn(-y, ys)

    def test_varied_configs_no_self_intersection(self):
        for z in (6, 12, 20, 30, 45):
            for pa in (30.0, 37.5, 45.0):
                for x in (-0.5, 0.0, 0.5):
                    prof = im.external_tooth_profile(2.0, z, pa, x)
                    self.assertTrue(
                        is_simple_polygon(prof),
                        f"self-intersect z={z} pa={pa} x={x}",
                    )


class TestInternalSpaceProfile(unittest.TestCase):
    def test_simple_polygon(self):
        prof = im.internal_space_profile(2.0, 14, 30.0)
        self.assertTrue(is_simple_polygon(prof))


class TestImperial(unittest.TestCase):
    def test_dp_to_module(self):
        self.assertAlmostEqual(im.diametral_pitch_to_module(16.0), 25.4 / 16.0, places=9)

    def test_dp_invalid(self):
        with self.assertRaises(ValueError):
            im.diametral_pitch_to_module(0.0)


if __name__ == "__main__":
    unittest.main()
