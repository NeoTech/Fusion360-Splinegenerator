"""
tests.adsk_stub
===============

A minimal, dependency-free stand-in for the ``adsk.core`` / ``adsk.fusion``
modules.  Importing this package and calling :func:`install` registers fake
``adsk``, ``adsk.core`` and ``adsk.fusion`` modules in ``sys.modules`` so the
CAD layer (``cad.sketch_builder`` / ``cad.feature_builder``) can be imported
and exercised outside of Fusion 360.

The stub records every geometry call (circles, splines, lines, extrudes,
patterns, chamfers) on the created objects so tests can assert on them.
"""

from __future__ import annotations

import sys
import types
from typing import List


# ---------------------------------------------------------------------------
# adsk.core
# ---------------------------------------------------------------------------
class Point3D:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    @staticmethod
    def create(x=0.0, y=0.0, z=0.0):
        return Point3D(x, y, z)

    def __repr__(self):
        return f"Point3D({self.x}, {self.y}, {self.z})"


# ---------------------------------------------------------------------------
# Event-handler base classes + enums referenced at import time by the add-in.
# ---------------------------------------------------------------------------
class _EventHandler:
    def __init__(self):
        self._subs = []

    def add(self, h):
        self._subs.append(h)

    def remove(self, h):
        if h in self._subs:
            self._subs.remove(h)

    def removeNone(self):
        self._subs.clear()


class CommandCreatedEventHandler:
    def notify(self, args):  # pragma: no cover - overridden
        raise NotImplementedError


class CommandEventHandler:
    def notify(self, args):  # pragma: no cover - overridden
        raise NotImplementedError


class CommandInputChangedEventHandler:
    def notify(self, args):  # pragma: no cover - overridden
        raise NotImplementedError


# Real Fusion API name for the command-input-changed handler base class.
class InputChangedEventHandler:
    def notify(self, args):  # pragma: no cover - overridden
        raise NotImplementedError


class ValueInputType:
    LinearValueInputType = 0
    RealValueInputType = 1
    IntegerValueInputType = 2


class ValueInput:
    """Stub mirroring adsk.core.ValueInput.

    ``createByReal`` stores a raw number (used for dimensionless inputs whose
    ``.value`` is read directly). ``createByString`` parses a "<num> <unit>"
    expression and stores it in internal units (cm), matching how a linear
    ValueCommandInput's ``.value`` behaves in real Fusion.
    """

    def __init__(self, internal):
        self._internal = float(internal)

    @staticmethod
    def createByReal(value):
        return ValueInput(value)

    @staticmethod
    def createByString(expr):
        parts = str(expr).split()
        num = float(parts[0])
        unit = parts[1].lower() if len(parts) > 1 else "cm"
        if unit == "mm":
            return ValueInput(num / 10.0)
        if unit == "m":
            return ValueInput(num * 100.0)
        return ValueInput(num)


class DropDownStyle:
    ExpandableDropDownStyle = 0
    ListDropDownStyle = 1


# Real Fusion API uses the plural name ``DropDownStyles``.
class DropDownStyles:
    ExpandableDropDownStyle = 0
    ListDropDownStyle = 1
    TextListDropDownStyle = 2


class _ListItem:
    def __init__(self, name, selected=False, index=0):
        self.name = name
        self.isSelected = selected
        self.index = index


class _ListItems:
    def __init__(self):
        self._items: List[_ListItem] = []

    def add(self, name, selected=False, index=0):
        it = _ListItem(name, selected, index)
        self._items.append(it)
        return it

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _Input:
    def __init__(self, input_id, value=0.0):
        self.id = input_id
        self._value = value
        self.isEnabled = True
        self.isVisible = True
        self.listItems = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = float(v)

    @property
    def expression(self):
        return f"{self._value} cm"

    @expression.setter
    def expression(self, expr):
        # Parse "<number> <unit>" and store in cm (internal unit).
        parts = str(expr).split()
        num = float(parts[0])
        unit = parts[1].lower() if len(parts) > 1 else "cm"
        if unit == "mm":
            self._value = num / 10.0
        elif unit == "m":
            self._value = num * 100.0
        elif unit in ("in", "inch"):
            self._value = num * 2.54
        else:  # cm or unitless
            self._value = num


