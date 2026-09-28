"""Smoke tests for core.presets lookup tables."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import presets  # noqa: E402


class TestPresets(unittest.TestCase):
    def test_names_nonempty(self):
        self.assertTrue(len(presets.preset_names()) > 1)

    def test_custom_present(self):
        self.assertIn("Custom", presets.preset_names())

    def test_apply_custom(self):
        self.assertEqual(presets.apply_preset("Custom"), {"kind": "custom"})

    def test_apply_unknown(self):
        self.assertEqual(presets.apply_preset("does not exist"), {"kind": "custom"})

    def test_parallel_presets_have_diameters(self):
        for name, p in presets.PRESETS.items():
            if p.get("kind") == "parallel":
                self.assertIn("major_diameter_mm", p, name)
                self.assertIn("minor_diameter_mm", p, name)
                self.assertGreater(
                    p["major_diameter_mm"], p["minor_diameter_mm"], name
                )

    def test_involute_presets_have_module_or_dp(self):
        for name, p in presets.PRESETS.items():
            if p.get("kind") == "involute":
                self.assertTrue(
                    "module_mm" in p or "dp" in p, f"{name} missing module/dp"
                )
                self.assertIn("teeth", p, name)
                self.assertIn("pressure_angle_deg", p, name)

    def test_returns_copy(self):
        a = presets.apply_preset("DIN 5480 W30x2x14")
        a["teeth"] = 999
        b = presets.apply_preset("DIN 5480 W30x2x14")
        self.assertNotEqual(b["teeth"], 999)


if __name__ == "__main__":
    unittest.main()
