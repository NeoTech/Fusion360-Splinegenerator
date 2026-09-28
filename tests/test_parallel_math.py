"""Smoke tests for core.parallel_math (pure, no Fusion required)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import parallel_math as pm  # noqa: E402
from tests.geom_util import (  # noqa: E402
    is_simple_polygon,
    max_radius,
    min_radius,
)


class TestRadii(unittest.TestCase):
    def test_basic(self):
        g = pm.compute_radii(34.9254, 29.4132, 6)
        self.assertAlmostEqual(g["major_radius"], 34.9254 / 2.0, places=6)
        self.assertAlmostEqual(g["minor_radius"], 29.4132 / 2.0, places=6)

    def test_invalid_diameters(self):
        with self.assertRaises(ValueError):
            pm.compute_radii(20.0, 30.0, 6)

    def test_min_teeth(self):
        with self.assertRaises(ValueError):
            pm.compute_radii(30.0, 20.0, 1)


class TestExternalProfile(unittest.TestCase):
    def test_simple_polygon(self):
        prof = pm.external_tooth_profile(34.9254, 29.4132, 6)
        self.assertTrue(is_simple_polygon(prof))

    def test_four_vertices(self):
        prof = pm.external_tooth_profile(34.9254, 29.4132, 6)
        self.assertEqual(len(prof), 4)

    def test_radius_bounds(self):
        prof = pm.external_tooth_profile(44.45, 40.487, 20)
        self.assertAlmostEqual(max_radius(prof), 44.45 / 2.0, places=3)
        self.assertAlmostEqual(min_radius(prof), 40.487 / 2.0, places=3)

    def test_with_tooth_width(self):
        prof = pm.external_tooth_profile(34.9254, 29.4132, 6, tooth_width_mm=8.73)
        self.assertTrue(is_simple_polygon(prof))

    def test_varied_no_self_intersection(self):
        for z in (6, 10, 20, 21):
            prof = pm.external_tooth_profile(34.9254, 29.4132, z)
            self.assertTrue(is_simple_polygon(prof), f"z={z}")


class TestInternalProfile(unittest.TestCase):
    def test_simple_polygon(self):
        prof = pm.internal_space_profile(34.9254, 29.4132, 6)
        self.assertTrue(is_simple_polygon(prof))


class TestInchToMm(unittest.TestCase):
    def test_conversion(self):
        self.assertAlmostEqual(pm.inch_to_mm(1.0), 25.4, places=9)


if __name__ == "__main__":
    unittest.main()
