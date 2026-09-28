"""
cad.builder
===========

High-level orchestration that turns a parameter dictionary into a finished
spline body inside a Fusion 360 component.

This module is deliberately free of UI code so it can be unit-tested with the
``tests.adsk_stub`` fake API.  The add-in entry point
(``Fusion360-SplineGenerator.py``) simply resolves the active component /
construction plane and calls :func:`build_spline`.
"""

from __future__ import annotations

from typing import Any, Dict

import adsk.core as core
import adsk.fusion as fusion

from core import involute_math, parallel_math
from cad import feature_builder, sketch_builder


def _resolve_profile_points(params: Dict[str, Any]):
    """Return (points_mm, use_spline, geometry_radii_mm, key_radii_mm).

    ``key_radii_mm`` is a dict with ``root`` and ``major`` radii in mm used to
    build the base blank / hub body.
    """
    spline_type = params["spline_type"]
    teeth = int(params["teeth"])
    internal = params.get("gender", "external") == "internal"

    if spline_type in ("metric", "imperial"):
        if spline_type == "metric":
            module_mm = float(params["module_mm"])
        else:
            module_mm = involute_math.diametral_pitch_to_module(float(params["dp"]))
        pa = float(params["pressure_angle_deg"])
        x = float(params.get("profile_shift", 0.0))
        root_type = params.get("root_type", "flat")
        cdo = float(params.get("center_distance_offset_mm", 0.0))
        if internal:
            pts = involute_math.internal_space_profile(
                module_mm, teeth, pa, x, root_type=root_type,
                center_distance_offset_mm=cdo,
            )
        else:
            pts = involute_math.external_tooth_profile(
                module_mm, teeth, pa, x, root_type=root_type,
                center_distance_offset_mm=cdo,
            )
        g = involute_math.compute_radii(
            module_mm, teeth, pa, x, internal,
            root_type=root_type, center_distance_offset_mm=cdo,
        )
        radii = [g["root_radius"], g["base_radius"], g["pitch_radius"], g["major_radius"]]
        key = {"root": g["root_radius"], "major": g["major_radius"], "wall": module_mm}
        # Draw the involute tooth as a straight-line polygon (not a fitted
        # spline): a closed spline sags between vertices, which pulls the root
        # inward and leaves a gap against the base cylinder. Straight segments
        # through the flank samples keep the root flat and the faces clean.
        return pts, False, radii, key

    if spline_type == "parallel":
        major = float(params["major_diameter_mm"])
        minor = float(params["minor_diameter_mm"])
        width = float(params.get("tooth_width_mm", 0.0))
        if internal:
            pts = parallel_math.internal_space_profile(major, minor, teeth, width)
        else:
            pts = parallel_math.external_tooth_profile(major, minor, teeth, width)
        g = parallel_math.compute_radii(major, minor, teeth, width)
        radii = [g["minor_radius"], g["pitch_radius"], g["major_radius"]]
        key = {
            "root": g["minor_radius"],
            "major": g["major_radius"],
            "wall": (major - minor) / 2.0,
        }
        return pts, False, radii, key

    raise ValueError(f"Unknown spline_type: {spline_type}")


def build_spline(
    component: fusion.Component,
    plane: Any,
    params: Dict[str, Any],
) -> fusion.Feature:
    """Generate the full spline (one tooth + circular pattern) and return the
    pattern feature.

    ``params`` keys (all lengths in millimetres):
        spline_type : 'metric' | 'imperial' | 'parallel'
        gender      : 'external' | 'internal'
        teeth       : int
        module_mm / dp / pressure_angle_deg / profile_shift  (involute)
        major_diameter_mm / minor_diameter_mm / tooth_width_mm  (parallel)
        length_mm   : extrusion length
        chamfer_mm  : lead-in chamfer size (0 disables)
    """
    points_mm, use_spline, radii_mm, key = _resolve_profile_points(params)
    internal = params.get("gender", "external") == "internal"
    teeth = int(params["teeth"])
    length_mm = float(params["length_mm"])
    chamfer_mm = float(params.get("chamfer_mm", 0.0))

    # 1. Base blank: a solid cylinder at the root radius (external shaft) or
    #    major radius (internal hub).  The teeth are then joined to / cut from
    #    this body so the result is a single connected solid.
    base_radius = key["major"] if internal else key["root"]
    base_profile = sketch_builder.add_circle_profile(component, plane, base_radius)
    feature_builder.extrude_profile(base_profile, length_mm, cut=False)

    # 1b. Internal: bore the centre out to just below the tooth-crest radius
    #     first so the blank becomes a tube; the spaces are then cut into the
    #     tube wall.  Boring slightly below the crest (rather than exactly at
    #     it) keeps a thin solid band behind the teeth and avoids the
    #     tangent-face fragmentation that a crest-radius bore causes.
    if internal:
        bore_profile = sketch_builder.add_circle_profile(
            component, plane, key["root"] * 0.9
        )
        feature_builder.extrude_profile(bore_profile, length_mm, cut=True)

    # 2-4. Sketch: reference circles + a single closed tooth/space loop.
    sketch = sketch_builder.find_or_create_sketch_on(component, plane)
    sketch_builder.build_reference_circles(sketch, radii_mm)
    sketch_builder.build_tooth_profile(sketch, points_mm, use_spline=use_spline)

    profile = sketch.profiles.item(0)

    # 5. Extrude (external tooth boss) or cut (internal space) the single tooth.
    extrude = feature_builder.extrude_profile(profile, length_mm, cut=internal)

    # 6. Circular pattern across z teeth around the Z axis.
    pattern = feature_builder.circular_pattern(
        extrude, teeth, feature_builder.z_axis(component)
    )

    # 6b. External: join the patterned teeth into the root cylinder so the
    #     shaft is one body.  Internal: the bore + space cuts already produced
    #     the toothed ring, so nothing to join.
    if not internal:
        feature_builder.join_to_base(component)

    # 7. Lead-in chamfer on the end faces (best effort).
    if chamfer_mm > 0:
        try:
            body = component.bRepBodies.item(0)
            faces = feature_builder.collect_end_faces(body, length_mm)
            feature_builder.chamfer_faces(component, faces, chamfer_mm)
        except Exception:
            pass  # chamfer is cosmetic; never fail the whole build for it

    return pattern
