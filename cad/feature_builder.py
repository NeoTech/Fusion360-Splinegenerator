"""
cad.feature_builder
===================

Extrusion, circular patterning and chamfering for the generated spline.

All lengths handed to the API are centimetres (Fusion's internal unit); the
callers pass millimetres and we convert with ``MM_TO_CM``.
"""

from __future__ import annotations

from typing import Any, List, Tuple

import adsk.core as core
import adsk.fusion as fusion

MM_TO_CM = 0.1


def _app() -> core.Application:
    return core.Application.get()


def _origin_feature(comp: fusion.Component):
    return comp.parentDesign.origin


def z_axis(comp: fusion.Component) -> Any:
    """The component Z construction axis, used as the pattern axis."""
    return comp.zConstructionAxis


# ---------------------------------------------------------------------------
# Optional target-face placement
# ---------------------------------------------------------------------------
def _object_type(obj: Any) -> str:
    return getattr(obj, "objectType", "") or ""


def add_axis_from_circular_face(comp: fusion.Component, face: Any) -> Any:
    """A construction axis coincident with a cylindrical/conical/toroidal face.

    Parametric-safe (works in both parametric and direct modes).
    """
    axes = comp.constructionAxes
    inp = axes.createInput()
    if not inp.setByCircularFace(face):
        return None
    return axes.add(inp)


def add_plane_perpendicular_to_face(comp: fusion.Component, face: Any) -> Any:
    """A construction plane perpendicular to a cylindrical face's axis.

    This is the cross-section plane the spline profile is sketched on when the
    target is a bore / shaft outer cylinder.
    """
    planes = comp.constructionPlanes
    inp = planes.createInput()
    if not inp.setByPerpendicularToPlane(face, None, None, False):
        return None
    return planes.add(inp)


def add_plane_coincident_with_face(comp: fusion.Component, face: Any) -> Any:
    """A construction plane lying exactly on a planar face (zero offset).

    Sketching directly on a ``BRepFace`` makes Fusion passively project that
    face's boundary edges into the new sketch, which creates extra fillable
    profiles and lets ``profiles.item(0)`` grab the wrong (whole-face) region.
    A coincident construction plane carries no projected geometry, so the only
    profile present is the one we draw.  Parametric-safe via ``setByOffset``.
    """
    planes = comp.constructionPlanes
    inp = planes.createInput()
    zero = core.ValueInput.createByReal(0.0)
    if not inp.setByOffset(face, zero):
        return None
    return planes.add(inp)


def add_axis_normal_to_planar_face(comp: fusion.Component, face: Any) -> Any:
    """A construction axis normal to a planar face, anchored at the centre of a
    circular edge when one exists (the common shaft-end case).

    Returns ``None`` if no circular edge anchors the axis (caller falls back to
    the origin Z axis).
    """
    try:
        edges = list(face.edges)
    except Exception:
        edges = []
    for edge in edges:
        try:
            pts = comp.constructionPoints
            pin = pts.createInput()
            if not pin.setByCenter(edge):
                continue
            center = pts.add(pin)
            axes = comp.constructionAxes
            ain = axes.createInput()
            if ain.setByNormalToFaceAtPoint(face, center):
                return axes.add(ain)
        except Exception:
            continue
    return None


def resolve_target(
    component: fusion.Component, plane: Any, target: Any
) -> Tuple[Any, Any]:
    """Resolve an optional selected face/plane into (sketch_geom, pattern_axis).

    ``target`` is the entity the user picked (a BRepFace or ConstructionPlane),
    or ``None``.  Auto-detects the geometry type:

    * ``None``                       -> (``plane``, origin Z axis)  [default]
    * cylindrical / conical face     -> (perpendicular plane, cylinder axis)
    * planar face                    -> (the face, normal axis through a
      circular-edge centre, else origin Z)
    * construction plane / unknown   -> (the entity, origin Z axis)

    Any failure to build the derived geometry falls back to the default so a
    selection never breaks the whole build.
    """
    if target is None:
        return plane, z_axis(component)

    geom = getattr(target, "geometry", None)
    try:
        if geom is not None and hasattr(geom, "axis") and not hasattr(geom, "normal"):
            # Cylindrical / conical / toroidal face: use its axis + a
            # perpendicular cross-section plane.
            axis = add_axis_from_circular_face(component, target)
            sk_plane = add_plane_perpendicular_to_face(component, target)
            if axis is not None and sk_plane is not None:
                return sk_plane, axis
            return plane, z_axis(component)

        if geom is not None and hasattr(geom, "normal"):
            # Planar face: sketch on a coincident construction plane (never on
            # the raw face, whose outline Fusion would passively project into
            # the sketch and pollute the profile list); axis normal to it
            # (through a circular-edge centre when available).
            axis = add_axis_normal_to_planar_face(component, target)
            sk_plane = add_plane_coincident_with_face(component, target)
            if sk_plane is None:
                sk_plane = target
            return sk_plane, (axis if axis is not None else z_axis(component))
    except Exception:
        return plane, z_axis(component)

    # Construction plane or anything else: sketch on it, keep the origin axis.
    return target, z_axis(component)


