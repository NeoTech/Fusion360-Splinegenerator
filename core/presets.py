"""
core.presets
============

Standards lookup tables (DIN 5480, ANSI B92.1, SAE J499 / ISO 500).

The preset data lives in CSV files under ``core/data/`` (one file per standard
family) so the tables can be edited without touching Python.  At import time
these are parsed into the ``PRESETS`` dict that the UI layer consumes.

Data files
----------
* ``din5480_w.csv``  : DIN 5480 W-series (full-depth) metric involute
* ``din5480_n.csv``  : DIN 5480 N-series (reduced-depth) metric involute
* ``ansi_b921.csv``  : ANSI B92.1 / SAE imperial involute
* ``sae_pto.csv``    : SAE J499 / ISO 500 parallel-side tractor PTO

Each CSV uses a uniform superset header; an empty cell means the field is
omitted from that preset's parameter dict.  ``tools/gen_data_csv.py`` regenerates
the data files from the authoritative standard tables.

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

import csv
import os
from typing import Dict, Any, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, "data")

# CSV files are loaded in this order; "Custom" is always first in PRESETS.
_DATA_FILES = [
    "sae_pto.csv",
    "din5480_w.csv",
    "din5480_n.csv",
    "ansi_b921.csv",
]

# Column -> Python type.  Columns not listed (and empty cells) are skipped.
_INT_FIELDS = {"teeth"}
_FLOAT_FIELDS = {
    "pressure_angle_deg", "profile_shift", "length_mm", "module_mm",
    "tip_diameter_mm", "root_diameter_mm", "dp", "major_diameter_mm",
    "minor_diameter_mm", "tooth_width_mm",
}
_STR_FIELDS = {"kind", "spline_type", "gender", "dp_series", "root_type"}


def _parse_row(row: Dict[str, str]) -> Dict[str, Any]:
    """Convert one CSV row (a dict of strings) into a parameter dict."""
    params: Dict[str, Any] = {}
    for key, raw in row.items():
        if key == "name" or raw is None or raw == "":
            continue
        if key in _INT_FIELDS:
            params[key] = int(float(raw))
        elif key in _FLOAT_FIELDS:
            params[key] = float(raw)
        elif key in _STR_FIELDS:
            params[key] = raw
        # unknown columns are ignored
    return params


def _load_presets() -> Dict[str, Dict[str, Any]]:
    """Read every data file and build the ordered PRESETS mapping."""
    presets: Dict[str, Dict[str, Any]] = {"Custom": {"kind": "custom"}}
    for fname in _DATA_FILES:
        path = os.path.join(_DATA_DIR, fname)
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = row.get("name")
                if not name:
                    continue
                presets[name] = _parse_row(row)
    return presets


# name -> parameter dict (built from CSV at import time)
PRESETS: Dict[str, Dict[str, Any]] = _load_presets()


def reload_presets() -> Dict[str, Dict[str, Any]]:
    """Re-read the CSV data files and refresh ``PRESETS`` in place.

    Returns the freshly built mapping.  The module-level ``PRESETS`` name is
    updated so existing ``from core import presets`` references see new data
    without a Python process restart.
    """
    global PRESETS
    PRESETS = _load_presets()
    return PRESETS


# ANSI B92.1 stub diametral-pitch series (major/minor DP).  The UI dropdown
# offers these; the major DP drives the pitch diameter (D = z / P_d).
DP_SERIES = ["12/24", "16/32", "24/48", "32/64", "20/40", "40/80", "48/96"]


def dp_series_to_major_dp(series: str) -> float:
    """Return the major diametral pitch ``P_d`` of a "16/32"-style series."""
    if not series:
        return 0.0
    head = series.split("/")[0]
    return float(head)


# SAE J499 / ISO 500 parallel-side PTO shafts use a small set of fixed tooth
# counts.  The UI offers these as a convenience for the parallel standard.
PARALLEL_TOOTH_COUNTS = [6, 8, 10]


def preset_names() -> List[str]:
    """Ordered list of preset names for the UI dropdown."""
    return list(PRESETS.keys())


def apply_preset(name: str) -> Dict[str, Any]:
    """Return a copy of the parameter dict for ``name`` (empty for Custom)."""
    return dict(PRESETS.get(name, {"kind": "custom"}))