class _DropDown(_Input):
    def __init__(self, input_id):
        super().__init__(input_id)
        self.listItems = _ListItems()


class _Selection:
    def __init__(self, entity, point=None):
        self.entity = entity
        self.point = point


class _SelectionInput(_Input):
    """Stand-in for adsk.core.SelectionCommandInput."""

    def __init__(self, input_id):
        super().__init__(input_id)
        self._selections: List[_Selection] = []

    def setSelectionLimits(self, min_count, max_count):
        self._min, self._max = min_count, max_count

    def addSelection(self, entity, point=None):
        self._selections.append(_Selection(entity, point))
        return len(self._selections) - 1

    def clearSelection(self):
        self._selections.clear()

    @property
    def selectionCount(self):
        return len(self._selections)

    def selection(self, i):
        return self._selections[i]


class CommandInputs:
    """Minimal command-inputs container for testing the add-in logic."""

    def __init__(self):
        self._inputs = {}
        self._order: List[_Input] = []

    def addDropDownCommandInput(self, input_id, *a, **k):
        inp = _DropDown(input_id)
        self._inputs[input_id] = inp
        self._order.append(inp)
        return inp

    def addSelectionInput(self, input_id, *a, **k):
        inp = _SelectionInput(input_id)
        self._inputs[input_id] = inp
        self._order.append(inp)
        return inp

    def addIntegerSpinnerCommandInput(self, input_id, *a, **k):
        inp = _Input(input_id, value=a[-1] if a else 0)
        self._inputs[input_id] = inp
        self._order.append(inp)
        return inp

    def addRealValueCommandInput(self, input_id, *a, **k):
        # Signature: (Id, Name, Type, Value, Unit, Min, Max) -> value at a[2]
        inp = _Input(input_id, value=a[2] if len(a) > 2 else 0.0)
        self._inputs[input_id] = inp
        self._order.append(inp)
        return inp

    def addFloatSpinnerCommandInput(self, input_id, *a, **k):
        # Signature: (Id, Name, UnitType, Min, Max, SpinStep, InitialValue)
        # -> initial value is the last positional argument.
        inp = _Input(input_id, value=a[-1] if a else 0.0)
        self._inputs[input_id] = inp
        self._order.append(inp)
        return inp

    def addValueInput(self, input_id, name, unit_type, value_input):
        # Signature: (Id, Name, UnitType, ValueInput). The ValueInput carries a
        # value already expressed in internal units (cm) for linear inputs, or a
        # raw number for dimensionless inputs.
        inp = _Input(input_id, value=getattr(value_input, "_internal", 0.0))
        self._inputs[input_id] = inp
        self._order.append(inp)
        return inp

    def itemById(self, input_id):
        return self._inputs.get(input_id)

    def __iter__(self):
        return iter(self._order)


class Point2D:
    def __init__(self, x=0.0, y=0.0):
        self.x, self.y = float(x), float(y)


class ObjectCollection:
    def __init__(self):
        self._items: List[object] = []

    @staticmethod
    def create():
        return ObjectCollection()

    def add(self, item):
        self._items.append(item)
        return len(self._items) - 1

    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _SketchCircle:
    def __init__(self, center: Point3D, radius: float):
        self.center = center
        self.radius = radius
        self.isConstruction = False


class _SketchFittedSpline:
    def __init__(self, points: ObjectCollection):
        self.points = list(points)
        self.isClosed = False


class _SketchLine:
    def __init__(self, start: Point3D, end: Point3D):
        self.startPoint = start
        self.endPoint = end


class _SketchArc:
    def __init__(self, start: Point3D, mid: Point3D, end: Point3D):
        self.startPoint = start
        self.midPoint = mid
        self.endPoint = end


class _SketchCurves:
    def __init__(self):
        self.sketchCircles = _CircleCollection()
        self.sketchFittedSplines = _SplineCollection()
        self.sketchLines = _LineCollection()
        self.sketchArcs = _ArcCollection()


class _CircleCollection:
    def __init__(self):
        self.created: List[_SketchCircle] = []

    def addByCenterRadius(self, center, radius):
        c = _SketchCircle(center, radius)
        self.created.append(c)
        return c


