"""
cad.sketch_builder
==================

Turns geometry point arrays (millimetres) produced by the ``core`` math
engines into Fusion 360 sketch entities.

IMPORTANT: Fusion 360's internal length unit is the **centimetre**.  Every
value handed to the API here is converted from millimetres by dividing by 10
(``MM_TO_CM``).
"""

from __future__ import annotations

from typing import List, Tuple, Any

import adsk.core as core
import adsk.fusion as fusion

MM_TO_CM = 0.1

Point = Tuple[float, float]


def _app() -> core.Application:
    return core.Application.get()


def find_or_create_sketch(plane: Any, name: str = "SplineProfile") -> fusion.Sketch:
    """Create a new profile sketch on the given construction geometry."""
    comp = _app().ActiveProduct.designs[0].activeComponent
    return find_or_create_sketch_on(comp, plane, name)


def find_or_create_sketch_on(
    component: Any, plane: Any, name: str = "SplineProfile"
) -> fusion.Sketch:
    """Create a new profile sketch on ``plane`` within ``component``."""
    sk: fusion.Sketch = component.sketches.add(plane)
    sk.name = name
    return sk


def _pt(x_mm: float, y_mm: float) -> core.Point3D:
    return core.Point3D.create(x_mm * MM_TO_CM, y_mm * MM_TO_CM, 0.0)


def add_circle(
    sketch: fusion.Sketch, radius_mm: float, construction: bool = False
) -> fusion.SketchCircle:
    """Add a full circle centred on the sketch origin.

    ``construction=True`` marks it as construction geometry so it does not
    create a fillable profile (used for the reference base/pitch/root/major
    circles).
    """
    c = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        core.Point3D.create(0.0, 0.0, 0.0), radius_mm * MM_TO_CM
    )
    if construction:
        c.isConstruction = True
    return c


def add_closed_spline(
    sketch: fusion.Sketch, points_mm: List[Point], closed: bool = True
) -> fusion.SketchFittedSpline:
    """Add a fitted spline through ``points_mm`` (mm) as a single curve.

    Uses :class:`adsk.core.ObjectCollection` to gather the sketch points and
    ``sketchFittedSplines.add`` to build the smooth curve.
    """
    oc = core.ObjectCollection.create()
    for (x, y) in points_mm:
        oc.add(_pt(x, y))
    spline = sketch.sketchCurves.sketchFittedSplines.add(oc)
    if closed:
        spline.isClosed = True
    return spline


def add_closed_polyline(sketch: fusion.Sketch, points_mm: List[Point]) -> List[Any]:
    """Add a closed polygon of straight lines through ``points_mm``."""
    lines = []
    n = len(points_mm)
    for i in range(n):
        x0, y0 = points_mm[i]
        x1, y1 = points_mm[(i + 1) % n]
        lines.append(
            sketch.sketchCurves.sketchLines.addByTwoPoints(_pt(x0, y0), _pt(x1, y1))
        )
    return lines


def add_arc_3pt(sketch: fusion.Sketch, p_start: Point, p_mid: Point, p_end: Point):
    """Add a single 3-point arc through start/mid/end (millimetres)."""
    return sketch.sketchCurves.sketchArcs.addByThreePoints(
        _pt(*p_start), _pt(*p_mid), _pt(*p_end)
    )


def add_line(sketch: fusion.Sketch, p_start: Point, p_end: Point):
    """Add a single straight line between two points (millimetres)."""
    return sketch.sketchCurves.sketchLines.addByTwoPoints(_pt(*p_start), _pt(*p_end))


def build_tooth_edges(sketch: fusion.Sketch, edges: List[tuple]) -> List[Any]:
    """Draw a closed loop described as an edge list.

    Each edge is ``("arc", start, mid, end)`` or ``("line", start, end)`` with
    points in millimetres.  This is how involute teeth are drawn: each flank is
    one 3-point arc, the tip/crest lands are arcs, and the root/groove bottom is
    a single straight line, giving tangent-continuous faces with no facets.
    """
    out = []
    for e in edges:
        if e[0] == "arc":
            out.append(add_arc_3pt(sketch, e[1], e[2], e[3]))
        else:
            out.append(add_line(sketch, e[1], e[2]))
    return out


def build_tooth_profile(
    sketch: fusion.Sketch, points_mm: List[Point], use_spline: bool = True
) -> Any:
    """Build the single-tooth (or single-space) closed loop.

    ``use_spline`` selects a fitted-spline loop versus a straight-line polygon.
    Involute teeth should instead be drawn with :func:`build_tooth_edges`.
    """
    if use_spline:
        return add_closed_spline(sketch, points_mm, closed=True)
    return add_closed_polyline(sketch, points_mm)


def build_reference_circles(
    sketch: fusion.Sketch, radii_mm: List[float]
) -> List[fusion.SketchCircle]:
    """Add the base / pitch / root / major bounding circles as construction
    geometry so they never form fillable profiles."""
    return [add_circle(sketch, r, construction=True) for r in radii_mm]


def add_circle_profile(
    component: Any, plane: Any, radius_mm: float
) -> fusion.Profile:
    """Create a sketch holding a single solid circle and return its profile.

    Used to build the base blank (external root cylinder or internal hub
    blank) that the teeth are joined to or cut from.
    """
    sk = component.sketches.add(plane)
    sk.name = "SplineBase"
    add_circle(sk, radius_mm, construction=False)
    return sk.profiles.item(0)
