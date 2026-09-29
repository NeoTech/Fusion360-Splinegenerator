"""Regenerate tools/sae_j744.csv with the common SAE J744 involute hydraulic
motor / pump input-shaft splines.

SAE J744 (Hydraulic Equipment - Mounting Flanges and Shafts for Attachments)
tabulates a fixed set of 30-degree involute shaft-end codes used on SAE A/B/C/D/E/F
flange motors and pumps throughout the automotive, off-highway and mobile-hydraulic
industries.  These shafts are geometrically the same family as the ANSI B92.1
30-degree flat-root side-fit involute splines, so the basic external (shaft)
diameters follow the identical closed-form equations in inches:

    major M = (N + 1) / P
    minor m = (N - 1.35) / P   for P <= 12/24
    minor m = (N - 2.0 ) / P   for P >= 16/32

with N the tooth count and P the (major) diametral pitch of the P/2P stub series.
The pitch diameter is D = N / P.

The shaft-end codes below are transcribed from the J744 shaft-end table; the
diameters are computed from the standard formulas (the published "minimum LA"
minor values in the standard are inspection wear limits, slightly above the
basic minor computed here).

Run from the add-in root:  python tools/gen_sae_full.py
"""

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "sae_j744.csv")

PRESSURE_ANGLE = 30.0

# (code, flange, teeth N, major DP P).  Transcribed from SAE J744 shaft-end table.
SHAFTS = [
    ("13-4", "A-A", 9, 20.0),
    ("16-4", "A", 9, 16.0),
    ("19-4", "A", 11, 16.0),
    ("22-4", "B", 13, 16.0),
    ("25-4", "B-B", 15, 16.0),
    ("32-4", "C", 14, 12.0),
    ("38-4", "C-C", 17, 12.0),
    ("44-4", "D", 13, 8.0),
    ("50-4", "F", 15, 8.0),
]


def _series_label(p):
    return "%g/%g" % (p, 2 * p)


def _minor(n, p):
    c = 1.35 if p <= 12.0 else 2.0
    return (n - c) / p


def _major(n, p):
    return (n + 1.0) / p


def build():
    rows = []
    for code, flange, n, p in SHAFTS:
        rows.append({
            "desig": "SAE J744 %s (%s flange) %dT %s DP" % (
                code, flange, n, _series_label(p)),
            "code": code,
            "flange": flange,
            "series": _series_label(p),
            "dp": "%g" % p,
            "z": n,
            "pa": "%g" % PRESSURE_ANGLE,
            "root": "flat",
            "pitch_in": "%.6f" % (n / p),
            "major_in": "%.6f" % _major(n, p),
            "minor_in": "%.6f" % _minor(n, p),
        })
    return rows


HEADER = ["desig", "code", "flange", "series", "dp", "z", "pa", "root",
          "pitch_in", "major_in", "minor_in"]


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    print("wrote", OUT, len(rows), "rows")


if __name__ == "__main__":
    main()