class _SplineCollection:
    def __init__(self):
        self.created: List[_SketchFittedSpline] = []

    def add(self, points):
        s = _SketchFittedSpline(points)
        self.created.append(s)
        return s


class _LineCollection:
    def __init__(self):
        self.created: List[_SketchLine] = []

    def addByTwoPoints(self, p0, p1):
        ln = _SketchLine(p0, p1)
        self.created.append(ln)
        return ln


class _ArcCollection:
    def __init__(self):
        self.created: List[_SketchArc] = []

    def addByThreePoints(self, p0, p1, p2):
        a = _SketchArc(p0, p1, p2)
        self.created.append(a)
        return a


class _Sketch:
    def __init__(self, parent_component, plane=None):
        self.parentComponent = parent_component
        self.sketchCurves = _SketchCurves()
        self._name = "Sketch"
        self.profiles = _Profiles(self)
        self.plane = plane

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value


class _Profile:
    def __init__(self, sketch):
        self.parentSketch = sketch


class _Profiles:
    def __init__(self, sketch):
        self._profile = _Profile(sketch)

    def __iter__(self):
        return iter([self._profile])

    def __len__(self):
        return 1

    def item(self, i):
        return self._profile


class _Sketches:
    def __init__(self, component):
        self._component = component

    def add(self, plane):
        sk = _Sketch(self._component, plane)
        self._component.sketches_list.append(sk)
        return sk


class _Features:
    def __init__(self, component):
        self._component = component
        self.extrudeFeatures = _ExtrudeFeatures(component)
        self.circularPatternFeatures = _CircularPatternFeatures(component)
        self.combineFeatures = _CombineFeatures(component)
        self.chamferFeatures = _ChamferFeatures(component)


class _ExtrudeInput:
    def __init__(self, profile, operation):
        self.profile = profile
        self.operation = operation
        self._distance = 0.0

    def setDistanceExtent(self, symmetric, value_input):
        self._distance = getattr(value_input, "_internal", 0.0)


class _ExtrudeFeatures:
    def __init__(self, component):
        self._component = component
        self.created: List[object] = []

    def createInput(self, profile, operation):
        return _ExtrudeInput(profile, operation)

    def add(self, inp):
        f = types.SimpleNamespace(
            profile=inp.profile, operation=inp.operation,
            distance=inp._distance, parentComponent=self._component,
        )
        self.created.append(f)
        self._component.features_log.append(("extrude", f))
        # A NewBody extrude creates a fresh solid; cut/join do not.
        if inp.operation == FeatureOperations.NewBodyFeatureOperation:
            self._component._bodies += 1
        return f


class _CircularPatternInput:
    def __init__(self, entities, axis):
        self.entities = list(entities)
        self.axis = axis
        self._quantity = 0
        self.totalAngle = None
        self.isSymmetric = False
        self.patternComputeOption = None

    @property
    def quantity(self):
        return self._quantity

    @quantity.setter
    def quantity(self, value_input):
        self._quantity = int(getattr(value_input, "_internal", 0))


class _CircularPatternFeatures:
    def __init__(self, component):
        self._component = component
        self.created: List[object] = []

    def createInput(self, entities, axis):
        return _CircularPatternInput(entities, axis)

    def add(self, inp):
        f = types.SimpleNamespace(
            features=inp.entities, axis=inp.axis, count=inp._quantity,
            parentComponent=self._component,
        )
        self.created.append(f)
        self._component.features_log.append(("circular_pattern", f))
        return f


class _CombineFeatures:
    def __init__(self, component):
        self._component = component
        self.created: List[object] = []

    def createInput(self, target, tools):
        return types.SimpleNamespace(
            target=target, tools=list(tools),
            operation=None, isKeepToolBodies=False,
        )

    def add(self, inp):
        f = types.SimpleNamespace(
            target=inp.target, tools=inp.tools, operation=inp.operation,
            parentComponent=self._component,
        )
        self.created.append(f)
        self._component.features_log.append(("combine", f))
        # Joining collapses the tool bodies into the target.
        self._component._bodies = 1
        return f


