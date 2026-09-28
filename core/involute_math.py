"""
core.involute_math
==================

Pure (dependency-free) geometry engine for involute splines.

All public functions accept SI-style inputs in **millimetres** and angles in
**degrees**, and return Cartesian point arrays in millimetres expressed in
sketch-local coordinates (X, Y).  Unit conversion to Fusion 360's internal
centimetre base unit happens only in the CAD layer (``cad.sketch_builder``).

Standards covered
-----------------
* DIN 5480  (metric involute splines, module driven)
* ANSI B92.1 / SAE (imperial involute splines, stub diametral pitch driven)

The involute flank is generated with the classic parametric polar form.  For a
point on the flank at radius ``r`` whose local pressure angle is ``alpha_r``
(``cos(alpha_r) = r_b / r``), the polar angle measured from the tooth
centre-line is::

    phi(r) = psi_p + inv(alpha) - inv(alpha_r)

where ``inv(a) = tan(a) - a`` is the involute function and ``psi_p`` is the
half tooth angle at the pitch circle.  Mirroring ``phi`` about the tooth
bisector produces the opposite flank.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _deg(rad: float) -> float:
    return math.degrees(rad)


def _rad(deg: float) -> float:
    return math.radians(deg)


def involute_func(angle_rad: float) -> float:
    """The involute function ``tan(a) - a``."""
    return math.tan(angle_rad) - angle_rad


# ---------------------------------------------------------------------------
# Root type (ANSI B92.1 side fit)
# ---------------------------------------------------------------------------
# ANSI B92.1 involute splines come in two side-fit/root forms:
#   * "flat"   - flat root, full addendum (a = 1.0 m), small clearance.
#   * "fillet" - fillet root, stub addendum (a = 0.6 m) with a generous root
#                fillet radius so the mating hub crest clears the shaft root.
ROOT_TYPES = ("flat", "fillet")

_ROOT_FACTORS = {
    # root_type: (addendum_factor, clearance_factor, root_fillet_factor)
    "flat": (1.0, 0.25, 0.0),
    "fillet": (0.6, 0.40, 0.38),
}


def root_type_factors(root_type: str) -> Tuple[float, float, float]:
    """Return ``(addendum_factor, clearance_factor, root_fillet_factor)`` for a
    named ANSI root type.  Unknown names fall back to the flat-root set."""
    return _ROOT_FACTORS.get(root_type, _ROOT_FACTORS["flat"])


# ---------------------------------------------------------------------------
# Radius set
# ---------------------------------------------------------------------------
def compute_radii(
    module_mm: float,
    teeth: int,
    pressure_angle_deg: float,
    profile_shift: float = 0.0,
    internal: bool = False,
    addendum_factor: float = None,
    clearance_factor: float = None,
    root_fillet_factor: float = None,
    root_type: str = "flat",
    center_distance_offset_mm: float = 0.0,
    slop_mm: float = 0.0,
) -> Dict[str, float]:
    """Return the characteristic radii (mm) of one involute spline.

    Parameters
    ----------
    module_mm:
        Normal module ``m`` in millimetres.  For imperial splines the caller
        converts the stub diametral pitch to an equivalent module first
        (``m = 25.4 / DP``).
    teeth:
        Number of teeth ``z``.
    pressure_angle_deg:
        Reference pressure angle ``alpha`` in degrees (30 / 37.5 / 45).
    profile_shift:
        Dimensionless profile shift coefficient ``x``.
    internal:
        ``True`` for a hub / sleeve (internal) spline, ``False`` for a shaft.
    root_type:
        ANSI side-fit root form, ``"flat"`` or ``"fillet"``.  Selects the
        addendum / clearance / fillet factors unless those are passed
        explicitly.  Metric (DIN 5480) callers normally leave the default
        ``"flat"``.
    center_distance_offset_mm:
        Optional radial offset applied to the pitch radius (a metric
        centre-distance adjustment).  Shifts both the major and root radii
        outward by this amount without changing the tooth thickness.
    slop_mm:
        Radial fit allowance (interference / clearance).  A positive value
        enlarges an internal hub by ``slop_mm`` and shrinks an external shaft
        by ``slop_mm``, opening a small clearance so a precisely-modelled
        mating pair is not an exact (too-tight) line-to-line fit.  Applied as a
        radial shift of the pitch radius, so the involute tooth shape is
        preserved and only its radial placement moves.
    """
    if teeth < 2:
        raise ValueError("A spline needs at least 2 teeth.")

    if addendum_factor is None or clearance_factor is None or root_fillet_factor is None:
        a_f, c_f, r_f = root_type_factors(root_type)
        addendum_factor = a_f if addendum_factor is None else addendum_factor
        clearance_factor = c_f if clearance_factor is None else clearance_factor
        root_fillet_factor = r_f if root_fillet_factor is None else root_fillet_factor

    pitch_d = module_mm * teeth
    # Fit allowance: grow an internal hub, shrink an external shaft (radially).
    slop_shift = slop_mm if internal else -slop_mm
    alpha = _rad(pressure_angle_deg)
    # The involute flank (the mating surface) carries the full radial slop, so
    # the base circle that generates it is shifted by the whole amount --
    # otherwise only the tip/root lands move and the flank arcs stay anchored to
    # the unshifted base circle.
    r_base = (pitch_d / 2.0) * math.cos(alpha) + slop_shift
    # The tip/root lands only move by HALF the slop.  The flanks, not the lands,
    # are the fit surfaces, so the tooth closes up at top and bottom while the
    # side clearance stays at the full slop.
    r_pitch = pitch_d / 2.0 + center_distance_offset_mm + slop_shift / 2.0

    # Addendum / dedendum (external convention).
    addendum = module_mm * (addendum_factor + profile_shift)
    dedendum = module_mm * (addendum_factor + clearance_factor - profile_shift)

    if not internal:
        r_major = r_pitch + addendum          # tip of the shaft tooth
        r_root = r_pitch - dedendum           # bottom of the shaft tooth
    else:
        # Internal: the "space" we cut is the mirror of an external tooth.
        r_major = r_pitch + dedendum          # bottom land of the hub (large)
        r_root = r_pitch - addendum           # crest of the hub tooth (small)

    return {
        "module": module_mm,
        "teeth": teeth,
        "pressure_angle": pressure_angle_deg,
        "profile_shift": profile_shift,
        "pitch_radius": r_pitch,
        "base_radius": r_base,
        "major_radius": r_major,
        "root_radius": r_root,
        "pitch_diameter": pitch_d,
        "major_diameter": 2.0 * r_major,
        "root_diameter": 2.0 * r_root,
        "half_tooth_angle_pitch": half_tooth_angle_pitch(
            module_mm, teeth, pressure_angle_deg, profile_shift, internal
        ),
    }


def half_tooth_angle_pitch(
    module_mm: float,
    teeth: int,
    pressure_angle_deg: float,
    profile_shift: float = 0.0,
    internal: bool = False,
) -> float:
    """Half angular tooth thickness at the pitch circle (radians).

    ``s = m * (pi/2 + 2*x*tan(alpha))`` is the circular tooth thickness of an
    external spline; the half angle is ``s / (2 * r_pitch)``.  An internal
    spline space is the complement.
    """
    alpha = _rad(pressure_angle_deg)
    r_pitch = module_mm * teeth / 2.0
    if not internal:
        s = module_mm * (math.pi / 2.0 + 2.0 * profile_shift * math.tan(alpha))
    else:
        s = module_mm * (math.pi / 2.0 - 2.0 * profile_shift * math.tan(alpha))
    return s / (2.0 * r_pitch)


# ---------------------------------------------------------------------------
# Involute flank sampling
# ---------------------------------------------------------------------------
def involute_flank_points(
    r_start: float,
    r_end: float,
    r_base: float,
    psi_p: float,
    alpha_rad: float,
    samples: int = 12,
) -> List[Point]:
    """Sample one involute flank from radius ``r_start`` to ``r_end``.

    Returns points ordered from ``r_start`` to ``r_end``.  ``psi_p`` is the
    half tooth angle at the pitch circle (see
    :func:`half_tooth_angle_pitch`).  The flank is expressed as a positive
    polar angle from the tooth centre-line.
    """
    if r_base <= 0:
        raise ValueError("Base radius must be positive.")

    # The involute only exists at/above the base circle.
    r_lo = max(r_start, r_base)
    pts: List[Point] = []
    inv_alpha = involute_func(alpha_rad)

    # If the requested start is below the base circle, prepend a radial
    # segment point at r_start on the same angular line as r_lo so the
    # profile stays contiguous (root fillet / radial flank region).
    if r_start < r_base:
        # angle at base circle == psi_p + inv_alpha - inv_alpha = psi_p
        pts.append((r_start * math.cos(psi_p), r_start * math.sin(psi_p)))

    def _phi(r: float) -> float:
        alpha_r = math.acos(min(1.0, r_base / r))
        return psi_p + inv_alpha - involute_func(alpha_r)

    # If the tooth/space comes to a point below r_end (phi reaches 0), the
    # involute terminates there; sampling beyond would fold the flank across
    # the centre-line and self-intersect the profile.
    if _phi(r_end) <= 0.0:
        r_tip = _solve_pointed_tip(r_lo, r_end, _phi)
        for i in range(samples):
            r = r_lo + (r_tip - r_lo) * (i / (samples - 1)) if samples > 1 else r_lo
            phi = max(0.0, _phi(r))
            pts.append((r * math.cos(phi), r * math.sin(phi)))
        # Snap the final sample exactly onto the centre-line tip.
        pts[-1] = (r_tip, 0.0)
        return pts

    for i in range(samples):
        r = r_lo + (r_end - r_lo) * (i / (samples - 1)) if samples > 1 else r_lo
        pts.append((r * math.cos(_phi(r)), r * math.sin(_phi(r))))
    return pts


def _solve_pointed_tip(r_lo: float, r_hi: float, phi_fn, tol: float = 1e-9) -> float:
    """Bisection for the radius where ``phi_fn(r)`` crosses zero (pointed tip)."""
    lo, hi = r_lo, r_hi
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if phi_fn(mid) > 0.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def _involute_angle(r: float, r_base: float, psi_p: float, alpha: float) -> float:
    """Polar angle (rad) of the involute flank at radius ``r`` measured from the
    tooth centre-line.  Below the base circle the flank is radial, so the
    base-circle angle ``psi_p`` is returned."""
    if r <= r_base:
        return psi_p
    alpha_r = math.acos(min(1.0, r_base / r))
    return psi_p + involute_func(alpha) - involute_func(alpha_r)


def _flank_point(r: float, r_base: float, psi_p: float, alpha: float) -> Point:
    """Cartesian point on the involute flank at radius ``r`` (upper half)."""
    a = _involute_angle(r, r_base, psi_p, alpha)
    return (r * math.cos(a), r * math.sin(a))


def _mirror_pt(p: Point) -> Point:
    """Mirror a single point about the X axis (the tooth centre-line)."""
    return (p[0], -p[1])


def _arc_or_line(start: Point, mid: Point, end: Point) -> tuple:
    """Return an ``("arc", ...)`` edge, or a ``("line", start, end)`` edge when
    the three points are near-collinear (a degenerate arc that Fusion would
    reject).  Used for short lands (tip / crest) that collapse to a straight
    chord when the tooth is nearly pointed."""
    cross = (mid[0] - start[0]) * (end[1] - start[1]) - (
        mid[1] - start[1]
    ) * (end[0] - start[0])
    span = max(abs(end[0] - start[0]), abs(end[1] - start[1]), 1e-12)
    if abs(cross) / span < 1e-4:
        return ("line", start, end)
    return ("arc", start, mid, end)


def _pointed_tip(r_lo: float, r_hi: float, r_base: float, psi_p: float, alpha: float):
    """Radius where the flank reaches the centre-line (phi -> 0) within
    ``[r_lo, r_hi]``, or ``None`` if the flank stays positive (flat tip land)."""
    if _involute_angle(r_hi, r_base, psi_p, alpha) > 0.0:
        return None
    return _solve_pointed_tip(
        r_lo, r_hi, lambda r: _involute_angle(r, r_base, psi_p, alpha)
    )


def _mirror(points: List[Point]) -> List[Point]:
    """Mirror a point list about the X axis (the tooth centre-line)."""
    return [(x, -y) for (x, y) in points]


def _dedupe(points: List[Point], tol: float = 1e-9) -> List[Point]:
    """Drop consecutive coincident vertices (and a closing duplicate)."""
    out: List[Point] = []
    for p in points:
        if out and abs(out[-1][0] - p[0]) < tol and abs(out[-1][1] - p[1]) < tol:
            continue
        out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) < tol and abs(
        out[0][1] - out[-1][1]
    ) < tol:
        out.pop()
    return out


# ---------------------------------------------------------------------------
# Single-tooth closed profiles
# ---------------------------------------------------------------------------
def external_tooth_edges(
    module_mm: float,
    teeth: int,
    pressure_angle_deg: float,
    profile_shift: float = 0.0,
    root_type: str = "flat",
    center_distance_offset_mm: float = 0.0,
    slop_mm: float = 0.0,
) -> List[tuple]:
    """Closed edge loop for ONE external tooth, centred on +X.

    Each involute flank is a single 3-point arc anchored on the root, pitch and
    major circles; the tip land is one arc and the root land a straight line.
    This produces clean tangent-continuous faces instead of the faceted
    surfaces a many-segment polyline yields.
    """
    g = compute_radii(
        module_mm, teeth, pressure_angle_deg, profile_shift, False,
        root_type=root_type, center_distance_offset_mm=center_distance_offset_mm,
        slop_mm=slop_mm,
    )
    r_b, r_a, r_f, r_p = (
        g["base_radius"], g["major_radius"], g["root_radius"], g["pitch_radius"],
    )
    psi_p = g["half_tooth_angle_pitch"]
    alpha = _rad(pressure_angle_deg)

    start = _flank_point(r_f, r_b, psi_p, alpha)
    r_tip = _pointed_tip(max(r_f, r_b), r_a, r_b, psi_p, alpha)
    end = (r_tip, 0.0) if r_tip is not None else _flank_point(r_a, r_b, psi_p, alpha)
    r_mid = min(r_p, (r_tip if r_tip is not None else r_a) * 0.999)
    r_mid = max(r_mid, max(r_f, r_b) * 1.001)
    mid = _flank_point(r_mid, r_b, psi_p, alpha)
    ms, mm_, me = _mirror_pt(start), _mirror_pt(mid), _mirror_pt(end)

    edges = [("arc", start, mid, end)]
    if r_tip is None:
        edges.append(_arc_or_line(end, (r_a, 0.0), me))
    edges.append(("arc", me, mm_, ms))
    edges.append(("line", ms, start))
    return edges


def internal_space_edges(
    module_mm: float,
    teeth: int,
    pressure_angle_deg: float,
    profile_shift: float = 0.0,
    root_type: str = "flat",
    center_distance_offset_mm: float = 0.0,
    slop_mm: float = 0.0,
) -> List[tuple]:
    """Closed edge loop for ONE internal spline space (the cut region).

    Flanks are 3-point arcs from the hub crest (small radius) out to the hub
    root (large radius); the groove bottom is a straight line and the crest
    land a single arc.
    """
    g = compute_radii(
        module_mm, teeth, pressure_angle_deg, profile_shift, True,
        root_type=root_type, center_distance_offset_mm=center_distance_offset_mm,
        slop_mm=slop_mm,
    )
    r_b, r_major, r_root, r_p = (
        g["base_radius"], g["major_radius"], g["root_radius"], g["pitch_radius"],
    )
    psi_p = g["half_tooth_angle_pitch"]
    alpha = _rad(pressure_angle_deg)

    start = _flank_point(r_root, r_b, psi_p, alpha)
    r_tip = _pointed_tip(max(r_root, r_b), r_major, r_b, psi_p, alpha)
    end = (r_tip, 0.0) if r_tip is not None else _flank_point(r_major, r_b, psi_p, alpha)
    r_mid = min(r_p, (r_tip if r_tip is not None else r_major) * 0.999)
    r_mid = max(r_mid, max(r_root, r_b) * 1.001)
    mid = _flank_point(r_mid, r_b, psi_p, alpha)
    ms, mm_, me = _mirror_pt(start), _mirror_pt(mid), _mirror_pt(end)

    edges = [("arc", start, mid, end)]
    if r_tip is None:
        edges.append(("line", end, me))     # groove bottom (straight land)
    edges.append(("arc", me, mm_, ms))
    edges.append(_arc_or_line(ms, (r_root, 0.0), start))  # crest land
    return edges


def _edges_to_points(edges: List[tuple]) -> List[Point]:
    """Flatten an edge loop to its polygon vertices (for tests / fallback)."""
    pts: List[Point] = []
    for e in edges:
        if e[0] == "arc":
            pts += [e[1], e[2], e[3]]
        else:
            pts.append(e[1])
    return _dedupe(pts)


def external_tooth_profile(
    module_mm: float,
    teeth: int,
    pressure_angle_deg: float,
    profile_shift: float = 0.0,
    samples: int = 12,
    root_fillet_mm: float = 0.0,
    root_type: str = "flat",
    center_distance_offset_mm: float = 0.0,
) -> List[Point]:
    """Vertex list of one external tooth (flattened from the 3-point-arc edges).

    Kept for the pure-math tests; the CAD builder uses
    :func:`external_tooth_edges` to draw true arcs.
    """
    return _edges_to_points(
        external_tooth_edges(
            module_mm, teeth, pressure_angle_deg, profile_shift,
            root_type=root_type, center_distance_offset_mm=center_distance_offset_mm,
        )
    )


def internal_space_profile(
    module_mm: float,
    teeth: int,
    pressure_angle_deg: float,
    profile_shift: float = 0.0,
    samples: int = 12,
    root_type: str = "flat",
    center_distance_offset_mm: float = 0.0,
) -> List[Point]:
    """Vertex list of one internal space (flattened from the arc edges)."""
    return _edges_to_points(
        internal_space_edges(
            module_mm, teeth, pressure_angle_deg, profile_shift,
            root_type=root_type, center_distance_offset_mm=center_distance_offset_mm,
        )
    )


def _arc_between(p_from: Point, p_to: Point, radius: float, steps: int = 4) -> List[Point]:
    """Sample a circular arc (excluding endpoints) at ``radius`` joining two
    already-placed points, going the short way around.

    If the two endpoints already coincide (e.g. a pointed tooth tip on the
    centre-line) the arc is empty, so no spurious bulge is introduced.
    """
    if abs(p_from[0] - p_to[0]) < 1e-9 and abs(p_from[1] - p_to[1]) < 1e-9:
        return []
    a0 = math.atan2(p_from[1], p_from[0])
    a1 = math.atan2(p_to[1], p_to[0])
    # Take the shorter angular direction.
    delta = a1 - a0
    while delta > math.pi:
        delta -= 2 * math.pi
    while delta < -math.pi:
        delta += 2 * math.pi
    out: List[Point] = []
    for i in range(1, steps):
        a = a0 + delta * (i / steps)
        out.append((radius * math.cos(a), radius * math.sin(a)))
    return out


# ---------------------------------------------------------------------------
# Imperial helper
# ---------------------------------------------------------------------------
def diametral_pitch_to_module(dp: float) -> float:
    """Convert a (stub) diametral pitch ``P`` [1/in] to module [mm]."""
    if dp <= 0:
        raise ValueError("Diametral pitch must be positive.")
    return 25.4 / dp
