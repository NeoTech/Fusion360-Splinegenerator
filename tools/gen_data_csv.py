"""Regenerate the core/data/*.csv preset files from the authoritative tables.

The DIN 5480 W- and N-series come from the raw standard tables in tools/
(din5480_w.csv, din5480_n.csv), which are themselves produced by
gen_w_full.py / gen_n_full.py.  The ANSI and PTO families are small and kept
inline here.  All four are emitted into core/data/ in the uniform preset schema
that core.presets parses at import time.

Run from the add-in root:  python tools/gen_data_csv.py
"""

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "core", "data")
SRC_W = os.path.join(ROOT, "tools", "din5480_w.csv")
SRC_N = os.path.join(ROOT, "tools", "din5480_n.csv")
SRC_B = os.path.join(ROOT, "tools", "ansi_b921.csv")
SRC_J = os.path.join(ROOT, "tools", "sae_j744.csv")
SRC_PTO = os.path.join(ROOT, "tools", "sae_pto.csv")

IN2MM = 25.4

# Uniform superset header. Empty cell => field omitted from the preset dict.
HEADER = [
    "name", "kind", "spline_type", "gender", "teeth", "pressure_angle_deg",
    "profile_shift", "length_mm", "module_mm", "tip_diameter_mm",
    "root_diameter_mm", "dp", "dp_series", "root_type", "major_diameter_mm",
    "minor_diameter_mm", "tooth_width_mm",
]


def _num(value):
    """Trim trailing zeros so 2.0 -> '2', 0.50 -> '0.5' (cosmetic only)."""
    return ("%g" % float(value))


def _dec(value):
    """Keep at least one decimal so 2 -> '2.0', 1.25 -> '1.25' (N-series naming)."""
    return str(float(value))


def _metric_rows(src, name_fn):
    rows = []
    with open(src, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "name": name_fn(r),
                "kind": "involute", "spline_type": "metric", "gender": "external",
                "teeth": r["z"], "pressure_angle_deg": "30", "profile_shift": "0",
                "length_mm": "40", "module_mm": _num(r["m"]),
                "tip_diameter_mm": _num(r["tip"]),
                "root_diameter_mm": _num(r["root"]),
            })
    return rows


def _w_name(r):
    # W6\u00d70.5\u00d710 -> DIN 5480 W6x0.5x10
    return "DIN 5480 " + r["desig"].replace("\u00d7", "x")


def _n_name(r):
    # N-series keeps a decimal in the module: DIN 5480 N40x2.0x18
    return "DIN 5480 N%sx%sx%s" % (_num(r["dB"]), _dec(r["m"]), r["z"])


def gen_w():
    return _metric_rows(SRC_W, _w_name)


def gen_n():
    return _metric_rows(SRC_N, _n_name)


def gen_ansi():
    rows = []
    with open(SRC_B, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "name": r["desig"], "kind": "involute", "spline_type": "imperial",
                "gender": "external", "teeth": r["z"],
                "pressure_angle_deg": _num(r["pa"]), "profile_shift": "0",
                "length_mm": "40", "dp": _num(r["dp"]), "dp_series": r["series"],
                "root_type": r["root"],
                "tip_diameter_mm": _num(float(r["major_in"]) * IN2MM),
                "root_diameter_mm": _num(float(r["minor_in"]) * IN2MM),
            })
    return rows


def gen_sae():
    # SAE J744 involute hydraulic motor/pump shaft splines (30 deg flat root).
    rows = []
    with open(SRC_J, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "name": r["desig"], "kind": "involute", "spline_type": "imperial",
                "gender": "external", "teeth": r["z"],
                "pressure_angle_deg": _num(r["pa"]), "profile_shift": "0",
                "length_mm": "40", "dp": _num(r["dp"]), "dp_series": r["series"],
                "root_type": r["root"],
                "tip_diameter_mm": _num(float(r["major_in"]) * IN2MM),
                "root_diameter_mm": _num(float(r["minor_in"]) * IN2MM),
            })
    return rows


def gen_pto():
    # SAE J499 / ISO 500 parallel-side tractor PTO shafts (types 1-4).
    rows = []
    with open(SRC_PTO, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "name": r["desig"], "kind": "parallel", "spline_type": "parallel",
                "gender": "external", "teeth": r["z"], "length_mm": "60",
                "major_diameter_mm": _num(r["major_mm"]),
                "minor_diameter_mm": _num(r["minor_mm"]),
                "tooth_width_mm": _num(r["tooth_width_mm"]),
            })
    return rows


def write(fname, rows):
    path = os.path.join(DATA, fname)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})
    print("wrote", path, len(rows), "rows")


def main():
    os.makedirs(DATA, exist_ok=True)
    write("din5480_w.csv", gen_w())
    write("din5480_n.csv", gen_n())
    write("ansi_b921.csv", gen_ansi())
    write("sae_j744.csv", gen_sae())
    write("sae_pto.csv", gen_pto())


if __name__ == "__main__":
    main()
