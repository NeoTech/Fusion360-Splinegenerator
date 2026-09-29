"""Regenerate tools/sae_pto.csv with the standard agricultural tractor PTO
splines (SAE J499 / ASAE / ISO 500 / DIN 9611).

The rear-tractor PTO shaft family is defined by four ISO 500 types.  Type 1 is
the classic 6-spline parallel-side shaft; types 2-4 are involute but are modelled
here with the same parallel-side (straight flank) approximation the add-in uses
for all PTO presets, driven purely by their published major / minor diameters and
tooth thickness.  Diameters are the published nominal millimetre values.

    type  nominal      teeth  rpm        major    minor    tooth_w
    1     1-3/8 in     6      540        34.9254  29.4132  8.73
    2     1-3/8 in     21     1000       34.9254  31.75    3.0
    3     1-3/4 in     20     1000       44.45    40.487   4.0
    4     57.5 mm      22     1000/1300  57.525   52.760   3.955

Run from the add-in root:  python tools/gen_sae_pto_full.py
"""

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "sae_pto.csv")

# (name, teeth, major_mm, minor_mm, tooth_width_mm).  Types 1-3 keep the exact
# values already used by the add-in tests; type 4 is the high-capacity addition.
PTOS = [
    ('Tractor PTO 1-3/8" 6T (540 RPM)', 6, 34.9254, 29.4132, 8.73),
    ('Tractor PTO 1-3/8" 21T (1000 RPM)', 21, 34.9254, 31.75, 3.0),
    ('Tractor PTO 1-3/4" 20T (1000 RPM)', 20, 44.45, 40.487, 4.0),
    ('Tractor PTO 57.5mm 22T (1000/1300 RPM)', 22, 57.525, 52.760, 3.955),
]

HEADER = ["desig", "z", "major_mm", "minor_mm", "tooth_width_mm"]


def build():
    rows = []
    for name, z, maj, mino, tw in PTOS:
        rows.append({
            "desig": name, "z": z,
            "major_mm": ("%g" % maj), "minor_mm": ("%g" % mino),
            "tooth_width_mm": ("%g" % tw),
        })
    return rows


def main():
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(build())
    print("wrote", OUT, len(PTOS), "rows")


if __name__ == "__main__":
    main()
