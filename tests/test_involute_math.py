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

    def test_explicit_diameter_override(self):
        # Reduced-depth N-series: explicit da/df override the formula radii.
        g = im.compute_radii(2.0, 18, 30.0, internal=False,
                             major_diameter_mm=39.60, root_diameter_mm=35.20)
        self.assertAlmostEqual(g["major_diameter"], 39.60, places=6)
        self.assertAlmostEqual(g["root_diameter"], 35.20, places=6)
        # Pitch / base circles are unaffected by the override.
        self.assertAlmostEqual(g["pitch_diameter"], 36.0, places=6)

    def test_override_none_keeps_formula(self):
        a = im.compute_radii(2.0, 18, 30.0)
        b = im.compute_radii(2.0, 18, 30.0, major_diameter_mm=None,
                             root_diameter_mm=None)
        self.assertAlmostEqual(a["major_diameter"], b["major_diameter"], places=9)
        self.assertAlmostEqual(a["root_diameter"], b["root_diameter"], places=9)

    def test_profile_shift_grows_teeth(self):
        base = im.compute_radii(2.0, 20, 30.0, profile_shift=0.0)
        shifted = im.compute_radii(2.0, 20, 30.0, profile_shift=0.5)
        self.assertGreater(shifted["major_radius"], base["major_radius"])

    def test_slop_grows_internal_shrinks_external(self):
        # Positive slop enlarges a hub and shrinks a shaft (radially), giving
        # clearance so a mating pair is not a line-to-line fit.
        ext0 = im.compute_radii(2.0, 20, 30.0, internal=False, slop_mm=0.0)
        ext = im.compute_radii(2.0, 20, 30.0, internal=False, slop_mm=0.2)
        int0 = im.compute_radii(2.0, 20, 30.0, internal=True, slop_mm=0.0)
        int_ = im.compute_radii(2.0, 20, 30.0, internal=True, slop_mm=0.2)
        # The tip/root lands move by HALF the slop (they are not the fit
        # surfaces), so the tooth closes up at top and bottom.
        self.assertAlmostEqual(ext["major_radius"], ext0["major_radius"] - 0.1, places=6)
        self.assertAlmostEqual(ext["root_radius"], ext0["root_radius"] - 0.1, places=6)
        self.assertAlmostEqual(int_["major_radius"], int0["major_radius"] + 0.1, places=6)
        self.assertAlmostEqual(int_["root_radius"], int0["root_radius"] + 0.1, places=6)
        # The base circle (which anchors the involute flank arcs) carries the
        # FULL slop -- the flanks are the mating surfaces.
        self.assertAlmostEqual(ext["base_radius"], ext0["base_radius"] - 0.2, places=6)
        self.assertAlmostEqual(int_["base_radius"], int0["base_radius"] + 0.2, places=6)

    def test_slop_moves_flank_arcs_not_just_lands(self):
        # A flank point (an arc vertex, not a land) must move radially with slop.
        e0 = im.external_tooth_edges(2.0, 20, 30.0, slop_mm=0.0)
        e1 = im.external_tooth_edges(2.0, 20, 30.0, slop_mm=0.5)
        # First edge is the flank arc; its start point sits on the root circle,
        # which moves by half the slop (the lands close up to slop/2).
        p0, p1 = e0[0][1], e1[0][1]
        r0 = math.hypot(*p0)
        r1 = math.hypot(*p1)
        self.assertAlmostEqual(r1, r0 - 0.25, places=6)
        # And the flank's angular position changes (the arc itself moved), not
        # just its radius -- proving the involute was regenerated from the
        # shifted base circle.
        a0 = math.atan2(p0[1], p0[0])
        a1 = math.atan2(p1[1], p1[0])
        self.assertNotAlmostEqual(a0, a1, places=6)

    def test_slop_zero_is_default(self):
        a = im.compute_radii(2.0, 20, 30.0, internal=True)
        b = im.compute_radii(2.0, 20, 30.0, internal=True, slop_mm=0.0)
        self.assertAlmostEqual(a["major_radius"], b["major_radius"], places=9)

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
