"""
core.parallel_math
==================

Pure geometry engine for parallel-side (straight-sided) splines used on
agricultural tractor PTO shafts (SAE J499 / ISO 500 / DIN 9611).

Unlike involute splines the flanks are straight radial lines, so a single
tooth profile is a simple polygon: two radial flanks joined by a tip land and
a root land.  Inputs are millimetres, outputs are sketch-local (X, Y) point
arrays in millimetres.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

Point = Tuple[float, float]


def compute_radii(
    major_diameter_mm: float,
    minor_diameter_mm: float,
    teeth: int,
    tooth_width_mm: float = 0.0,
    internal: bool = False,
    slop_mm: float = 0.0,
) -> Dict[str, float]:
    """Characteristic radii/diameters for a parallel-side spline.

    ``slop_mm`` is a radial fit allowance: a positive value enlarges an internal
    hub and shrinks an external shaft (both radii shift by ``+slop`` for a hub,
    ``-slop`` for a shaft) so a precisely-modelled mating pair is not an exact
    line-to-line fit.  The tooth/space angles are held fixed, so the profile
    scales purely radially.
    """
    if teeth < 2:
        raise ValueError("A spline needs at least 2 teeth.")
    shift = slop_mm if internal else -slop_mm
    r_major = major_diameter_mm / 2.0 + shift
    r_minor = minor_diameter_mm / 2.0 + shift
    if r_major <= r_minor:
        raise ValueError("Major diameter must exceed minor diameter.")
    return {
        "major_radius": r_major,
        "minor_radius": r_minor,
        "major_diameter": major_diameter_mm,
        "minor_diameter": minor_diameter_mm,
        "teeth": teeth,
        "tooth_width": tooth_width_mm,
        "pitch_radius": (r_major + r_minor) / 2.0,
    }


def _half_tooth_angle(r_major: float, teeth: int, tooth_width_mm: float) -> float:
    """Half angular width of one tooth.

    If an explicit chordal ``tooth_width_mm`` is supplied at the major
    diameter it is honoured; otherwise the tooth is assumed to occupy half the
    pitch (``pi / z`` full angle -> ``pi / (2 z)`` half angle).
    """
    if tooth_width_mm and tooth_width_mm > 0:
        # chord width at major radius -> half angle
        return math.asin(min(1.0, (tooth_width_mm / 2.0) / r_major))
    return math.pi / (2.0 * teeth)


def external_tooth_profile(
    major_diameter_mm: float,
    minor_diameter_mm: float,
    teeth: int,
    tooth_width_mm: float = 0.0,
    slop_mm: float = 0.0,
) -> List[Point]:
    """Closed trapezoid for ONE external parallel-side tooth, centred on +X.

    Order: root-left -> tip-left -> tip-right -> root-right -> close.
    """
    g = compute_radii(
        major_diameter_mm, minor_diameter_mm, teeth, tooth_width_mm,
        internal=False, slop_mm=slop_mm,
    )
    r_a, r_f = g["major_radius"], g["minor_radius"]
    ha = _half_tooth_angle(r_a, teeth, tooth_width_mm)
    # Keep the root narrower than the tip only if a chordal width was given;
    # for the default half-pitch case flanks are radial so ha is shared.
    ha_root = ha if not tooth_width_mm else math.asin(
        min(1.0, (tooth_width_mm / 2.0) / r_a)
    )

    pts = [
        (r_f * math.cos(ha_root), r_f * math.sin(ha_root)),   # root left
        (r_a * math.cos(ha), r_a * math.sin(ha)),             # tip left
        (r_a * math.cos(ha), -r_a * math.sin(ha)),            # tip right
        (r_f * math.cos(ha_root), -r_f * math.sin(ha_root)),  # root right
    ]
    return pts


def internal_space_profile(
    major_diameter_mm: float,
    minor_diameter_mm: float,
    teeth: int,
    tooth_width_mm: float = 0.0,
    slop_mm: float = 0.0,
) -> List[Point]:
    """Closed polygon for ONE internal spline space (the cut region).

    For a parallel-side hub the space between hub teeth is the complement of an
    external tooth: a trapezoid whose wide end is at the hub crest (minor
    radius) and narrow end at the hub root (major radius).
    """
    g = compute_radii(
        major_diameter_mm, minor_diameter_mm, teeth, tooth_width_mm,
        internal=True, slop_mm=slop_mm,
    )
    r_a, r_f = g["major_radius"], g["minor_radius"]
    # Space half-angle at the small (crest) radius.
    ha_space = math.pi / (2.0 * teeth)
    pts = [
        (r_f * math.cos(ha_space), r_f * math.sin(ha_space)),
        (r_a * math.cos(ha_space), r_a * math.sin(ha_space)),
        (r_a * math.cos(ha_space), -r_a * math.sin(ha_space)),
        (r_f * math.cos(ha_space), -r_f * math.sin(ha_space)),
    ]
    return pts


def inch_to_mm(value_inch: float) -> float:
    return value_inch * 25.4
