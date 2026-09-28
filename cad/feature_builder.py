"""
cad.feature_builder
===================

Extrusion, circular patterning and chamfering for the generated spline.

All lengths handed to the API are centimetres (Fusion's internal unit); the
callers pass millimetres and we convert with ``MM_TO_CM``.
"""

from __future__ import annotations

from typing import Any, List

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


def extrude_profile(
    profile: fusion.Profile,
    length_mm: float,
    cut: bool = False,
) -> fusion.ExtrudeFeature:
    """Extrude (boss) or cut a single sketch profile along +Z by ``length_mm``.

    ``cut=True`` produces a subtractive (internal hub) operation.
    """
    comp = profile.parentSketch.parentComponent
    feats = comp.features.extrudeFeatures

    operation = (
        fusion.FeatureOperations.CutFeatureOperation
        if cut
        else fusion.FeatureOperations.NewBodyFeatureOperation
    )
    inp = feats.createInput(profile, operation)
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


def join_to_base(comp: fusion.Component) -> Any:
    """Join every body after the first (the patterned teeth) into the base
    body (index 0) so the shaft is a single connected solid.

    No-op when there is only one body.
    """
    bodies = comp.bRepBodies
    if bodies.count < 2:
        return None
    base = bodies.item(0)
    tools = core.ObjectCollection.create()
    for i in range(1, bodies.count):
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