def extrude_profile(
    profile: fusion.Profile,
    length_mm: float,
    cut: bool = False,
    symmetric: bool = False,
) -> fusion.ExtrudeFeature:
    """Extrude (boss) or cut a single sketch profile along the sketch normal.

    ``cut=True`` produces a subtractive (internal hub) operation.

    ``symmetric=True`` extrudes equally to both sides of the sketch plane.  For
    a *cut into an existing body* this is the robust choice: the cut reaches
    ``length_mm`` into the material on whichever side the stock actually lies,
    so the user never has to guess a direction (the face normal may point into
    or out of the part).  The total distance is doubled so each side spans the
    requested ``length_mm``.
    """
    comp = profile.parentSketch.parentComponent
    feats = comp.features.extrudeFeatures

    operation = (
        fusion.FeatureOperations.CutFeatureOperation
        if cut
        else fusion.FeatureOperations.NewBodyFeatureOperation
    )
    inp = feats.createInput(profile, operation)
    if symmetric:
        # Symmetric about the profile plane: total = 2 * length so each side
        # (and therefore the depth into the stock) is length_mm.
        inp.setDistanceExtent(
            True, core.ValueInput.createByString(f"{2.0 * length_mm} mm")
        )
    else:
        inp.setDistanceExtent(
            False, core.ValueInput.createByString(f"{length_mm} mm")
        )
    return feats.add(inp)


def circular_pattern(
    feature: fusion.Feature,
    count: int,
    axis: Any,
) -> fusion.CircularPatternFeature:
    """Revolve ``feature`` ``count`` times around ``axis`` (full 360deg)."""
    comp = feature.parentComponent
    pats = comp.features.circularPatternFeatures

    input_obj = core.ObjectCollection.create()
    input_obj.add(feature)

    inp = pats.createInput(input_obj, axis)
    inp.quantity = core.ValueInput.createByString(str(count))
    inp.totalAngle = core.ValueInput.createByString("360 deg")
    inp.isSymmetric = False
    inp.patternComputeOption = (
        fusion.PatternComputeOptions.IdenticalPatternCompute
    )
    return pats.add(inp)


def join_to_base(comp: fusion.Component, start_index: int = 0) -> Any:
    """Join the bodies created by *this* build into the blank it created.

    ``start_index`` is the number of bodies that already existed in the
    component before this build started.  The blank this build extruded is at
    ``start_index`` and its patterned teeth follow it, so only bodies from
    ``start_index`` onward are touched.  Any pre-existing body (e.g. a spline
    already occupying the same space) stays isolated and is never merged in.

    No-op when this build produced only the blank (no separate tooth bodies).
    """
    bodies = comp.bRepBodies
    if bodies.count <= start_index + 1:
        return None
    base = bodies.item(start_index)
    tools = core.ObjectCollection.create()
    for i in range(start_index + 1, bodies.count):
        tools.add(bodies.item(i))
    combine = comp.features.combineFeatures
    inp = combine.createInput(base, tools)
    inp.operation = fusion.FeatureOperations.JoinFeatureOperation
    inp.isKeepToolBodies = False
    return combine.add(inp)


def collect_end_faces(
    body: fusion.BRepBody, z_target_mm: float, tol_mm: float = 1e-3
) -> List[fusion.BRepFace]:
    """Return planar faces lying on the plane ``z == z_target_mm``.

    Uses each face's bounding box to detect the flat end faces of the extruded
    body (the faces to receive the lead-in chamfer).
    """
    z_target_cm = z_target_mm * MM_TO_CM
    tol_cm = tol_mm * MM_TO_CM
    faces: List[fusion.BRepFace] = []
    for face in body.faces:
        try:
            box = face.boundingBox
        except Exception:
            continue
        if (
            abs(box.minPoint.z - z_target_cm) < tol_cm
            and abs(box.maxPoint.z - z_target_cm) < tol_cm
        ):
            faces.append(face)
    return faces


def chamfer_faces(
    comp: fusion.Component,
    faces: List[fusion.BRepFace],
    size_mm: float,
) -> Any:
    """Apply a lead-in chamfer of ``size_mm`` to the supplied faces."""
    if not faces:
        return None
    cham = comp.features.chamferFeatures
    input_obj = core.ObjectCollection.create()
    for f in faces:
        input_obj.add(f)
    return cham.add(
        fusion.ChamferType.DistanceDistanceChamferType,
        size_mm * MM_TO_CM,
        size_mm * MM_TO_CM,
        False,
        input_obj,
        False,
    )
