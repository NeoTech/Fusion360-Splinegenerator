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
    """
    if teeth < 2:
        raise ValueError("A spline needs at least 2 teeth.")

    if addendum_factor is None or clearance_factor is None or root_fillet_factor is None:
        a_f, c_f, r_f = root_type_factors(root_type)
        addendum_factor = a_f if addendum_factor is None else addendum_factor
        clearance_factor = c_f if clearance_factor is None else clearance_factor
        root_fillet_factor = r_f if root_fillet_factor is None else root_fillet_factor

    pitch_d = module_mm * teeth
    r_pitch = pitch_d / 2.0 + center_distance_offset_mm
    alpha = _rad(pressure_angle_deg)
    r_base = (pitch_d / 2.0) * math.cos(alpha)

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
    """Closed polyline for ONE external spline tooth, centred on +X.

    Order: root-left -> up left flank -> tip arc -> down right flank ->
    root-right -> close.  The builder revolves this loop ``z`` times.
    """
    g = compute_radii(
        module_mm, teeth, pressure_angle_deg, profile_shift, False,
        root_type=root_type, center_distance_offset_mm=center_distance_offset_mm,
    )
    r_b, r_a, r_f = g["base_radius"], g["major_radius"], g["root_radius"]
    psi_p = g["half_tooth_angle_pitch"]
    alpha = _rad(pressure_angle_deg)

    left = involute_flank_points(r_f, r_a, r_b, psi_p, alpha, samples)
    # Right flank runs tip -> root so the loop stays contiguous.
    right = _mirror(left[::-1])

    # Tip land: short rounded arc across the tooth top.
    tip = _arc_between(left[-1], right[0], r_a)
    # Root land: a single straight line across the bottom, formed by the
    # closing polygon edge from right's last point back to left's first point.
    # No arc, so the tooth base is flat and sits exactly on the root circle
    # (no inward sag / gap against the base cylinder).
    return _dedupe(left + tip + right)


def internal_space_profile(
    module_mm: float,
    teeth: int,
    pressure_angle_deg: float,
    profile_shift: float = 0.0,
    samples: int = 12,
    root_type: str = "flat",
    center_distance_offset_mm: float = 0.0,
) -> List[Point]:
    """Closed polyline for ONE internal spline tooth-space (the cut region).

    For an internal spline the hub teeth are involute too, but the cutting
    tool profile is the *space* between them, which is itself an involute
    channel.  We generate the space as a loop whose flanks are involutes
    measured from the space centre-line.
    """
    g = compute_radii(
        module_mm, teeth, pressure_angle_deg, profile_shift, True,
        root_type=root_type, center_distance_offset_mm=center_distance_offset_mm,
    )
    r_b, r_major, r_root = g["base_radius"], g["major_radius"], g["root_radius"]
    psi_p = g["half_tooth_angle_pitch"]
    alpha = _rad(pressure_angle_deg)

    # Flanks run from the hub crest (small radius) out to the hub root (large).
    left = involute_flank_points(r_root, r_major, r_b, psi_p, alpha, samples)
    right = _mirror(left[::-1])
    # Groove bottom (at r_major) is a single straight line: the closing edge
    # from left's last point to right's first point. The crest land (at r_root)
    # keeps a short arc.
    inner = _arc_between(right[-1], left[0], r_root)
    return _dedupe(left + right + inner)


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