class _ChamferFeatures:
    def __init__(self, component):
        self._component = component
        self.created: List[object] = []

    def add(self, ctype, d1, d2, useAll, faces, flip):
        f = types.SimpleNamespace(
            type=ctype, distance1=d1, distance2=d2,
            faces=list(faces), parentComponent=self._component,
        )
        self.created.append(f)
        self._component.features_log.append(("chamfer", f))
        return f


class _Axis:
    def __init__(self, name):
        self.name = name


class _Plane:
    def __init__(self, name):
        self.name = name


class _Origin:
    def __init__(self):
        self.zAxis = _Axis("Z")
        self.xAxis = _Axis("X")
        self.yAxis = _Axis("Y")
        self.xyPlane = _Plane("XY")
        self.yzPlane = _Plane("YZ")
        self.xzPlane = _Plane("XZ")


class _BoundingBox:
    def __init__(self, minz, maxz):
        self.minPoint = types.SimpleNamespace(z=minz)
        self.maxPoint = types.SimpleNamespace(z=maxz)


class _PlanarGeometry:
    """Stand-in for adsk.core.PlanarSurface: exposes .normal only."""

    def __init__(self, normal=(0.0, 0.0, 1.0)):
        self.normal = Point3D(*normal)


class _CylindricalGeometry:
    """Stand-in for adsk.core.CylindricalSurface: exposes .axis, no .normal."""

    def __init__(self, axis=(0.0, 0.0, 1.0)):
        self.axis = Point3D(*axis)
        self.radius = 1.0


class _Edge:
    def __init__(self, kind="line"):
        self.kind = kind


class _Face:
    def __init__(self, minz, maxz, geometry=None, edges=None):
        self.boundingBox = _BoundingBox(minz, maxz)
        self.geometry = geometry
        self.edges = edges if edges is not None else []


class _Faces:
    def __init__(self, faces):
        self._faces = faces

    def __iter__(self):
        return iter(self._faces)


class _Body:
    def __init__(self, faces):
        self.faces = _Faces(faces)


# ---------------------------------------------------------------------------
# Construction geometry (axes / planes / points) for target-face placement.
# ---------------------------------------------------------------------------
class _ConstructionAxisInput:
    def __init__(self, owner):
        self._owner = owner
        self.method = None
        self.entity = None

    def setByCircularFace(self, face):
        self.method, self.entity = "circular", face
        return True

    def setByNormalToFaceAtPoint(self, face, point):
        self.method, self.entity = "normal_face_point", (face, point)
        return True


class _ConstructionAxes:
    def __init__(self, component):
        self._component = component
        self.created: List[_Axis] = []

    def createInput(self):
        return _ConstructionAxisInput(self)

    def add(self, inp):
        ax = _Axis("CAX")
        self.created.append(ax)
        self._component.construction_axes_log.append((inp.method, inp.entity, ax))
        return ax


class _ConstructionPlaneInput:
    def __init__(self, owner):
        self._owner = owner
        self.method = None
        self.entity = None

    def setByPerpendicularToPlane(self, face, distance, ref, use_u):
        self.method, self.entity = "perp", face
        return True

    def setByOffset(self, planar_entity, offset):
        self.method, self.entity = "offset", planar_entity
        return True


class _ConstructionPlanes:
    def __init__(self, component):
        self._component = component
        self.created: List[_Plane] = []

    def createInput(self):
        return _ConstructionPlaneInput(self)

    def add(self, inp):
        pl = _Plane("CPL")
        self.created.append(pl)
        self._component.construction_planes_log.append((inp.method, inp.entity, pl))
        return pl


class _ConstructionPointInput:
    def __init__(self, owner):
        self._owner = owner
        self.method = None
        self.entity = None

    def setByCenter(self, edge):
        self.method, self.entity = "center", edge
        return True


class _ConstructionPoints:
    def __init__(self, component):
        self._component = component
        self.created: List[object] = []

    def createInput(self):
        return _ConstructionPointInput(self)

    def add(self, inp):
        pt = types.SimpleNamespace(entity=inp.entity)
        self.created.append(pt)
        self._component.construction_points_log.append((inp.method, inp.entity, pt))
        return pt


