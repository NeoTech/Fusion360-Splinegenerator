"""Regenerate tools/ansi_b921.csv with the common ANSI B92.1-1970 involute
spline series used throughout the automotive industry.

Unlike DIN 5480 (which is published as fixed dB/z tables), ANSI B92.1 defines
its sizes *parametrically*: every combination of a standard diametral-pitch
series P/2P, an integer tooth count N, a pressure angle and a root form is a
standardised spline whose basic external (shaft) diameters follow closed-form
equations in inches.  This script enumerates the common automotive subset and
emits the exact basic major (tip) and minor (root) diameters so the CAD layer
can reproduce them via the tip/root override path (the builder's metric
addendum factors are not valid for ANSI stub teeth).

Basic external formulas (inches), D = N/P is the pitch diameter:

    major M = (N + 1) / P                       (all side-fit series)

    30 deg flat-root   side fit : m = (N - 1.35)/P  (P <= 12/24)
                                  m = (N - 2.0 )/P  (P >= 16/32)
    30 deg fillet-root side fit : m = (N - 1.8 )/P
    37.5 deg fillet-root        : m = (N - 1.3 )/P
    45 deg fillet-root          : m = (N - 1.0 )/P

To keep the preset list usable, only the finer automotive DP series are
generated and rows are kept when the pitch diameter falls inside
[MIN_PD_IN, MAX_PD_IN].

Run from the add-in root:  python tools/gen_b921_full.py
"""

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "ansi_b921.csv")

# Common automotive stub-pitch series (major DP P; the /2P is the stub pitch).
SERIES = [12.0, 16.0, 20.0, 24.0, 32.0, 40.0, 48.0]

# Keep only physically sensible shaft sizes for a usable dropdown.
MIN_PD_IN = 0.30
MAX_PD_IN = 3.00

# (pressure_angle_deg, root_form) -> minor-diameter coefficient rule.
# The flat-root 30 deg rule depends on the pitch, handled in _minor().
FORMS = [
    (30.0, "flat"),
    (30.0, "fillet"),
    (37.5, "fillet"),
    (45.0, "fillet"),
]

# Tooth-count ranges per pressure angle (45 deg series run finer/deeper).
def _n_range(pa):
    return range(6, 101) if pa == 45.0 else range(6, 61)


def _series_label(p):
    return "%g/%g" % (p, 2 * p)


def _minor(pa, form, n, p):
    """Basic external minor (root) diameter in inches."""
    if pa == 30.0 and form == "flat":
        c = 1.35 if p <= 12.0 else 2.0
    elif pa == 30.0 and form == "fillet":
        c = 1.8
    elif pa == 37.5:
        c = 1.3
    elif pa == 45.0:
        c = 1.0
    else:
        raise ValueError("unknown form %s/%s" % (pa, form))
    return (n - c) / p


def _major(n, p):
    return (n + 1.0) / p


def build():
    rows = []
    for p in SERIES:
        for pa, form in FORMS:
            for n in _n_range(pa):
                pd = n / p
                if not (MIN_PD_IN <= pd <= MAX_PD_IN):
                    continue
                major = _major(n, p)
                minor = _minor(pa, form, n, p)
                if minor <= 0:
                    continue
                rows.append({
                    "desig": "ANSI B92.1 %s DP %dT %gdeg%s" % (
                        _series_label(p), n, pa,
                        " (Fillet)" if form == "fillet" else ""),
                    "series": _series_label(p),
                    "dp": "%g" % p,
                    "z": n,
                    "pa": "%g" % pa,
                    "root": form,
                    "pitch_in": "%.6f" % pd,
                    "major_in": "%.6f" % major,
                    "minor_in": "%.6f" % minor,
                })
    # De-duplicate by designation, keep first.
    seen = set()
    uniq = []
    for r in rows:
        if r["desig"] in seen:
            continue
        seen.add(r["desig"])
        uniq.append(r)
    return uniq


HEADER = ["desig", "series", "dp", "z", "pa", "root",
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
