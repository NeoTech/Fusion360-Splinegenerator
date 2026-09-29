"""Regenerate tools/din5480_n.csv with the full DIN 5480 N-series up to dB 100.

The N-series is the reduced-depth hub profile of DIN 5480.  It shares the exact
same preferred-series (reference diameter dB, tooth count z) tables as the
W-series, so the size tables are imported from gen_w_full and only the
diameters differ:

    pitch = m * z
    da    = dB - 0.2 * m       (reduced-depth tip / major diameter)
    df    = dB - 2.4 * m       (reduced-depth root / minor diameter)
    base  = pitch * cos(30 deg)

Because da sits below dB by construction, every (dB, m, z) triple in the table
is geometrically valid; rows are only filtered by dB <= MAX_DB and de-duplicated.

Run from the add-in root:  python tools/gen_n_full.py
"""

import csv
import math
import os

from gen_w_full import TABLES, _fmt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "din5480_n.csv")

MAX_DB = 100.0


def build():
    rows = []
    seen = set()
    for m, pairs in TABLES.items():
        for dB, z in pairs:
            if dB > MAX_DB:
                continue
            key = (dB, m, z)
            if key in seen:
                continue
            seen.add(key)
            pitch = m * z
            da = dB - 0.2 * m
            df = dB - 2.4 * m
            base = pitch * math.cos(math.radians(30.0))
            desig = "N%s\u00d7%s\u00d7%d" % (_fmt(dB), _fmt(m), z)
            rows.append({
                "desig": desig,
                "dB": _fmt(dB),
                "m": _fmt(m),
                "z": str(z),
                "pitch": _fmt(round(pitch, 3)),
                "tip": _fmt(round(da, 3)),
                "root": _fmt(round(df, 3)),
                "base": _fmt(round(base, 3)),
            })
    rows.sort(key=lambda r: (float(r["dB"]), float(r["m"]), int(r["z"])))
    return rows


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["desig", "dB", "m", "z", "pitch", "tip", "root", "base"]
        )
        w.writeheader()
        w.writerows(rows)
    print("wrote", OUT, len(rows), "rows")


if __name__ == "__main__":
    main()