class _Component:
    def __init__(self, design):
        self.parentDesign = design
        self.sketches = _Sketches(self)
        self.features = _Features(self)
        self.sketches_list: List[_Sketch] = []
        self.features_log: List[tuple] = []
        self._bodies = 0
        self.zConstructionAxis = _Axis("Z")
        self.constructionAxes = _ConstructionAxes(self)
        self.constructionPlanes = _ConstructionPlanes(self)
        self.constructionPoints = _ConstructionPoints(self)
        self.construction_axes_log: List[tuple] = []
        self.construction_planes_log: List[tuple] = []
        self.construction_points_log: List[tuple] = []

    @property
    def bodies(self):
        return _Bodies(self)

    @property
    def bRepBodies(self):
        return _Bodies(self)


class _Bodies:
    def __init__(self, component):
        self._component = component

    def item(self, i):
        # Return a body with two end faces at z=0 and z=length (cm).
        length_cm = 0.0
        for kind, f in self._component.features_log:
            if kind == "extrude":
                length_cm = f.distance
        return _Body([_Face(0.0, 0.0), _Face(length_cm, length_cm)])

    @property
    def count(self):
        return self._component._bodies

    def __len__(self):
        return self._component._bodies


class _Design:
    def __init__(self):
        self.origin = _Origin()
        self._root = _Component(self)
        self.activeComponent = self._root

    def components(self):
        return [self._root]


class _Products:
    def __init__(self):
        self.designs = [_Design()]


class _ActiveProduct:
    def __init__(self):
        self.designs = [_Design()]


class Application:
    _instance = None

    def __init__(self):
        self.ActiveProduct = _ActiveProduct()
        self.products = _Products()

    @staticmethod
    def get():
        if Application._instance is None:
            Application._instance = Application()
        return Application._instance

    @staticmethod
    def reset():
        Application._instance = None


# ---------------------------------------------------------------------------
# adsk.fusion enums
# ---------------------------------------------------------------------------
class ProfileFeatureType:
    JoinType = 0
    CutType = 1
    NewBodyOutputType = 2


class FeatureOperations:
    NewBodyFeatureOperation = 0
    JoinFeatureOperation = 1
    CutFeatureOperation = 2
    IntersectFeatureOperation = 3


class PatternComputeOptions:
    FormedPatternCompute = 0
    IdenticalPatternCompute = 1
    OptimalPatternCompute = 2


class PatternFeatureRangeType:
    FullRoundPatternRange = 0
    PartialRoundPatternRange = 1


class ChamferType:
    DistanceDistanceChamferType = 0
    AngleDistanceChamferType = 1


# ---------------------------------------------------------------------------
# Module installation
# ---------------------------------------------------------------------------
def install():
    """Register the stub as ``adsk``, ``adsk.core`` and ``adsk.fusion``."""
    core_mod = sys.modules.setdefault("adsk.core", types.ModuleType("adsk.core"))
    fusion_mod = sys.modules.setdefault("adsk.fusion", types.ModuleType("adsk.fusion"))
    adsk_mod = sys.modules.setdefault("adsk", types.ModuleType("adsk"))

    for name, obj in globals().items():
        if name.startswith("_") or name in ("sys", "types"):
            continue
        setattr(core_mod, name, obj)

    # fusion module only needs the enums + re-export of core basics
    fusion_mod.ProfileFeatureType = ProfileFeatureType
    fusion_mod.FeatureOperations = FeatureOperations
    fusion_mod.PatternComputeOptions = PatternComputeOptions
    fusion_mod.PatternFeatureRangeType = PatternFeatureRangeType
    fusion_mod.ChamferType = ChamferType
    fusion_mod.Component = _Component
    fusion_mod.Sketch = _Sketch
    fusion_mod.Profile = _Profile
    fusion_mod.BRepBody = _Body
    fusion_mod.BRepFace = _Face
    fusion_mod.Plane = _Plane

    adsk_mod.core = core_mod
    adsk_mod.fusion = fusion_mod

    sys.modules["adsk"] = adsk_mod
    sys.modules["adsk.core"] = core_mod
    sys.modules["adsk.fusion"] = fusion_mod
    return adsk_mod
