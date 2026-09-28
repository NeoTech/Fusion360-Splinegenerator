"""
core.presets
============

Standards lookup tables (DIN 5480, ANSI B92.1, SAE J499 / ISO 500).

Each preset is a dictionary of design parameters keyed by a human-readable
name.  The UI layer reads these to auto-fill and lock the parameter inputs.

Units
-----
* ``module_mm``        : normal module, millimetres
* ``dp``               : stub diametral pitch, 1/inch (imperial involute)
* ``major_diameter_mm``/``minor_diameter_mm`` : parallel-side diameters, mm
* ``pressure_angle_deg`` : reference pressure angle, degrees
* ``profile_shift``    : dimensionless profile shift coefficient x
* ``teeth``            : number of teeth z
"""

from __future__ import annotations

from typing import Dict, Any

# name -> parameter dict
PRESETS: Dict[str, Dict[str, Any]] = {
    "Custom": {
        "kind": "custom",
    },

    # ---- SAE J499 / ISO 500 parallel-side tractor PTO -------------------
    "Tractor PTO 1-3/8\" 6T (540 RPM)": {
        "kind": "parallel",
        "spline_type": "parallel",
        "gender": "external",
        "teeth": 6,
        "major_diameter_mm": 34.9254,   # 1-3/8 in
        "minor_diameter_mm": 29.4132,   # 1-5/32 in
        "tooth_width_mm": 8.73,
        "length_mm": 60.0,
    },
    "Tractor PTO 1-3/8\" 21T (1000 RPM)": {
        "kind": "parallel",
        "spline_type": "parallel",
        "gender": "external",
        "teeth": 21,
        "major_diameter_mm": 34.9254,   # 1-3/8 in
        "minor_diameter_mm": 31.75,     # 1-1/4 in
        "tooth_width_mm": 3.0,
        "length_mm": 60.0,
    },
    "Tractor PTO 1-3/4\" 20T (1000 RPM)": {
        "kind": "parallel",
        "spline_type": "parallel",
        "gender": "external",
        "teeth": 20,
        "major_diameter_mm": 44.45,     # 1-3/4 in
        "minor_diameter_mm": 40.487,    # 1-19/32 in
        "tooth_width_mm": 4.0,
        "length_mm": 60.0,
    },

    # ---- DIN 5480 metric involute ----------------------------------------
    "DIN 5480 W30x2x14": {
        "kind": "involute",
        "spline_type": "metric",
        "gender": "external",
        "module_mm": 2.0,
        "teeth": 14,
        "pressure_angle_deg": 30.0,
        "profile_shift": 0.0,
        "length_mm": 40.0,
    },
    "DIN 5480 W40x2x18": {
        "kind": "involute",
        "spline_type": "metric",
        "gender": "external",
        "module_mm": 2.0,
        "teeth": 18,
        "pressure_angle_deg": 30.0,
        "profile_shift": 0.0,
        "length_mm": 40.0,
    },
    "DIN 5480 W26x3x16": {
        "kind": "involute",
        "spline_type": "metric",
        "gender": "external",
        "module_mm": 3.0,
        "teeth": 16,
        "pressure_angle_deg": 30.0,
        "profile_shift": 0.0,
        "length_mm": 40.0,
    },

    # ---- ANSI B92.1 imperial involute ------------------------------------
    "ANSI B92.1 16/32 DP 30T 30deg": {
        "kind": "involute",
        "spline_type": "imperial",
        "gender": "external",
        "dp": 16.0,
        "dp_series": "16/32",
        "root_type": "flat",
        "teeth": 30,
        "pressure_angle_deg": 30.0,
        "profile_shift": 0.0,
        "length_mm": 40.0,
    },
    "ANSI B92.1 16/32 DP 30T 30deg (Fillet)": {
        "kind": "involute",
        "spline_type": "imperial",
        "gender": "external",
        "dp": 16.0,
        "dp_series": "16/32",
        "root_type": "fillet",
        "teeth": 30,
        "pressure_angle_deg": 30.0,
        "profile_shift": 0.0,
        "length_mm": 40.0,
    },
    "ANSI B92.1 24/48 DP 37.5deg": {
        "kind": "involute",
        "spline_type": "imperial",
        "gender": "external",
        "dp": 24.0,
        "dp_series": "24/48",
        "root_type": "flat",
        "teeth": 24,
        "pressure_angle_deg": 37.5,
        "profile_shift": 0.0,
        "length_mm": 40.0,
    },
}


# ANSI B92.1 stub diametral-pitch series (major/minor DP).  The UI dropdown
# offers these; the major DP drives the pitch diameter (D = z / P_d).
DP_SERIES = ["12/24", "16/32", "24/48", "32/64"]


def dp_series_to_major_dp(series: str) -> float:
    """Return the major diametral pitch ``P_d`` of a "16/32"-style series."""
    if not series:
        return 0.0
    head = series.split("/")[0]
    return float(head)


# SAE J499 / ISO 500 parallel-side PTO shafts use a small set of fixed tooth
# counts.  The UI offers these as a convenience for the parallel standard.
PARALLEL_TOOTH_COUNTS = [6, 8, 10]


def preset_names() -> list:
    """Ordered list of preset names for the UI dropdown."""
    return list(PRESETS.keys())


def apply_preset(name: str) -> Dict[str, Any]:
    """Return a copy of the parameter dict for ``name`` (empty for Custom)."""
    return dict(PRESETS.get(name, {"kind": "custom"}))
