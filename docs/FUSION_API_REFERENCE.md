# Autodesk Fusion API Comprehensive Reference

**Last Updated:** 2026-03-12
**Official Repository:** https://github.com/AutodeskFusion360/FusionAPIReference
**Official Docs:** https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-A92A4B10-3781-4925-94C6-47DA85A4F65A

---

## Table of Contents

1. [API Overview & Architecture](#1-api-overview--architecture)
2. [Sketch API](#2-sketch-api)
3. [Solid Modeling API](#3-solid-modeling-api)
4. [Component & Assembly API](#4-component--assembly-api)
5. [Construction Geometry API](#5-construction-geometry-api)
6. [Parameters API](#6-parameters-api)
7. [CAM API](#7-cam-api)
8. [Event Handling & Custom Commands](#8-event-handling--custom-commands)
9. [Add-in vs Script](#9-add-in-vs-script)
10. [Data, Import & Export API](#10-data-import--export-api)
11. [Design Mode Switching (Parametric vs Direct)](#11-design-mode-switching-parametric-vs-direct)
12. [Document Management](#12-document-management)
13. [Workspace Switching](#13-workspace-switching)
14. [UI Manipulation](#14-ui-manipulation)
15. [Palettes (Custom HTML Dialogs)](#15-palettes-custom-html-dialogs)
16. [Selection & Active Context](#16-selection--active-context)
17. [Material & Appearance API](#17-material--appearance-api)
18. [Timeline API](#18-timeline-api)
19. [Mesh & T-Spline API](#19-mesh--t-spline-api)
20. [Drawing API](#20-drawing-api)
21. [Simulation & Generative Design API](#21-simulation--generative-design-api)
22. [Rendering API](#22-rendering-api)
23. [Units & Preferences API](#23-units--preferences-api)
24. [Custom Graphics API](#24-custom-graphics-api)
25. [Data & Cloud API](#25-data--cloud-api)
26. [Undo & Transaction Management](#26-undo--transaction-management)
27. [API Availability Summary](#api-availability-summary)

---

## 1. API Overview & Architecture

### Supported Languages

- **Python** (primary language for scripts and add-ins)
- **C++** (full native API access, header files in `Fusion_API_CPP_Reference/include/`)

Python is the most common choice. The API modules are:

```python
import adsk.core      # Core application, UI, geometry, events
import adsk.fusion    # Design, sketches, features, components
import adsk.cam       # CAM operations, setups, toolpaths
import adsk.drawing   # Drawing workspace
```

### Object Model Hierarchy

```
Application (adsk.core.Application)
  +-- documents (Documents)
  |     +-- Document
  |           +-- products
  |                 +-- Design (adsk.fusion.Design)
  |                 +-- CAM (adsk.cam.CAM)
  +-- userInterface (UserInterface)
  +-- importManager (ImportManager)
  +-- data (DataFile access)
  +-- preferences (Preferences)
  +-- materialLibraries

Design (adsk.fusion.Design)
  +-- rootComponent (Component)
  +-- activeComponent (Component)
  +-- allComponents
  +-- allParameters
  +-- userParameters (UserParameters)
  +-- timeline (Timeline)
  +-- exportManager (ExportManager)
  +-- fusionUnitsManager
  +-- designType (ParametricDesignType or DirectDesignType)

Component (adsk.fusion.Component)
  +-- sketches (Sketches)
  +-- features (Features)
  +-- bRepBodies (BRepBodies)
  +-- occurrences (Occurrences)
  +-- joints (Joints)
  +-- asBuiltJoints (AsBuiltJoints)
  +-- jointOrigins (JointOrigins)
  +-- constructionPlanes (ConstructionPlanes)
  +-- constructionAxes (ConstructionAxes)
  +-- constructionPoints (ConstructionPoints)
  +-- modelParameters (ModelParameters)
  +-- material (Material)
  +-- xYConstructionPlane, xZConstructionPlane, yZConstructionPlane
  +-- xConstructionAxis, yConstructionAxis, zConstructionAxis
```

### Core Entry Point Pattern

Every Fusion script/add-in starts the same way:

```python
import adsk.core
import adsk.fusion
import traceback

app = adsk.core.Application.get()
ui = app.userInterface

def run(context):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root_comp = design.rootComponent
        # ... your code here ...
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
```

### Key Application Properties

| Property | Type | Description |
|----------|------|-------------|
| `app.activeProduct` | Product | Currently active product (Design, CAM, etc.) |
| `app.activeDocument` | Document | Currently active document |
| `app.userInterface` | UserInterface | UI access for commands, palettes, dialogs |
| `app.importManager` | ImportManager | Import files |
| `app.documents` | Documents | Open/create documents |
| `app.currentUser` | User | Current logged-in user |
| `app.version` | str | Fusion version string |
| `app.pointTolerance` | float | Geometric tolerance for point comparison |

### Key Application Events (26 total)

- `documentCreated`, `documentOpening`, `documentOpened`
- `documentActivating`, `documentActivated`
- `documentDeactivating`, `documentDeactivated`
- `documentClosing`, `documentClosed`
- `documentSaving`, `documentSaved`
- `startupCompleted`
- `onlineStatusChanged`, `cameraChanged`
- `openingFromURL`, `openedFromURL`
- `insertingFromURL`, `insertedFromURL`

### Internal Units

**All Fusion API values use internal units:**
- Length: **centimeters** (cm)
- Angles: **radians**
- To work with user units, use `fusionUnitsManager` or `unitsManager`

```python
units_mgr = design.fusionUnitsManager
# Convert from user units (e.g., mm) to internal (cm)
internal_val = units_mgr.evaluateExpression('10 mm', 'cm')  # returns 1.0
```

---

## 2. Sketch API

### Creating a Sketch

Sketches are created on a construction plane or planar face:

```python
root_comp = design.rootComponent
sketches = root_comp.sketches

# Create sketch on XY plane
xy_plane = root_comp.xYConstructionPlane
sketch = sketches.add(xy_plane)

# Create sketch on XZ plane
xz_plane = root_comp.xZConstructionPlane
sketch2 = sketches.add(xz_plane)

# Create sketch on a planar face
face = some_body.faces.item(0)
sketch3 = sketches.add(face)
```

### Sketch Class (adsk.fusion.Sketch)

**Key Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `sketchCurves` | SketchCurves | Access to all curve collections (lines, circles, arcs, splines, etc.) |
| `sketchPoints` | SketchPoints | Point collection |
| `sketchDimensions` | SketchDimensions | Dimension collection |
| `geometricConstraints` | GeometricConstraints | Constraint collection |
| `profiles` | Profiles | Computed closed profiles for feature creation |
| `sketchTexts` | SketchTexts | Text entities |
| `name` | str | Sketch name |
| `isVisible` | bool | Visibility |
| `isFullyConstrained` | bool | Whether all geometry is constrained |
| `origin` | Point3D | Sketch origin in model space |
| `transform` | Matrix3D | Sketch-to-model transform |
| `isComputeDeferred` | bool | Defer recompute for batch operations (performance) |
| `referencePlane` | ConstructionPlane/BRepFace | The plane the sketch lives on |

**Key Methods:**
| Method | Description |
|--------|-------------|
| `project2(entity)` | Project geometry onto sketch plane |
| `projectCutEdges(body)` | Intersect body with sketch plane to create curves |
| `intersectWithSketchPlane(entities)` | Intersect entities with sketch plane |
| `importSVG(filename, ...)` | Import SVG into sketch |
| `move(entities, transform)` | Move sketch entities |
| `copy(entities, transform)` | Copy sketch entities |
| `findConnectedCurves(curve)` | Find curves connected at endpoints |
| `modelToSketchSpace(point)` | Convert model coords to sketch coords |
| `sketchToModelSpace(point)` | Convert sketch coords to model coords |
| `saveAsDXF(filename)` | Export sketch as DXF (retired) |
| `deleteMe()` | Delete the sketch |
| `redefine(plane)` | Move sketch to different plane |
| `setConstructionState(curves, isConstruction)` | Set construction state |
| `setCenterlineState(lines, isCenterline)` | Set centerline state |

### Sketch Curves (adsk.fusion.SketchCurves)

Access sub-collections via:

```python
lines = sketch.sketchCurves.sketchLines
circles = sketch.sketchCurves.sketchCircles
arcs = sketch.sketchCurves.sketchArcs
ellipses = sketch.sketchCurves.sketchEllipses
splines = sketch.sketchCurves.sketchFittedSplines
fixed_splines = sketch.sketchCurves.sketchFixedSplines
conic_curves = sketch.sketchCurves.sketchConicCurves
```

### SketchLines (adsk.fusion.SketchLines)

| Method | Description |
|--------|-------------|
| `addByTwoPoints(pt1, pt2)` | Line between two points (Point3D or SketchPoint) |
| `addTwoPointRectangle(pt1, pt2)` | Rectangle from opposing corners (returns 4 lines) |
| `addCenterPointRectangle(center, corner)` | Rectangle from center + corner |
| `addThreePointRectangle(pt1, pt2, pt3)` | Rectangle: base edge + height point |
| `addEdgePolygon(pt1, pt2, sides)` | Regular polygon defined by one edge |
| `addScribedPolygon(center, vertex, sides, inscribed)` | Inscribed/circumscribed polygon |
| `addAngleChamfer(line1, line2, ...)` | Chamfer between two lines by angle |
| `addDistanceChamfer(line1, line2, ...)` | Chamfer between two lines by distance |

```python
# Create a rectangle
lines = sketch.sketchCurves.sketchLines
pt0 = adsk.core.Point3D.create(0, 0, 0)
pt1 = adsk.core.Point3D.create(5, 3, 0)  # 5cm x 3cm
rect_lines = lines.addTwoPointRectangle(pt0, pt1)

# Create individual lines
line1 = lines.addByTwoPoints(
    adsk.core.Point3D.create(0, 0, 0),
    adsk.core.Point3D.create(5, 0, 0)
)
```

### SketchCircles (adsk.fusion.SketchCircles)

| Method | Description |
|--------|-------------|
| `addByCenterRadius(center, radius)` | Circle by center point and radius |
| `addByTwoPoints(pt1, pt2)` | Circle where distance between points = diameter |
| `addByThreePoints(pt1, pt2, pt3)` | Circle through three points |
| `addByThreeTangents(line1, line2, line3)` | Circle tangent to three lines |
| `addByTwoTangents(line1, line2)` | Circle tangent to two lines |

```python
circles = sketch.sketchCurves.sketchCircles
center = adsk.core.Point3D.create(0, 0, 0)
circle = circles.addByCenterRadius(center, 2.5)  # radius 2.5 cm
```

### SketchArcs (adsk.fusion.SketchArcs)

| Method | Description |
|--------|-------------|
| `addByThreePoints(pt1, pt2, pt3)` | Arc through three points |
| `addByCenterStartEnd(center, start, end)` | Arc by center, start, end points |
| `addByCenterStartSweep(center, start, sweepAngle)` | Arc by center, start, sweep angle |
| `addFillet(curve1, curve2, radius)` | Fillet arc between two curves |

```python
arcs = sketch.sketchCurves.sketchArcs
arc = arcs.addByThreePoints(
    adsk.core.Point3D.create(0, 0, 0),
    adsk.core.Point3D.create(1, 1, 0),
    adsk.core.Point3D.create(2, 0, 0)
)

# Create fillet between two lines
fillet = arcs.addFillet(line1, line2, 0.5)  # 0.5 cm radius
```

### SketchFittedSplines (adsk.fusion.SketchFittedSplines)

| Method | Description |
|--------|-------------|
| `add(points)` | Fitted spline through an ObjectCollection of Point3D |

```python
splines = sketch.sketchCurves.sketchFittedSplines
points = adsk.core.ObjectCollection.create()
points.add(adsk.core.Point3D.create(0, 0, 0))
points.add(adsk.core.Point3D.create(1, 2, 0))
points.add(adsk.core.Point3D.create(3, 1, 0))
points.add(adsk.core.Point3D.create(5, 3, 0))
spline = splines.add(points)
```

### Sketch Dimensions (adsk.fusion.SketchDimensions)

| Method | Description |
|--------|-------------|
| `addDistanceDimension(entity1, entity2, orientation, textPoint)` | Linear distance dimension |
| `addDiameterDimension(circle_or_arc, textPoint)` | Diameter dimension |
| `addRadialDimension(circle_or_arc, textPoint)` | Radial dimension |
| `addAngularDimension(line1, line2, textPoint)` | Angular dimension between lines |
| `addConcentricCircleDimension(circle1, circle2, textPoint)` | Between concentric circles |
| `addEllipseMajorRadiusDimension(ellipse, textPoint)` | Ellipse major radius |
| `addEllipseMinorRadiusDimension(ellipse, textPoint)` | Ellipse minor radius |
| `addOffsetDimension(line, entity, textPoint)` | Offset perpendicular to line |
| `addLinearDiameterDimension(centerline, entity, textPoint)` | Linear diameter dimension |
| `addTangentDistanceDimension(line, circle1, circle2, textPoint)` | Tangent distance |

```python
dims = sketch.sketchDimensions
text_pt = adsk.core.Point3D.create(2.5, -1, 0)

# Distance dimension between two lines
dim = dims.addDistanceDimension(
    line1.startSketchPoint,
    line2.startSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    text_pt
)

# Diameter dimension on a circle
dim2 = dims.addDiameterDimension(circle, adsk.core.Point3D.create(3, 3, 0))

# Set dimension value via parameter
dim.parameter.expression = '25 mm'
```

### Geometric Constraints (adsk.fusion.GeometricConstraints)

| Method | Description |
|--------|-------------|
| `addCoincident(entity1, entity2)` | Coincident (point-to-point or point-to-curve) |
| `addCoincidentToSurface(point, surface)` | Point on surface |
| `addCollinear(line1, line2)` | Collinear lines |
| `addConcentric(circle1, circle2)` | Concentric circles/arcs |
| `addEqual(entity1, entity2)` | Equal length/radius |
| `addHorizontal(line)` | Horizontal constraint |
| `addHorizontalPoints(pt1, pt2)` | Horizontal alignment of points |
| `addVertical(line)` | Vertical constraint |
| `addVerticalPoints(pt1, pt2)` | Vertical alignment of points |
| `addParallel(line1, line2)` | Parallel lines |
| `addPerpendicular(line1, line2)` | Perpendicular lines |
| `addTangent(curve1, curve2)` | Tangent curves |
| `addSmooth(curve1, curve2)` | Smooth connection (needs spline) |
| `addMidPoint(point, curve)` | Midpoint constraint |
| `addSymmetry(entity1, entity2, symmetryLine)` | Symmetry |
| `addOffset2(curves, directionPoint, offset)` | Offset curves |
| `addLineOnPlanarSurface(line, face)` | Line on surface |
| `addLineParallelToPlanarSurface(line, face)` | Line parallel to surface |
| `addPerpendicularToSurface(curve, face)` | Perpendicular to surface |
| `addPolygon(lines)` | Polygon constraint on lines |
| `createCircularPatternInput(entities, center)` | Circular pattern input |
| `createRectangularPatternInput(entities, ...)` | Rectangular pattern input |

```python
constraints = sketch.geometricConstraints

# Make a line horizontal
constraints.addHorizontal(line1)

# Make two lines perpendicular
constraints.addPerpendicular(line1, line2)

# Add coincident constraint
constraints.addCoincident(line1.endSketchPoint, line2.startSketchPoint)

# Add tangent constraint
constraints.addTangent(arc1, line1)
```

### Profiles

After creating closed sketch geometry, profiles are auto-computed:

```python
# Get the first profile (closed region)
profile = sketch.profiles.item(0)

# Get all profiles
for i in range(sketch.profiles.count):
    profile = sketch.profiles.item(i)
```

### Performance Tip: Deferred Compute

```python
sketch.isComputeDeferred = True  # Pause recomputes
# ... add lots of geometry ...
sketch.isComputeDeferred = False  # Recompute once
```

---

## 3. Solid Modeling API

All features are accessed via `component.features`:

```python
features = root_comp.features
```

### Features Collection (adsk.fusion.Features)

The Features object provides access to 80+ feature type collections. Key ones:

**Parametric Modeling:**
- `extrudeFeatures`, `revolveFeatures`, `sweepFeatures`, `loftFeatures`
- `holeFeatures`, `threadFeatures`
- `filletFeatures`, `chamferFeatures`
- `shellFeatures`, `draftFeatures`
- `combineFeatures`
- `mirrorFeatures`, `circularPatternFeatures`, `rectangularPatternFeatures`, `pathPatternFeatures`
- `scaleFeatures`, `moveFeatures`, `splitBodyFeatures`, `splitFaceFeatures`

**Surface Features:**
- `patchFeatures`, `ruledSurfaceFeatures`, `boundaryFillFeatures`
- `offsetFeatures`, `thickenFeatures`, `stitchFeatures`, `unstitchFeatures`
- `trimFeatures`, `untrimFeatures`, `extendFeatures`
- `replaceFaceFeatures`, `deleteFaceFeatures`, `offsetFacesFeatures`

**Primitives:**
- `boxFeatures`, `cylinderFeatures`, `sphereFeatures`, `torusFeatures`
- `coilFeatures`, `pipeFeatures`, `ribFeatures`, `webFeatures`

**Sheet Metal:**
- `flangeFeatures`, `hemFeatures`, `ripFeatures`
- `unfoldFeatures`, `refoldFeatures`

**Mesh:**
- `meshConvertFeatures`, `meshRepairFeatures`, `meshReduceFeatures`
- `meshSmoothFeatures`, `meshSeparateFeatures`, `meshShellFeatures`

**Utility Methods:**
- `createPath(curves)` - Create a Path for sweep/loft operations

### FeatureOperations Enum

```python
adsk.fusion.FeatureOperations.NewBodyFeatureOperation      # Create new body
adsk.fusion.FeatureOperations.JoinFeatureOperation         # Boolean union (join)
adsk.fusion.FeatureOperations.CutFeatureOperation          # Boolean subtract (cut)
adsk.fusion.FeatureOperations.IntersectFeatureOperation    # Boolean intersect
adsk.fusion.FeatureOperations.NewComponentFeatureOperation # New component
```

### Extrude Feature

```python
extrudes = root_comp.features.extrudeFeatures

# --- Simple extrude ---
profile = sketch.profiles.item(0)
distance = adsk.core.ValueInput.createByReal(2.0)  # 2 cm
extrude = extrudes.addSimple(profile, distance,
    adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

# --- Full extrude with input object ---
extrude_input = extrudes.createInput(profile,
    adsk.fusion.FeatureOperations.JoinFeatureOperation)

# One-side extent
distance_def = adsk.fusion.DistanceExtentDefinition.create(
    adsk.core.ValueInput.createByReal(3.0))
extrude_input.setOneSideExtent(distance_def,
    adsk.fusion.ExtentDirections.PositiveExtentDirection)

# Symmetric extent
extrude_input.setSymmetricExtent(
    adsk.core.ValueInput.createByReal(2.0), True)  # 2cm each side

# Two-side extent
extrude_input.setTwoSidesExtent(
    adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(1.0)),
    adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(2.0)))

# To-object extent
extrude_input.setOneSideToExtent(
    adsk.fusion.ToEntityExtentDefinition.create(face, False))

# All extent
extrude_input.setOneSideExtent(
    adsk.fusion.AllExtentDefinition.create(),
    adsk.fusion.ExtentDirections.PositiveExtentDirection)

# Add taper angle
extrude_input.taperAngleOne = adsk.core.ValueInput.createByString('5 deg')

extrude_feature = extrudes.add(extrude_input)
```

### Revolve Feature

```python
revolves = root_comp.features.revolveFeatures

# Create input: profile + axis line + operation
rev_input = revolves.createInput(profile, axis_line,
    adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

# Full revolution (360 degrees)
angle = adsk.core.ValueInput.createByReal(2 * 3.14159265)
rev_input.setAngleExtent(False, angle)

# Partial revolution
angle = adsk.core.ValueInput.createByString('180 deg')
rev_input.setAngleExtent(False, angle)

revolve_feature = revolves.add(rev_input)
```

### Sweep Feature

```python
sweeps = root_comp.features.sweepFeatures

# Create path from sketch curves
path = features.createPath(path_curve)

# Basic sweep input (profile + path)
sweep_input = sweeps.createInput(profile, path,
    adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

# Optional: set orientation
sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType

# Optional: add guide rail
# sweep_input.guideRail = guide_path

sweep_feature = sweeps.add(sweep_input)
```

### Loft Feature

```python
lofts = root_comp.features.loftFeatures

loft_input = lofts.createInput(
    adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

# Add loft sections (profiles on different planes)
loft_input.loftSections.add(profile1)
loft_input.loftSections.add(profile2)

# Optional: add rails, center line
# loft_input.centerLineOrRails.addCenterLine(center_curve)

loft_feature = lofts.add(loft_input)
```

### Boolean / Combine Feature

```python
combines = root_comp.features.combineFeatures

# Collect tool bodies
tool_bodies = adsk.core.ObjectCollection.create()
tool_bodies.add(tool_body)

combine_input = combines.createInput(target_body, tool_bodies)
combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
# Options: JoinFeatureOperation (0), CutFeatureOperation (1), IntersectFeatureOperation (2)
combine_input.isKeepToolBodies = False  # Remove tool bodies after operation
combine_input.isNewComponent = False

combine_feature = combines.add(combine_input)
```

### Fillet Feature

```python
fillets = root_comp.features.filletFeatures

fillet_input = fillets.createInput()

# Add edges with constant radius
edges = adsk.core.ObjectCollection.create()
edges.add(edge1)
edges.add(edge2)
fillet_input.addConstantRadiusEdgeSet(edges,
    adsk.core.ValueInput.createByReal(0.3), True)  # 0.3 cm = 3mm radius

# Variable radius fillet
# fillet_input.addVariableRadiusEdgeSet(edges, startRadius, endRadius, positions, radii, True)

fillet_feature = fillets.add(fillet_input)

# Full round fillet
full_round_input = fillets.createFullRoundFilletInput()
# full_round_input.addFullRoundFilletEdgeSet(side1, centerEdges, side2)
```

### Chamfer Feature

```python
chamfers = root_comp.features.chamferFeatures

# Equal distance chamfer
chamfer_input = chamfers.createInput2()
edges = adsk.core.ObjectCollection.create()
edges.add(edge1)
chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
    edges, adsk.core.ValueInput.createByReal(0.2), True)

chamfer_feature = chamfers.add(chamfer_input)
```

### Shell Feature

```python
shells = root_comp.features.shellFeatures

# Shell with selected faces removed
faces = adsk.core.ObjectCollection.create()
faces.add(top_face)
shell_input = shells.createInput(faces)
shell_input.insideThickness = adsk.core.ValueInput.createByReal(0.2)  # 2mm wall

shell_feature = shells.add(shell_input)
```

### Mirror Feature

```python
mirrors = root_comp.features.mirrorFeatures

# Mirror bodies
bodies_to_mirror = adsk.core.ObjectCollection.create()
bodies_to_mirror.add(body)

mirror_input = mirrors.createInput(bodies_to_mirror, mirror_plane)
mirror_input.isCombine = False  # Keep as separate body

mirror_feature = mirrors.add(mirror_input)
```

### Pattern Features

```python
# Rectangular pattern
rect_patterns = root_comp.features.rectangularPatternFeatures
input_entities = adsk.core.ObjectCollection.create()
input_entities.add(body_or_feature)

rect_input = rect_patterns.createInput(input_entities,
    root_comp.xConstructionAxis,
    adsk.core.ValueInput.createByReal(3),    # count
    adsk.core.ValueInput.createByReal(2.0),  # spacing (2cm)
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)

# Add second direction
rect_input.setDirectionTwo(
    root_comp.yConstructionAxis,
    adsk.core.ValueInput.createByReal(2),    # count
    adsk.core.ValueInput.createByReal(2.0))  # spacing

rect_feature = rect_patterns.add(rect_input)

# Circular pattern
circ_patterns = root_comp.features.circularPatternFeatures
circ_input = circ_patterns.createInput(input_entities,
    root_comp.zConstructionAxis)
circ_input.quantity = adsk.core.ValueInput.createByReal(6)
circ_input.totalAngle = adsk.core.ValueInput.createByString('360 deg')

circ_feature = circ_patterns.add(circ_input)
```

### Split Body Feature

```python
split_bodies = root_comp.features.splitBodyFeatures
split_input = split_bodies.createInput(
    body_to_split,
    splitting_entity,  # face, plane, or surface
    True)  # keep both sides

split_feature = split_bodies.add(split_input)
```

---

## 4. Component & Assembly API

### Component Hierarchy

In Fusion, designs are structured as:
- **Root Component** - The top-level component (always exists)
- **Sub-Components** - Referenced via Occurrences
- **Occurrences** - Instances of components (can reference same component multiple times)

```python
design = adsk.fusion.Design.cast(app.activeProduct)
root_comp = design.rootComponent

# All components in the design
for comp in design.allComponents:
    print(comp.name)
```

### Component Class Key Properties

| Property | Description |
|----------|-------------|
| `name` | Component name |
| `id` | Persistent unique identifier |
| `sketches` | Sketches collection |
| `features` | Features collection |
| `bRepBodies` | B-Rep solid/surface bodies |
| `meshBodies` | Mesh bodies |
| `occurrences` | Child occurrences (top-level only) |
| `allOccurrences` | All occurrences at any depth |
| `joints` | Joints in component |
| `asBuiltJoints` | As-built joints |
| `jointOrigins` | Joint origins |
| `constructionPlanes/Axes/Points` | Construction geometry |
| `modelParameters` | Parameters from features |
| `material` | Physical material |
| `opacity` | 0.0-1.0 opacity override |
| `partNumber` | Part number string |
| `description` | Component description |

### Creating New Components

```python
# Method 1: Create via occurrence
transform = adsk.core.Matrix3D.create()  # identity = origin
new_occ = root_comp.occurrences.addNewComponent(transform)
new_comp = new_occ.component
new_comp.name = 'MyComponent'

# Method 2: Feature creates new component
extrude_input = extrudes.createInput(profile,
    adsk.fusion.FeatureOperations.NewComponentFeatureOperation)
```

### Occurrences (adsk.fusion.Occurrence)

An Occurrence is an instance of a Component placed in the assembly.

| Property/Method | Description |
|----------------|-------------|
| `component` | The referenced component |
| `transform2` | 3D matrix for position/orientation (get/set) |
| `name` | Instance name in browser |
| `fullPathName` | Full path in assembly hierarchy |
| `isActive` | Whether currently being edited |
| `activate()` | Enter editing this component |
| `isGrounded` | Whether pinned in place |
| `isReferencedComponent` | Whether referencing external file |
| `childOccurrences` | Sub-occurrences |
| `bRepBodies` | Body proxies in this context |
| `joints` | Joint proxies |
| `isLightBulbOn` | Visibility |
| `breakLink()` | Convert external reference to local |
| `replace(newComponent)` | Replace with different component |

```python
# Place a component multiple times
occ1 = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
comp = occ1.component
comp.name = 'Part1'

# Create second instance of same component
transform = adsk.core.Matrix3D.create()
transform.translation = adsk.core.Vector3D.create(10, 0, 0)
occ2 = root_comp.occurrences.addExistingComponent(comp, transform)

# Move an occurrence
mat = occ1.transform2
mat.translation = adsk.core.Vector3D.create(5, 5, 0)
occ1.transform2 = mat
design.snapshots.add()  # Important: snapshot to finalize position
```

### 4.1 JointGeometry — Defining Joint Positions

`JointGeometry` is a transient object defining where a joint is positioned, created via static factory methods.

#### Static Creation Methods

**`createByPoint(point)`** — from `ConstructionPoint`, `SketchPoint`, or `BRepVertex`

```python
geo = adsk.fusion.JointGeometry.createByPoint(sketchPoint)
```

**`createByPlanarFace(face, edge, keyPointType)`** — from a planar `BRepFace`

```python
geo = adsk.fusion.JointGeometry.createByPlanarFace(
    endFace, None, adsk.fusion.JointKeyPointTypes.CenterKeyPoint)
```

**`createByCurve(curve, keyPointType)`** — from `BRepEdge` or `SketchCurve`

```python
geo = adsk.fusion.JointGeometry.createByCurve(
    sketchLine, adsk.fusion.JointKeyPointTypes.MiddleKeyPoint)
```

**`createByNonPlanarFace(face, keyPointType)`** — from cylindrical, conical, spherical, or toroidal `BRepFace`

```python
geo = adsk.fusion.JointGeometry.createByNonPlanarFace(
    cylFace, adsk.fusion.JointKeyPointTypes.MiddleKeyPoint)
```

**`createByProfile(profile, sketchCurve, keyPointType)`** — from a sketch `Profile`

**`createByCylinderOrConeFace(face, angle, height)`** — from cylindrical/conical face with quadrant angle

```python
geo = adsk.fusion.JointGeometry.createByCylinderOrConeFace(
    cylFace,
    adsk.fusion.JointQuadrantAngleTypes.StartJointQuadrantAngleType,
    adsk.fusion.JointKeyPointTypes.MiddleKeyPoint)
```

**`createBySphereFace(face, azimuthAngle, polarAngle)`** — from spherical face

**`createByTorusFace(face, azimuthAngle, sectionAngle)`** — from toroidal face

**`createBySplineFace(face, paramU, paramV)`** — from spline face

**`createByTangentFaceEdge(face, edge, edgePointType)`** — from tangent face/edge pair

**`createByBetweenTwoPlanes(planeOne, planeTwo, entityOne, entityTwo, keyPointType)`** — midpoint between two planes

**`createByTwoEdgeIntersection(edgeOne, edgeTwo)`** — from two intersecting linear edges

#### JointGeometry Properties (read-only)

| Property | Type | Description |
|---|---|---|
| `origin` | `Point3D` | Calculated origin point |
| `primaryAxisVector` | `Vector3D` | Z-axis direction |
| `secondaryAxisVector` | `Vector3D` | X-axis direction |
| `thirdAxisVector` | `Vector3D` | Y-axis direction |
| `entityOne` | varies | First defining entity |
| `entityTwo` | varies | Second defining entity (or None) |
| `geometryType` | `JointGeometryTypes` | Type enum |
| `keyPointType` | `JointKeyPointTypes` | Key point type |

#### Key Enumerations

**`JointKeyPointTypes`**: `StartKeyPoint` (0), `MiddleKeyPoint` (1), `EndKeyPoint` (2), `CenterKeyPoint` (3)

**`JointQuadrantAngleTypes`**: `StartJointQuadrantAngleType` (0), `QuarterJointQuadrantAngleType` (1), `MiddleJointQuadrantAngleType` (2), `ThirdQuarterJointQuadrantAngleType` (3)

**`JointDirections`**: `XAxisJointDirection` (0), `YAxisJointDirection` (1), `ZAxisJointDirection` (2), `CustomJointDirection` (3)

### 4.2 Joints (adsk.fusion.Joints)

Joints define mechanical relationships between components. Creating a joint snaps the first component to align with the second.

#### JointInput — Configuration

Created via `joints.createInput(geometryOrOriginOne, geometryOrOriginTwo)` where each argument is a `JointGeometry` or `JointOrigin`.

| Property | Type | Description |
|---|---|---|
| `angle` | ValueInput | Angle between geometries (radians or expression). Default 0 |
| `offset` | ValueInput | Offset between geometries (cm or expression). Default 0 |
| `isFlipped` | bool | Flip joint direction |
| `geometryOrOriginOne` | JointGeometry/JointOrigin | First geometry |
| `geometryOrOriginTwo` | JointGeometry/JointOrigin | Second geometry |

#### Motion Type Methods (on JointInput)

```python
jointInput.setAsRigidJointMotion()

jointInput.setAsRevoluteJointMotion(rotationAxis, customRotationAxisEntity=None)

jointInput.setAsSliderJointMotion(sliderDirection, customSliderDirectionEntity=None)

jointInput.setAsCylindricalJointMotion(rotationAxis, customRotationAxisEntity=None)

jointInput.setAsBallJointMotion(pitchDirection, yawDirection, customPitch=None, customYaw=None)

jointInput.setAsPlanarJointMotion(normalDirection, customNormal=None, customPrimarySlide=None)

jointInput.setAsPinSlotJointMotion(rotationAxis, slideDirection, customRot=None, customSlide=None)
```

#### Creating a Joint

```python
joints = rootComp.joints
jointInput = joints.createInput(geo1, geo2)
jointInput.setAsRevoluteJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
jointInput.angle = adsk.core.ValueInput.createByString('0 deg')
jointInput.offset = adsk.core.ValueInput.createByString('1 cm')
jointInput.isFlipped = True
joint = joints.add(jointInput)
```

#### Joint Object Properties (post-creation)

| Property | Type | Access | Description |
|---|---|---|---|
| `name` | str | Get/Set | Display name |
| `jointMotion` | JointMotion | Get | Motion object (cast to specific type) |
| `isLocked` | bool | Get/Set | Lock/unlock the joint |
| `isSuppressed` | bool | Get/Set | Suppress/unsuppress |
| `isFlipped` | bool | Get/Set | Flip direction |
| `isLightBulbOn` | bool | Get/Set | Browser visibility toggle |
| `healthState` | FeatureHealthStates | Get | Healthy/Warning/Error |
| `errorOrWarningMessage` | str | Get | Message when unhealthy |
| `angle` | Parameter | Get | Angle parameter |
| `offset` | Parameter | Get | Offset parameter |
| `occurrenceOne` | Occurrence | Get | First occurrence |
| `occurrenceTwo` | Occurrence | Get | Second occurrence |
| `geometryOrOriginOne` | JointGeometry/JointOrigin | Get/Set | First geometry |
| `geometryOrOriginTwo` | JointGeometry/JointOrigin | Get/Set | Second geometry |
| `motionLinks` | MotionLinks | Get | Associated motion links |
| `entityToken` | str | Get | Persistent token for `findEntityByToken()` |
| `timelineObject` | TimelineObject | Get | Timeline entry |

Existing joints can change motion type via `joint.setAsRevoluteJointMotion(...)`, etc.

### 4.3 JointMotion Types

All accessed via `joint.jointMotion`, cast to specific type.

#### JointTypes Enum

| Value | Int | DOF | Motion Properties |
|---|---|---|---|
| `RigidJointType` | 0 | 0 | None |
| `RevoluteJointType` | 1 | 1 | rotationValue, rotationLimits |
| `SliderJointType` | 2 | 1 | slideValue, slideLimits |
| `CylindricalJointType` | 3 | 2 | rotationValue + slideValue |
| `PinSlotJointType` | 4 | 2 | rotationValue + slideValue (different axes) |
| `PlanarJointType` | 5 | 3 | primarySlideValue + secondarySlideValue + rotationValue |
| `BallJointType` | 6 | 3 | pitchValue + yawValue + rollValue |

#### RevoluteJointMotion (1 DOF: rotation)

| Property | Type | Access | Description |
|---|---|---|---|
| `rotationAxis` | JointDirections | Get/Set | Axis of rotation |
| `rotationAxisVector` | Vector3D | Get | Direction vector |
| `rotationValue` | float (radians) | Get/Set | Current rotation — setting this drives the joint |
| `rotationLimits` | JointLimits | Get | Min/max/rest limits |
| `customRotationAxisEntity` | Entity | Get/Set | Custom axis entity |

```python
revMotion = adsk.fusion.RevoluteJointMotion.cast(joint.jointMotion)
revMotion.rotationValue = math.pi / 2  # 90 degrees
```

#### SliderJointMotion (1 DOF: translation)

| Property | Type | Access | Description |
|---|---|---|---|
| `slideDirection` | JointDirections | Get/Set | Slide axis |
| `slideValue` | float (cm) | Get/Set | Current slide distance |
| `slideLimits` | JointLimits | Get | Min/max/rest limits |

```python
sliderMotion = adsk.fusion.SliderJointMotion.cast(joint.jointMotion)
sliderMotion.slideValue = 5.0  # 5 cm
```

#### CylindricalJointMotion (2 DOF: rotation + translation along same axis)

| Property | Type | Access |
|---|---|---|
| `rotationValue` | float (radians) | Get/Set |
| `rotationLimits` | JointLimits | Get |
| `slideValue` | float (cm) | Get/Set |
| `slideLimits` | JointLimits | Get |

#### BallJointMotion (3 DOF: pitch, yaw, roll)

| Property | Type | Access |
|---|---|---|
| `pitchValue` | float (radians) | Get/Set |
| `pitchLimits` | JointLimits | Get |
| `yawValue` | float (radians) | Get/Set |
| `yawLimits` | JointLimits | Get |
| `rollValue` | float (radians) | Get/Set |
| `rollLimits` | JointLimits | Get |

#### PlanarJointMotion (3 DOF: 2 translations + 1 rotation on a plane)

| Property | Type | Access |
|---|---|---|
| `primarySlideValue` | float (cm) | Get/Set |
| `primarySlideLimits` | JointLimits | Get |
| `secondarySlideValue` | float (cm) | Get/Set |
| `secondarySlideLimits` | JointLimits | Get |
| `rotationValue` | float (radians) | Get/Set |
| `rotationLimits` | JointLimits | Get |

#### PinSlotJointMotion (2 DOF: rotation + translation on different axes)

| Property | Type | Access |
|---|---|---|
| `rotationValue` | float (radians) | Get/Set |
| `rotationLimits` | JointLimits | Get |
| `slideValue` | float (cm) | Get/Set |
| `slideLimits` | JointLimits | Get |

### 4.4 JointLimits

Every DOF has a `JointLimits` object with:

| Property | Type | Access | Description |
|---|---|---|---|
| `isMinimumValueEnabled` | bool | Get/Set | Enable minimum limit |
| `minimumValue` | float | Get/Set | Min (cm for distance, radians for angle) |
| `isMaximumValueEnabled` | bool | Get/Set | Enable maximum limit |
| `maximumValue` | float | Get/Set | Max (cm or radians) |
| `isRestValueEnabled` | bool | Get/Set | Enable rest/home value |
| `restValue` | float | Get/Set | Rest value (cm or radians) |

```python
import math
revMotion = adsk.fusion.RevoluteJointMotion.cast(joint.jointMotion)
limits = revMotion.rotationLimits
limits.isMinimumValueEnabled = True
limits.minimumValue = math.radians(-90)
limits.isMaximumValueEnabled = True
limits.maximumValue = math.radians(90)
limits.isRestValueEnabled = True
limits.restValue = 0.0
```

### 4.5 As-Built Joints (adsk.fusion.AsBuiltJoints)

Define motion between components **already positioned correctly** — no snapping occurs.

- **Regular Joint**: snaps component 1 to component 2 at the joint geometry
- **As-Built Joint**: components stay where they are

```python
asBuiltJoints = rootComp.asBuiltJoints

# Rigid as-built joint (geometry=None)
abjInput = asBuiltJoints.createInput(occ1, occ2, None)
asBuiltJoint = asBuiltJoints.add(abjInput)

# Revolute as-built joint
geo = adsk.fusion.JointGeometry.createByNonPlanarFace(
    cylFace, adsk.fusion.JointKeyPointTypes.MiddleKeyPoint)
abjInput = asBuiltJoints.createInput(occ1, occ2, geo)
abjInput.setAsRevoluteJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
asBuiltJoint = asBuiltJoints.add(abjInput)
```

`AsBuiltJoint` has the same `jointMotion`, `isLocked`, `isSuppressed`, `name`, `motionLinks`, `setAs*()` methods as `Joint`.

### 4.6 Joint Origins (adsk.fusion.JointOrigins)

Persistent reusable connection points stored in the component.

```python
jointOrigins = component.jointOrigins
joInput = jointOrigins.createInput(jointGeometry)
joInput.offsetX = adsk.core.ValueInput.createByString('5 mm')
joInput.offsetZ = adsk.core.ValueInput.createByString('10 mm')
joInput.angle = adsk.core.ValueInput.createByString('45 deg')
joInput.isFlipped = False
jointOrigin = jointOrigins.add(joInput)
```

| Property | Type | Access | Description |
|---|---|---|---|
| `geometry` | JointGeometry | Get/Set | Location geometry |
| `angle` | Parameter | Get | Angle parameter |
| `offsetX/Y/Z` | Parameter | Get | Offset parameters |
| `isFlipped` | bool | Get/Set | Flipped state |
| `xAxisEntity` | Entity | Get/Set | X axis entity |
| `zAxisEntity` | Entity | Get/Set | Z axis entity |
| `transform` | Matrix3D | Get | Position/orientation matrix |
| `primaryAxisVector` | Vector3D | Get | Z-axis direction |

### 4.7 Motion Links

Synchronize motion between two joints (or two DOFs within the same multi-DOF joint).

```python
motionLinks = rootComp.motionLinks
mlInput = motionLinks.createInput(revoluteJoint, sliderJoint)
mlInput.valueOne = adsk.core.ValueInput.createByString('360 deg')
mlInput.valueTwo = adsk.core.ValueInput.createByString('10 cm')
mlInput.isReversed = False
motionLink = motionLinks.add(mlInput)

# Link two DOFs within a single cylindrical joint
mlInput = motionLinks.createInput(cylindricalJoint)  # jointTwo=None
motionLink = motionLinks.add(mlInput)
```

| Property | Type | Access | Description |
|---|---|---|---|
| `jointOne` | Joint/AsBuiltJoint | Get | First joint |
| `jointTwo` | Joint/AsBuiltJoint | Get | Second joint (or None for same-joint link) |
| `valueOne/Two` | ModelParameter | Get | Motion parameters |
| `isReversed` | bool | Get/Set | Reverse direction |
| `isSuppressed` | bool | Get/Set | Suppression state |
| `name` | str | Get/Set | Display name |

### 4.8 Driving Joints Programmatically

Setting motion values is equivalent to the "Drive Joints" command.

```python
# Drive to specific angle
revMotion = adsk.fusion.RevoluteJointMotion.cast(joint.jointMotion)
revMotion.rotationValue = math.radians(45)

# Animation loop
for i in range(360):
    revMotion.rotationValue = math.radians(i)
    adsk.doEvents()  # update viewport

# Animate cylindrical joint (rotation + slide)
cylMotion = adsk.fusion.CylindricalJointMotion.cast(joint.jointMotion)
for i in range(360):
    fraction = i / 360.0
    cylMotion.rotationValue = 2 * math.pi * fraction
    cylMotion.slideValue = 4.0 * fraction
    adsk.doEvents()
```

### 4.9 Contact Sets

Groups of components/bodies for contact analysis. Affects simulation behavior, no real-time collision query.

```python
objs = adsk.core.ObjectCollection.create()
objs.add(occurrence1)
objs.add(occurrence2)
contactSet = design.contactSets.add(objs)
contactSet.name = 'Gear Mesh'
```

| Property | Type | Access | Description |
|---|---|---|---|
| `name` | str | Get/Set | Display name |
| `isSuppressed` | bool | Get/Set | Suppression state |
| `occurencesAndBodies` | ObjectCollection | Get/Set | Members (note: Autodesk typo in property name) |

### 4.10 Rigid Groups

Lock a set of occurrences to move as one unit.

```python
occs = adsk.core.ObjectCollection.create()
occs.add(occ1)
occs.add(occ2)
occs.add(occ3)
rigidGroup = rootComp.rigidGroups.add(occs, True)  # True = include children
rigidGroup.name = 'Frame Assembly'
```

| Property | Type | Access | Description |
|---|---|---|---|
| `name` | str | Get/Set | Display name |
| `isSuppressed` | bool | Get/Set | Suppress/unsuppress |
| `occurrences` | OccurrenceList | Get | Member occurrences |
| `setOccurrences(occs, includeChildren)` | method | | Replace members |

### 4.11 Complete Joint Example

```python
import adsk.core, adsk.fusion, math

app = adsk.core.Application.get()
design = adsk.fusion.Design.cast(app.activeProduct)
rootComp = design.rootComponent

# Create joint geometry on two components
endFace = ext1.endFaces.item(0)
geo1 = adsk.fusion.JointGeometry.createByPlanarFace(
    endFace, None, adsk.fusion.JointKeyPointTypes.CenterKeyPoint)

cylFace = ext2.sideFaces.item(0)
geo2 = adsk.fusion.JointGeometry.createByNonPlanarFace(
    cylFace, adsk.fusion.JointKeyPointTypes.StartKeyPoint)

# Create revolute joint
joints = rootComp.joints
jointInput = joints.createInput(geo1, geo2)
jointInput.setAsRevoluteJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
joint = joints.add(jointInput)
joint.name = 'Hinge'

# Set limits
revMotion = adsk.fusion.RevoluteJointMotion.cast(joint.jointMotion)
limits = revMotion.rotationLimits
limits.isMinimumValueEnabled = True
limits.minimumValue = math.radians(-90)
limits.isMaximumValueEnabled = True
limits.maximumValue = math.radians(90)
limits.isRestValueEnabled = True
limits.restValue = 0.0

# Animate
for i in range(181):
    revMotion.rotationValue = math.radians(-90 + i)
    adsk.doEvents()

# Lock
joint.isLocked = True
```

---

## 5. Construction Geometry API

### Construction Planes (adsk.fusion.ConstructionPlanes)

```python
planes = root_comp.constructionPlanes
plane_input = planes.createInput()
```

**11 creation methods on ConstructionPlaneInput:**

| Method | Description |
|--------|-------------|
| `setByOffset(planarEntity, offset)` | Offset from plane/face by distance |
| `setByAngle(linearEntity, angle, planarEntity)` | Through edge at angle to plane |
| `setByTwoEdges(edge1, edge2)` | Through two coplanar edges |
| `setByThreePoints(pt1, pt2, pt3)` | Through three points |
| `setByTangent(face, point)` | Tangent to cylindrical/conical face |
| `setByTangentAtPoint(face, point)` | Tangent to face at point |
| `setByTwoPlanes(plane1, plane2)` | Midplane between two planes |
| `setByDistanceOnPath(path, distance)` | Normal to path at distance |
| `setByOffsetThroughPoint(plane, point)` | Offset plane through specific point |
| `setByPlane(plane)` | From Plane object (direct modeling only) |

```python
# Offset plane
plane_input = planes.createInput()
offset = adsk.core.ValueInput.createByReal(5.0)  # 5cm offset
plane_input.setByOffset(root_comp.xYConstructionPlane, offset)
offset_plane = planes.add(plane_input)

# Angle plane
plane_input2 = planes.createInput()
angle = adsk.core.ValueInput.createByString('45 deg')
plane_input2.setByAngle(edge, angle, root_comp.xYConstructionPlane)
angle_plane = planes.add(plane_input2)

# Midplane between two faces
plane_input3 = planes.createInput()
plane_input3.setByTwoPlanes(face1, face2)
mid_plane = planes.add(plane_input3)
```

### Construction Axes (adsk.fusion.ConstructionAxes)

```python
axes = root_comp.constructionAxes
axis_input = axes.createInput()
```

**Creation methods on ConstructionAxisInput:**

| Method | Description |
|--------|-------------|
| `setByTwoPoints(pt1, pt2)` | Axis through two points |
| `setByLine(infiniteLine)` | From InfiniteLine3D (direct only) |
| `setByCircularFace(face)` | Through center of circular face |
| `setByNormalToFaceAtPoint(face, point)` | Normal to face at point |
| `setByEdge(edge)` | Along an edge |
| `setByTwoPlanes(plane1, plane2)` | Intersection of two planes |
| `setByPerpendicularAtPoint(face, point)` | Perpendicular to face at point |

```python
axis_input = axes.createInput()
axis_input.setByTwoPoints(
    adsk.core.Point3D.create(0, 0, 0),
    adsk.core.Point3D.create(0, 0, 10))
custom_axis = axes.add(axis_input)
```

### Construction Points (adsk.fusion.ConstructionPoints)

```python
points = root_comp.constructionPoints
point_input = points.createInput()
```

**Creation methods:**

| Method | Description |
|--------|-------------|
| `setByPoint(point)` | At a specific Point3D |
| `setByEdgeAndPlane(edge, plane)` | Intersection of edge and plane |
| `setByTwoEdges(edge1, edge2)` | Intersection of two edges |
| `setByThreePlanes(p1, p2, p3)` | Intersection of three planes |
| `setByCenterOfCircularFace(face)` | Center of circular face |

### Existing Origin Geometry

Every component has built-in origin geometry:

```python
comp.xYConstructionPlane   # XY plane
comp.xZConstructionPlane   # XZ plane
comp.yZConstructionPlane   # YZ plane
comp.xConstructionAxis     # X axis
comp.yConstructionAxis     # Y axis
comp.zConstructionAxis     # Z axis
comp.originConstructionPoint  # Origin point
```

---

## 6. Parameters API

Fusion has two types of parameters:

### User Parameters

User-defined variables that can drive dimensions:

```python
user_params = design.userParameters

# Create a new user parameter
user_params.add('width', adsk.core.ValueInput.createByReal(5.0), 'cm', 'Width of the box')
user_params.add('height', adsk.core.ValueInput.createByString('25 mm'), 'mm', 'Box height')

# Access existing parameter
param = user_params.itemByName('width')
param.expression = '30 mm'
param.value  # returns value in internal units (cm)
param.comment = 'Updated width'

# Iterate all user parameters
for i in range(user_params.count):
    p = user_params.item(i)
    print(f'{p.name} = {p.expression} ({p.value} cm)')

# Export/Import CSV
user_params.exportUserParameters('/path/to/params.csv')
user_params.importUserParameters('/path/to/params.csv')

# Use all parameters (user + model combined)
all_params = design.allParameters
```

### Model Parameters

Parameters created automatically by features (dimensions):

```python
# Access model parameters on a component
model_params = root_comp.modelParameters

for i in range(model_params.count):
    p = model_params.item(i)
    print(f'{p.name}: {p.expression} = {p.value}')

# Modify a model parameter
param = model_params.itemByName('d1')  # e.g., sketch dimension
param.expression = '50 mm'

# Use user parameter expressions in dimensions
param.expression = 'width * 2'  # references user parameter 'width'
```

### Bulk Parameter Modification

```python
# More efficient than modifying one at a time
params_to_modify = [
    ('d1', '10 mm'),
    ('d2', '20 mm'),
    ('width', '50 mm')
]
# Use design.modifyParameters() for batch updates
param_list = []
for name, expr in params_to_modify:
    param = design.allParameters.itemByName(name)
    if param:
        param_list.append((param, expr))
```

### Units Manager

```python
units_mgr = design.fusionUnitsManager
default_units = units_mgr.defaultLengthUnits  # e.g., 'mm'

# Evaluate expression to internal units
value = units_mgr.evaluateExpression('25.4 mm', 'cm')  # returns 2.54

# Format internal value to display string
display = units_mgr.formatInternalValue(2.54, 'mm', True)  # '25.4 mm'
```

### ValueInput Helper

```python
# By real number (internal units = cm for length, radians for angles)
vi = adsk.core.ValueInput.createByReal(2.5)

# By string expression (with units)
vi = adsk.core.ValueInput.createByString('25 mm')
vi = adsk.core.ValueInput.createByString('45 deg')
vi = adsk.core.ValueInput.createByString('width + 10 mm')  # parameter expression
```

---

## 7. CAM API

The CAM API (`adsk.cam`) provides access to manufacturing operations.

### CAM Object (adsk.cam.CAM)

```python
# Access CAM product
cam = adsk.cam.CAM.cast(app.activeProduct)
# OR from document:
doc = app.activeDocument
cam = adsk.cam.CAM.cast(doc.products.itemByProductType('CAMProductType'))

# Switch to CAM workspace
cam_ws = ui.workspaces.itemById('CAMEnvironment')
cam_ws.activate()
```

### Key CAM Properties

| Property | Description |
|----------|-------------|
| `setups` | Collection of manufacturing setups |
| `allOperations` | All operations including nested |
| `ncPrograms` | NC program collection |
| `allMachines` | All machines |
| `documentToolLibrary` | Tool library for document |
| `genericPostFolder` | System post folder |
| `personalPostFolder` | User's post folder |
| `temporaryFolder` | Temp file folder |

### Key CAM Methods

| Method | Description |
|--------|-------------|
| `generateToolpath(operations)` | Generate toolpaths (returns GenerateToolpathFuture) |
| `generateAllToolpaths()` | Generate all toolpaths |
| `clearToolpath(operations)` | Clear toolpaths |
| `clearAllToolpaths()` | Clear all toolpaths |
| `checkToolpath(operations)` | Validate operations |
| `checkValidity()` | Check for model changes |
| `getMachiningTime(operations)` | Calculate machining time |
| `generateSetupSheet(operations)` | Generate setup sheets |
| `generateAllSetupSheets()` | Generate all setup sheets |

### Creating a Setup

```python
setups = cam.setups
setup_input = setups.createInput(adsk.cam.OperationTypes.MillingOperation)

# Add models
models = [part_body]
setup_input.models = models

setup = setups.add(setup_input)
setup.name = 'My Setup'

# Configure stock
setup.stockMode = adsk.cam.SetupStockModes.RelativeBoxStock
setup.parameters.itemByName('job_stockOffsetMode').expression = "'simple'"
setup.parameters.itemByName('job_stockOffsetSides').expression = '0 mm'
setup.parameters.itemByName('job_stockOffsetTop').expression = '1 mm'

# Set WCS origin
setup.parameters.itemByName('wcs_origin_boxPoint').value.value = 'top 1'
```

### Creating Operations

```python
# Face operation
input = setup.operations.createInput('face')
input.tool = face_tool
input.displayName = 'Face Operation'
input.parameters.itemByName('tolerance').expression = '0.01 mm'
input.parameters.itemByName('stepover').expression = '0.75 * tool_diameter'
input.parameters.itemByName('direction').expression = "'climb'"
face_op = setup.operations.add(input)

# Adaptive roughing
input = setup.operations.createInput('adaptive')
input.tool = roughing_tool
input.displayName = 'Adaptive Roughing'
input.parameters.itemByName('tolerance').expression = '0.1 mm'
input.parameters.itemByName('maximumStepdown').expression = '5 mm'
adaptive_op = setup.operations.add(input)

# Parallel finishing
input = setup.operations.createInput('parallel')
input.tool = finishing_tool
input.displayName = 'Parallel Finishing'
input.parameters.itemByName('tolerance').expression = '0.01 mm'
parallel_op = setup.operations.add(input)

# Steep and shallow (requires Manufacturing Extension)
input = setup.operations.createInput('steep_and_shallow')
input.tool = finishing_tool
input.parameters.itemByName('tolerance').expression = '0.01 mm'
steep_op = setup.operations.add(input)
```

### Tool Library Access

```python
cam_manager = adsk.cam.CAMManager.get()
library_manager = cam_manager.libraryManager
tool_libraries = library_manager.toolLibraries

# Get Fusion 360 library folder
fusion_folder = tool_libraries.urlByLocation(
    adsk.cam.LibraryLocations.Fusion360LibraryLocation)

# Load a specific library
url = adsk.core.URL.create('systemlibraryroot://Samples/Milling Tools (Metric).json')
tool_library = tool_libraries.toolLibraryAtURL(url)

# Query tools
query = tool_library.createQuery()
query.criteria.add('tool_type', adsk.core.ValueInput.createByString('bull nose end mill'))
query.criteria.add('tool_diameter.min', adsk.core.ValueInput.createByReal(1.2))
results = query.query()
for result in results:
    tool = result.tool
```

### Toolpath Generation

```python
operations = adsk.core.ObjectCollection.create()
operations.add(face_op)
operations.add(adaptive_op)

# Generate toolpaths (async)
future = cam.generateToolpath(operations)

# Wait for completion
while not future.isGenerationCompleted:
    adsk.doEvents()  # Allow UI to update

# Check number completed
print(f'Completed: {future.numberOfCompleted}/{future.numberOfOperations}')
```

### Post-Processing & NC Programs

```python
# Get post library
post_library = library_manager.postLibrary

# Query for post processors
post_query = post_library.createQuery(adsk.cam.LibraryLocations.Fusion360LibraryLocation)
post_query.vendor = "Autodesk"
post_query.capability = adsk.cam.PostCapabilities.Milling
post_configs = post_query.query()

# Create NC program
nc_input = cam.ncPrograms.createInput()
nc_input.displayName = 'My NC Program'

nc_params = nc_input.parameters
nc_params.itemByName('nc_program_filename').value.value = 'output'
nc_params.itemByName('nc_program_output_folder').value.value = '~/Desktop'

nc_input.operations = [face_op, adaptive_op, parallel_op]
nc_program = cam.ncPrograms.add(nc_input)

# Set post processor and generate
nc_program.postConfiguration = post_config
nc_program.postProcess()
```

### CAM Events

- `setupActivated` / `setupActivating`
- `setupDeactivated` / `setupDeactivating`
- `setupChanged`
- `setupCreated`
- `setupDestroying`

---

## 8. Event Handling & Custom Commands

### Command Architecture

Fusion commands follow this lifecycle:
1. **CommandCreated** - UI button clicked, create dialog inputs
2. **InputChanged** - User changes an input value
3. **ValidateInputs** - Validate current input state
4. **Execute** / **ExecutePreview** - Perform the operation
5. **Destroy** - Cleanup

### Creating a Custom Command (Add-in Pattern)

```python
import adsk.core
import adsk.fusion
import os
import traceback

app = adsk.core.Application.get()
ui = app.userInterface

# Global handler lists (prevent garbage collection)
handlers = []

CMD_ID = 'myUniqueCommandId'
CMD_NAME = 'My Command'
CMD_DESC = 'Description of my command'

WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
IS_PROMOTED = True
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')


class MyCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            # Add command inputs (dialog controls)
            default_units = app.activeProduct.unitsManager.defaultLengthUnits

            inputs.addValueInput('length', 'Length', default_units,
                adsk.core.ValueInput.createByString('10 mm'))
            inputs.addValueInput('width', 'Width', default_units,
                adsk.core.ValueInput.createByString('5 mm'))
            inputs.addBoolValueInput('hollow', 'Make Hollow', True, '', False)
            inputs.addDropDownCommandInput('material', 'Material',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            inputs.addSelectionInput('face_select', 'Select Face', 'Select a face')

            # Connect event handlers
            on_execute = MyExecuteHandler()
            cmd.execute.add(on_execute)
            handlers.append(on_execute)

            on_input_changed = MyInputChangedHandler()
            cmd.inputChanged.add(on_input_changed)
            handlers.append(on_input_changed)

            on_validate = MyValidateInputsHandler()
            cmd.validateInputs.add(on_validate)
            handlers.append(on_validate)

            on_destroy = MyDestroyHandler()
            cmd.destroy.add(on_destroy)
            handlers.append(on_destroy)

        except:
            ui.messageBox(traceback.format_exc())


class MyExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            inputs = args.command.commandInputs
            length_input = adsk.core.ValueCommandInput.cast(inputs.itemById('length'))
            width_input = adsk.core.ValueCommandInput.cast(inputs.itemById('width'))

            length = length_input.value  # internal units (cm)
            width = width_input.value

            # Perform your operation here
            design = adsk.fusion.Design.cast(app.activeProduct)
            # ... create geometry ...

        except:
            ui.messageBox(traceback.format_exc())


class MyInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.InputChangedEventArgs):
        try:
            changed_input = args.input
            if changed_input.id == 'hollow':
                # React to input changes
                pass
        except:
            ui.messageBox(traceback.format_exc())


class MyValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            inputs = args.inputs
            # Set args.areInputsValid = False to disable OK button
            args.areInputsValid = True
        except:
            ui.messageBox(traceback.format_exc())


class MyDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        handlers.clear()


def run(context):
    try:
        # Cleanup previous instance
        old_def = ui.commandDefinitions.itemById(CMD_ID)
        if old_def:
            old_def.deleteMe()

        # Create command definition
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESC, ICON_FOLDER)

        # Connect created handler
        on_created = MyCommandCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        handlers.append(on_created)

        # Add to UI panel
        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        panel = workspace.toolbarPanels.itemById(PANEL_ID)

        old_control = panel.controls.itemById(CMD_ID)
        if old_control:
            old_control.deleteMe()

        control = panel.controls.addCommand(cmd_def)
        control.isPromoted = IS_PROMOTED

    except:
        ui.messageBox(traceback.format_exc())


def stop(context):
    try:
        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        if workspace:
            panel = workspace.toolbarPanels.itemById(PANEL_ID)
            if panel:
                control = panel.controls.itemById(CMD_ID)
                if control:
                    control.deleteMe()
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        handlers.clear()
    except:
        ui.messageBox(traceback.format_exc())
```

### CommandInputs Types Reference

| Method | Input Type | Description |
|--------|-----------|-------------|
| `addValueInput(id, name, units, default)` | ValueCommandInput | Numeric value with units |
| `addBoolValueInput(id, name, isCheckbox, resource, default)` | BoolValueCommandInput | Checkbox or button |
| `addStringValueInput(id, name, default)` | StringValueCommandInput | Text input |
| `addSelectionInput(id, name, tooltip)` | SelectionCommandInput | Entity selection |
| `addDropDownCommandInput(id, name, style)` | DropDownCommandInput | Dropdown list |
| `addFloatSpinnerCommandInput(id, name, units, min, max, step, default)` | FloatSpinnerCommandInput | Float spinner |
| `addIntegerSpinnerCommandInput(id, name, min, max, step, default)` | IntegerSpinnerCommandInput | Integer spinner |
| `addFloatSliderCommandInput(id, name, units, min, max)` | FloatSliderCommandInput | Slider |
| `addIntegerSliderCommandInput(id, name, min, max)` | IntegerSliderCommandInput | Integer slider |
| `addButtonRowCommandInput(id, name, isMultiSelect)` | ButtonRowCommandInput | Button row |
| `addRadioButtonGroupCommandInput(id, name)` | RadioButtonGroupCommandInput | Radio buttons |
| `addGroupCommandInput(id, name)` | GroupCommandInput | Collapsible group |
| `addTabCommandInput(id, name)` | TabCommandInput | Tab container |
| `addTableCommandInput(id, name, columns, rows)` | TableCommandInput | Table |
| `addImageCommandInput(id, name, imagePath)` | ImageCommandInput | Image display |
| `addTextBoxCommandInput(id, name, text, rows, isReadOnly)` | TextBoxCommandInput | Multi-line text |
| `addBrowserCommandInput(id, name, url)` | BrowserCommandInput | Web browser |
| `addDirectionCommandInput(id, name)` | DirectionCommandInput | Direction picker |
| `addDistanceValueCommandInput(id, name, default)` | DistanceValueCommandInput | Distance with manipulator |
| `addAngleValueCommandInput(id, name, default)` | AngleValueCommandInput | Angle with manipulator |
| `addTriadCommandInput(id, name)` | TriadCommandInput | 3D manipulator |
| `addSeparatorCommandInput(id)` | SeparatorCommandInput | Visual divider |

### Custom Events (Thread Communication)

```python
# Register custom event (from main thread)
custom_event = app.registerCustomEvent('MyCustomEventId')
on_custom = MyCustomEventHandler()
custom_event.add(on_custom)
handlers.append(on_custom)

# Fire from worker thread
app.fireCustomEvent('MyCustomEventId', 'additional_info_string')

# Handler receives in main thread
class MyCustomEventHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args: adsk.core.CustomEventArgs):
        info = args.additionalInfo
        # Safe to access Fusion API here (main thread)

# Cleanup
app.unregisterCustomEvent('MyCustomEventId')
```

### Available Workspaces

| Workspace ID | Description |
|-------------|-------------|
| `FusionSolidEnvironment` | Design (modeling) |
| `CAMEnvironment` | Manufacturing (CAM) |
| `FusionRenderEnvironment` | Render |
| `SimulationEnvironment` | Simulation |
| `FusionDrawingEnvironment` | Drawing |

### Common Panel IDs (Design workspace)

| Panel ID | Description |
|----------|-------------|
| `SolidScriptsAddinsPanel` | Scripts and Add-ins panel |
| `SolidCreatePanel` | Create panel |
| `SolidModifyPanel` | Modify panel |
| `ConstructPanel` | Construct panel |
| `InspectPanel` | Inspect panel |
| `InsertPanel` | Insert panel |

---

## 9. Add-in vs Script

### Scripts

- **Run once** and exit
- Single `run(context)` function
- No UI persistence (buttons disappear after execution)
- Simpler structure
- Good for one-off operations

**Script structure:**

```
MyScript/
  MyScript.py
  MyScript.manifest
```

**MyScript.py:**
```python
import adsk.core, adsk.fusion, traceback

app = adsk.core.Application.get()
ui = app.userInterface

def run(context):
    try:
        # Your code here
        ui.messageBox('Hello from script!')
    except:
        ui.messageBox(traceback.format_exc())
```

### Add-ins

- **Run persistently** (start on Fusion launch, optionally)
- Has both `run(context)` and `stop(context)` functions
- Adds **persistent UI elements** (buttons, panels)
- Event-driven architecture
- Can register commands and handle events continuously

**Add-in structure:**
```
MyAddin/
  MyAddin.py
  MyAddin.manifest
  resources/
    16x16.png
    32x32.png
    64x64.png
```

**Add-in requires both run() and stop():**
```python
def run(context):
    # Create UI elements, register commands
    pass

def stop(context):
    # Clean up UI elements, unregister commands
    pass
```

### Manifest File Format

```json
{
    "autodeskProduct": "Fusion360",
    "type": "addin",
    "id": "unique-uuid-here",
    "author": "Your Name",
    "description": {
        "": "Description of the add-in"
    },
    "version": "1.0",
    "runOnStartup": false,
    "supportedOS": "windows|mac",
    "editEnabled": true
}
```

For scripts, change `"type": "script"`.

The `"id"` must be a unique UUID. Generate with:
```python
import uuid
print(uuid.uuid4())
```

### Installation Locations

**Scripts:**
- Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts`
- Mac: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Scripts`

**Add-ins:**
- Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns`
- Mac: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`

### Key Differences Summary

| Feature | Script | Add-in |
|---------|--------|--------|
| Entry point | `run()` only | `run()` + `stop()` |
| Persistence | Runs once, exits | Stays loaded |
| UI elements | Temporary | Persistent buttons/commands |
| Auto-start | No | Optional (`runOnStartup`) |
| Manifest type | `"script"` | `"addin"` |
| Use case | Quick tasks, automation | Tools, custom commands |

---

## 10. Data, Import & Export API

### Export Manager (adsk.fusion.ExportManager)

```python
export_mgr = design.exportManager
```

**Supported export formats:**

| Method | Format | Description |
|--------|--------|-------------|
| `createSTEPExportOptions(filename)` | STEP (.step/.stp) | Standard CAD exchange |
| `createIGESExportOptions(filename)` | IGES (.igs/.iges) | Legacy CAD exchange |
| `createSATExportOptions(filename)` | SAT (.sat) | ACIS kernel format |
| `createSMTExportOptions(filename)` | SMT (.smt) | Autodesk shape format |
| `createSTLExportOptions(body, filename)` | STL (.stl) | Mesh/3D printing |
| `createFusionArchiveExportOptions(filename)` | F3D (.f3d) | Fusion native archive |
| `createC3MFExportOptions(body, filename)` | 3MF (.3mf) | 3D Manufacturing Format |
| `createOBJExportOptions(body, filename)` | OBJ (.obj) | Wavefront 3D |
| `createUSDExportOptions(filename)` | USD (.usd) | Universal Scene Description |
| `createDXFSketchExportOptions(sketch, filename)` | DXF (.dxf) | 2D sketch export |
| `createDXFFlatPatternExportOptions(filename)` | DXF (.dxf) | Sheet metal flat pattern |

```python
# Export as STEP
step_options = export_mgr.createSTEPExportOptions('/path/to/output.step')
export_mgr.execute(step_options)

# Export as STL
body = root_comp.bRepBodies.item(0)
stl_options = export_mgr.createSTLExportOptions(body, '/path/to/output.stl')
stl_options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
export_mgr.execute(stl_options)

# Export as F3D archive
f3d_options = export_mgr.createFusionArchiveExportOptions('/path/to/output.f3d')
export_mgr.execute(f3d_options)

# Export as 3MF
c3mf_options = export_mgr.createC3MFExportOptions(body, '/path/to/output.3mf')
export_mgr.execute(c3mf_options)

# Export sketch as DXF
dxf_options = export_mgr.createDXFSketchExportOptions(sketch, '/path/to/output.dxf')
export_mgr.execute(dxf_options)
```

### Import Manager (adsk.core.ImportManager)

```python
import_mgr = app.importManager
```

**Supported import formats:**

| Method | Format | Description |
|--------|--------|-------------|
| `createSTEPImportOptions(filename)` | STEP | Standard CAD |
| `createIGESImportOptions(filename)` | IGES | Legacy CAD |
| `createSATImportOptions(filename)` | SAT | ACIS kernel |
| `createSMTImportOptions(filename)` | SMT | Autodesk shape |
| `createFusionArchiveImportOptions(filename)` | F3D | Fusion archive |
| `createDXF2DImportOptions(filename, plane)` | DXF | 2D to sketch |
| `createSVGImportOptions(filename)` | SVG | Vector to sketch |

```python
# Import STEP file to new document
step_options = import_mgr.createSTEPImportOptions('/path/to/file.step')
import_mgr.importToNewDocument(step_options)

# Import STEP into existing component
step_options = import_mgr.createSTEPImportOptions('/path/to/file.step')
import_mgr.importToTarget(step_options, root_comp)

# Import DXF into sketch (must use importToTarget)
dxf_options = import_mgr.createDXF2DImportOptions('/path/to/file.dxf',
    root_comp.xYConstructionPlane)
import_mgr.importToTarget(dxf_options, root_comp)

# Import SVG into sketch
svg_options = import_mgr.createSVGImportOptions('/path/to/file.svg')
import_mgr.importToTarget(svg_options, root_comp)
```

### Accessing Design Data

```python
# Active document
doc = app.activeDocument

# Document name and data file
doc.name
doc.dataFile  # DataFile object for cloud data

# All open documents
for i in range(app.documents.count):
    d = app.documents.item(i)
    print(d.name)

# Create new document
new_doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)

# Save (cloud save)
doc.save('Save description')

# Close
doc.close(False)  # False = don't save
```

### BRepBody Access

```python
# Get all bodies in root component
bodies = root_comp.bRepBodies
for i in range(bodies.count):
    body = bodies.item(i)
    print(f'Body: {body.name}')
    print(f'  Faces: {body.faces.count}')
    print(f'  Edges: {body.edges.count}')
    print(f'  Vertices: {body.vertices.count}')
    print(f'  Volume: {body.volume} cm^3')
    print(f'  Is solid: {body.isSolid}')

# Physical properties
props = root_comp.getPhysicalProperties(
    adsk.fusion.CalculationAccuracy.MediumCalculationAccuracy)
print(f'Mass: {props.mass} kg')
print(f'Volume: {props.volume} cm^3')
print(f'Area: {props.area} cm^2')
print(f'Center of mass: {props.centerOfMass.x}, {props.centerOfMass.y}, {props.centerOfMass.z}')
```

---

## Appendix A: Common Geometry Classes (adsk.core)

| Class | Description | Key Methods |
|-------|-------------|-------------|
| `Point3D` | 3D point | `create(x, y, z)`, `distanceTo(point)`, `copy()` |
| `Vector3D` | 3D vector | `create(x, y, z)`, `normalize()`, `crossProduct()`, `dotProduct()` |
| `Matrix3D` | 4x4 transform matrix | `create()`, `translation`, `setToRotation()`, `transformBy()` |
| `Line3D` | Bounded line | `create(startPoint, endPoint)` |
| `InfiniteLine3D` | Infinite line | `create(origin, direction)` |
| `Arc3D` | 3D arc | `create(center, normal, refVector, radius, startAngle, endAngle)` |
| `Circle3D` | 3D circle | `create(center, normal, radius)` |
| `Plane` | Infinite plane | `create(origin, normal)` |
| `NurbsCurve3D` | NURBS curve | `createRational(...)`, `createNonRational(...)` |
| `BoundingBox3D` | Axis-aligned box | `minPoint`, `maxPoint`, `contains()`, `expand()` |
| `ObjectCollection` | Generic collection | `create()`, `add(item)`, `item(index)`, `count` |
| `ValueInput` | Value wrapper | `createByReal(value)`, `createByString(expression)` |

```python
# Point creation
pt = adsk.core.Point3D.create(1.0, 2.0, 3.0)

# Vector creation
vec = adsk.core.Vector3D.create(0, 0, 1)
vec.normalize()

# Matrix (transform)
mat = adsk.core.Matrix3D.create()  # identity
mat.translation = adsk.core.Vector3D.create(5, 0, 0)  # translate 5cm in X

# Object collection (used for many API calls)
collection = adsk.core.ObjectCollection.create()
collection.add(body1)
collection.add(body2)
```

---

## Appendix B: Official Resources

- **API Reference (HTML):** https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-A92A4B10-3781-4925-94C6-47DA85A4F65A
- **API Reference (GitHub):** https://github.com/AutodeskFusion360/FusionAPIReference
- **API User's Guide:** https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-C1545D80-D804-4CF3-886D-9B5C54B2D7A2
- **Python Stubs:** `FusionAPIReference/Fusion_API_Python_Reference/defs/adsk/` (core.py, fusion.py, cam.py)
- **C++ Headers:** `FusionAPIReference/Fusion_API_CPP_Reference/include/`
- **Sample Code (Patrick Rainsberry):** https://github.com/tapnair/Fusion360APIClass
- **Autodesk Forums:** https://forums.autodesk.com/t5/fusion-api-and-scripts/bd-p/22

---

## Appendix C: Quick Reference Patterns

### Minimal Script Template

```python
import adsk.core, adsk.fusion, traceback

def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent
        # ... your code ...
    except:
        ui.messageBox(traceback.format_exc())
```

### Create Sketch + Extrude Pattern

```python
design = adsk.fusion.Design.cast(app.activeProduct)
root = design.rootComponent

# Sketch
sketch = root.sketches.add(root.xYConstructionPlane)
lines = sketch.sketchCurves.sketchLines
lines.addTwoPointRectangle(
    adsk.core.Point3D.create(0, 0, 0),
    adsk.core.Point3D.create(5, 3, 0))

# Extrude
profile = sketch.profiles.item(0)
extrude = root.features.extrudeFeatures.addSimple(
    profile,
    adsk.core.ValueInput.createByReal(2.0),
    adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
```

### Create Hole Pattern

```python
# After creating a body...
holes = root.features.holeFeatures
hole_input = holes.createSimpleInput(
    adsk.core.ValueInput.createByReal(0.5))  # diameter 0.5cm = 5mm
hole_input.setPositionBySketchPoints(sketch_points)
hole_input.setDistanceExtent(
    adsk.core.ValueInput.createByReal(1.0))  # depth 1cm
hole = holes.add(hole_input)
```

### Error Handling Best Practice

```python
def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        # Always wrap in try/except
        # Always use traceback for detailed errors
        pass
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
```

---

## 11. Design Mode Switching (Parametric vs Direct)

The entire design is either Parametric (with timeline/history) or Direct (no history). This is a design-level setting, not per-component.

### Checking Design Type

```python
app = adsk.core.Application.get()
design = adsk.fusion.Design.cast(app.activeProduct)

if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
    # Has timeline, captures design history
    pass
elif design.designType == adsk.fusion.DesignTypes.DirectDesignType:
    # No timeline, direct edits only
    pass
```

### Switching Design Type

```python
# Switch to Direct (disables timeline) - CANNOT BE UNDONE for existing features
design.designType = adsk.fusion.DesignTypes.DirectDesignType

# Switch to Parametric (enables timeline from this point forward)
design.designType = adsk.fusion.DesignTypes.ParametricDesignType
```

### Performance Note

DirectDesignType is significantly faster for script-generated geometry because each operation in parametric mode adds to the timeline, causing cumulative slowdown. For scripts that generate many features (e.g., arrays of bodies), switching to Direct first avoids this overhead:

```python
# Performance optimization for batch geometry creation
app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(app.activeProduct)
design.designType = adsk.fusion.DesignTypes.DirectDesignType  # No timeline overhead

root = design.rootComponent
sketch = root.sketches.add(root.xYConstructionPlane)
for x in range(20):
    for y in range(20):
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(x * 2, y * 2, 0), 0.5)
        root.features.extrudeFeatures.addSimple(
            sketch.profiles[-1],
            adsk.core.ValueInput.createByReal(1),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        adsk.doEvents()
```

---

## 12. Document Management

### Creating Documents

```python
app = adsk.core.Application.get()

# Create new Fusion design document
doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)

# The new document becomes the active document
design = adsk.fusion.Design.cast(app.activeProduct)
```

### Opening Documents

```python
# Open a previously saved document from the data panel
# Returns the opened Document or None on failure
dataFile = ...  # a DataFile object from the data panel
doc = app.documents.open(dataFile)
```

### Saving Documents

```python
doc = app.activeDocument

# Save to existing location (must have been saved before)
doc.save('Description of changes')

# Save As to a specific folder
folder = doc.dataFile.parentFolder  # or get folder from data panel
doc.saveAs('MyDesign', folder, 'Description', '')
```

### Closing Documents

```python
# Close without saving (loses changes)
doc.close(False)

# Close with save prompt to user
doc.close(True)
```

**Limitation:** Closing a document is NOT supported within Command-related events (a transaction is open during commands, and document operations cannot be transacted).

### Insert File as Component

```python
root = design.rootComponent
dataFile = ...  # DataFile of the design to insert
occurrence = root.occurrences.addByInsert(
    dataFile,
    adsk.core.Matrix3D.create(),  # transform
    True  # create new component
)
```

---

## 13. Workspace Switching

### Activating a Workspace

```python
ui = app.userInterface

# Switch to Render workspace
renderWS = ui.workspaces.itemById('FusionRenderEnvironment')
renderWS.activate()

# Switch to CAM/Manufacture workspace
camWS = ui.workspaces.itemById('CAMEnvironment')
camWS.activate()

# Switch back to Design workspace
designWS = ui.workspaces.itemById('FusionSolidEnvironment')
designWS.activate()
```

### Known Workspace IDs

| Workspace | ID |
|-----------|-----|
| Design (Solid) | `FusionSolidEnvironment` |
| Render | `FusionRenderEnvironment` |
| Manufacture/CAM | `CAMEnvironment` |
| Simulation | `SimulationEnvironment` |
| Drawing | `FusionDrawingEnvironment` |
| Animation | `AnimationEnvironment` |

**Note:** Workspace IDs are not officially documented as a stable list and can change. Use the "Write User Interface to File" sample script to dump the current UI structure including all workspace IDs.

### Listing All Workspaces

```python
ui = app.userInterface
for ws in ui.workspaces:
    app.log(f'Workspace: {ws.name} (id: {ws.id})')
```

### Important Caveat

If the Manufacture workspace has never been activated for a document, the document will not have a CAM product. You may need to activate that workspace first before accessing `adsk.cam.CAM` functionality.

---

## 14. UI Manipulation

### UI Hierarchy

```
Workspaces (Design, CAM, Render...)
  +-- Toolbar Tabs (SOLID, SURFACE, MESH, SHEET METAL...)
        +-- Toolbar Panels (Create, Modify, Assemble...)
              +-- Controls (Buttons, Dropdowns, Separators)
```

### Adding a Button to a Panel

```python
ui = app.userInterface
cmdDefs = ui.commandDefinitions

# Create command definition
buttonDef = cmdDefs.addButtonDefinition(
    'MyButtonId',          # unique ID
    'My Button',           # display name
    'Tooltip description', # tooltip
    './/Resources//MyIcon' # icon folder path
)

# Add to a panel in the Design workspace
designWS = ui.workspaces.itemById('FusionSolidEnvironment')
panel = designWS.toolbarPanels.itemById('SolidScriptsAddinsPanel')
control = panel.controls.addCommand(buttonDef)
control.isPromotedByDefault = True
control.isPromoted = True
```

### Icon Requirements

Icons need four sizes in a resource folder:
- `16x16.png` (or .svg) - toolbar/dropdown small
- `32x32.png` (or .svg) - panel large
- `16x16@2x.png` - retina small
- `32x32@2x.png` - retina large

SVG format (Tiny 1.2) is preferred. Dark/light variants: `16x16-light_gray.svg`, `16x16@2x-dark_blue.svg`.

### Adding to Specific Toolbars

```python
# Quick Access Toolbar (top-left file commands)
qat = ui.toolbars.itemById('QAT')

# Quick Access Toolbar Right (top-right account commands)
qatRight = ui.toolbars.itemById('QATRight')

# Navigation Toolbar (bottom-center view commands)
navBar = ui.toolbars.itemById('NavToolbar')

# Add button to a dropdown in QAT
fileDropDown = qat.controls.itemById('FileSubMenuCommand')
control = fileDropDown.controls.addCommand(myDef, 'ThreeDprintCmdDef', True)
```

### Creating Dropdown Controls

```python
dropDown = panel.controls.addDropDown(
    'My Dropdown',
    './/Resources//DropdownIcon',
    'MyDropDownId'
)
dropDown.controls.addCommand(subCommandDef1)
dropDown.controls.addCommand(subCommandDef2)
```

### Cleanup on Add-in Stop

```python
def stop(context):
    ui = app.userInterface

    # Remove command definition
    cmdDef = ui.commandDefinitions.itemById('MyButtonId')
    if cmdDef:
        cmdDef.deleteMe()

    # Remove control from panel
    designWS = ui.workspaces.itemById('FusionSolidEnvironment')
    panel = designWS.toolbarPanels.itemById('SolidScriptsAddinsPanel')
    control = panel.controls.itemById('MyButtonId')
    if control:
        control.deleteMe()
```

### Discovering UI IDs

Run the built-in "Write User Interface to File" sample to export the complete UI structure as XML. This dumps all workspace IDs, toolbar tab IDs, panel IDs, and command definition IDs.

---

## 15. Palettes (Custom HTML Dialogs)

A Palette is a floating or docked dialog whose content is an HTML page. It acts as an embedded browser within Fusion.

### Creating a Palette

```python
palette = ui.palettes.add(
    'myPaletteId',     # unique ID
    'My Palette',      # display name
    'palette.html',    # HTML file (same folder as .py, or full URL)
    False,             # initially visible
    True,              # show close button
    True,              # resizable
    300,               # width
    200,               # height
    True               # use new browser engine (recommended)
)
palette.setPosition(800, 400)
palette.isVisible = True
```

### Python-to-JavaScript Communication

```python
# Send data from Python to JavaScript
palette.sendInfoToHTML('myAction', 'some data string')
```

JavaScript handler in palette.html:
```javascript
window.fusionJavaScriptHandler = {
    handle: function(action, data) {
        if (action === 'myAction') {
            document.getElementById('output').innerHTML = data;
        }
        return 'OK';
    }
};
```

### JavaScript-to-Python Communication

JavaScript sends:
```javascript
adsk.fusionSendData('buttonClicked', JSON.stringify({id: 42, name: 'test'}))
    .then(result => console.log(result));
```

Python event handler:
```python
class MyHTMLEventHandler(adsk.core.HTMLEventHandler):
    def notify(self, args):
        htmlArgs = adsk.core.HTMLEventArgs.cast(args)
        data = json.loads(htmlArgs.data)
        # Process data...
        htmlArgs.returnData = json.dumps({'status': 'ok'})

handler = MyHTMLEventHandler()
palette.incomingFromHTML.add(handler)
```

### Key Behaviors

- Palettes persist across command executions (unlike command dialogs)
- Palettes are NOT document-specific; they persist across workspace changes
- They are automatically deleted when their parent add-in stops
- Enable browser developer tools in Fusion Preferences for debugging

---

## 16. Selection & Active Context

### Active Component

```python
design = adsk.fusion.Design.cast(app.activeProduct)

# Get the currently active component (the one being edited)
activeComp = design.activeComponent

# Set active component (activates it for editing)
design.activateRootComponent()
# or activate a specific occurrence:
occ = root.occurrences.item(0)
design.activateOccurrence(occ)  # not available - see activeEditObject
```

### Active Edit Object

```python
# Returns current edit target (component, sketch, etc.)
# This is the container that receives newly created objects
editObj = app.activeEditObject  # returns Base object

# Or from Design:
editObj = design.activeEditObject
```

### Camera Control

```python
viewport = app.activeViewport

# Get current camera (returns a COPY - edits don't affect viewport until reassigned)
cam = viewport.camera

# Camera properties
cam.eye          # Point3D - camera position
cam.target       # Point3D - look-at point
cam.upVector     # Vector3D - up direction
cam.cameraType   # CameraTypes enum (Orthographic, Perspective, PerspectiveWithOrthoFaces)
cam.perspectiveAngle  # float - field of view (Perspective mode only)
cam.isFitView    # bool - if True, auto-fits to show entire model
cam.isSmoothTransition  # bool - animate transition to new position

# Modify and reassign
cam.eye = adsk.core.Point3D.create(10, 10, 10)
cam.target = adsk.core.Point3D.create(0, 0, 0)
cam.isSmoothTransition = True
viewport.camera = cam  # MUST reassign to apply changes

# Create a fresh camera
newCam = adsk.core.Camera.create()
newCam.eye = adsk.core.Point3D.create(50, 50, 50)
newCam.target = adsk.core.Point3D.create(0, 0, 0)
newCam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
viewport.camera = newCam

# Fit view to model
cam = viewport.camera
cam.isFitView = True
viewport.camera = cam

# Save viewport as image
viewport.saveAsImageFile('/tmp/screenshot.png', 1920, 1080)
```

### Named Views

```python
# Access named views collection
namedViews = design.namedViews

# Create a named view from current camera
cam = viewport.camera
namedViews.add('My Custom View', cam)

# Apply a named view
for nv in namedViews:
    if nv.name == 'My Custom View':
        viewport.camera = nv.camera
        break
```

### Viewport Properties

```python
viewport = app.activeViewport
viewport.visualStyle  # get/set visual style
viewport.refresh()    # force redraw
```

---

## 17. Material & Appearance API

### Loading Appearance Libraries

```python
# Access all material libraries
materialLibs = app.materialLibraries

# Get built-in library by name
fusionLib = materialLibs.itemByName('Fusion 360 Appearance Library')

# Load a custom library file
customLib = materialLibs.load('/path/to/library.adsklib')
```

### Applying Appearances to Bodies

```python
design = adsk.fusion.Design.cast(app.activeProduct)
root = design.rootComponent

# Get an appearance from a library
lib = app.materialLibraries.itemByName('Fusion 360 Appearance Library')
sourceAppear = lib.appearances.itemByName('Paint - Enamel Glossy (Red)')

# Copy appearance into the design (required before applying)
designAppear = design.appearances.addByCopy(sourceAppear, 'My Red Paint')

# Apply to a body
body = root.bRepBodies.item(0)
body.appearance = designAppear

# Apply to a face
face = body.faces.item(0)
face.appearance = designAppear

# Apply to a component
comp = root.occurrences.item(0).component
comp.appearance = designAppear
```

### Editing Appearance Properties

```python
appear = design.appearances.itemByName('My Red Paint')

# Access appearance properties
props = appear.appearanceProperties

# Change color
colorProp = adsk.core.ColorProperty.cast(props.itemByName('Color'))
colorProp.value = adsk.core.Color.create(0, 128, 255, 255)

# Access other properties by name (varies by appearance type):
# 'Glossiness', 'Reflectance', 'Transparency', 'Bump', etc.
```

### Physical Materials

```python
# Physical materials define engineering properties (density, yield strength, etc.)
matLib = app.materialLibraries.itemByName('Fusion 360 Material Library')
steel = matLib.materials.itemByName('Steel')

# Copy into design and apply to body
designMat = design.materials.addByCopy(steel, 'My Steel')
body.material = designMat
```

### Getting Physical Properties

```python
# Get physical properties of a body (area, volume, mass, center of mass, etc.)
physProps = body.physicalProperties

# For more accurate results:
physProps = body.getPhysicalProperties(
    adsk.fusion.CalculationAccuracy.HighCalculationAccuracy)

area = physProps.area           # cm^2
volume = physProps.volume       # cm^3
mass = physProps.mass           # kg
com = physProps.centerOfMass    # Point3D
density = physProps.density     # kg/cm^3
```

### Unloading Custom Libraries

```python
if customLib.isNative == False:
    customLib.unload()
```

---

## 18. Timeline API

Only available when `design.designType == ParametricDesignType`.

### Accessing the Timeline

```python
design = adsk.fusion.Design.cast(app.activeProduct)
timeline = design.timeline

timeline.count           # number of items
timeline.markerPosition  # current marker position (0 = beginning, count = end)
```

### Moving the Marker

```python
# Move to beginning
timeline.moveToBeginning()

# Move to end (shows all features)
timeline.moveToEnd()

# Step forward/backward
timeline.movetoNextStep()
timeline.moveToPreviousStep()

# Set marker to specific position
timeline.markerPosition = 5  # roll back to after 5th feature

# Play the timeline from current position
timeline.play()
```

### Rolling Back to a Specific Feature

```python
# Roll to just before a specific timeline object
timelineObj = timeline.item(3)  # 4th item (0-indexed)
timelineObj.rollTo(True)   # True = roll to just before this object
timelineObj.rollTo(False)  # False = roll to just after this object
```

### Suppressing Features

```python
# Suppress a feature (removes its effect without deleting)
timelineObj = timeline.item(5)
timelineObj.isSuppressed = True

# Unsuppress
timelineObj.isSuppressed = False

# Access the underlying feature entity
feature = timelineObj.entity  # returns the Feature object
```

### Timeline Groups

```python
# Access groups
groups = timeline.timelineGroups

# Create a group from a range of timeline objects
# (Select timeline items first, then group)
startObj = timeline.item(2)
endObj = timeline.item(5)
# Groups are typically created via UI or during component creation

# Iterate groups
for i in range(groups.count):
    group = groups.item(i)
    # group.count - number of items in group
    # group.isCollapsed - get/set collapsed state
```

### Delete All After Marker

```python
# Deletes all timeline objects after the current marker position
# WARNING: This is destructive and cannot be undone
timeline.deleteAllAfterMarker()
```

---

## 19. Mesh & T-Spline API

### Importing Mesh Bodies

```python
root = design.rootComponent
meshBodies = root.meshBodies

# Import STL/OBJ/3MF file
meshBodyList = meshBodies.add(
    '/path/to/model.stl',
    adsk.fusion.MeshUnits.MillimeterMeshUnit
)
# Returns MeshBodyList (OBJ files can produce multiple bodies)
mesh = meshBodyList.item(0)
```

### Importing Mesh in Parametric Mode

In parametric designs, mesh import must be wrapped in a BaseFeature edit:

```python
baseFeature = root.features.baseFeatures.add()
baseFeature.startEdit()

meshBodyList = meshBodies.add(
    '/path/to/model.stl',
    adsk.fusion.MeshUnits.MillimeterMeshUnit,
    baseFeature  # required in parametric mode
)

baseFeature.finishEdit()
```

### Accessing Mesh Data

```python
mesh = root.meshBodies.item(0)

# Get the display mesh (triangle mesh)
displayMesh = mesh.displayMesh
nodeCoords = displayMesh.nodeCoordinates     # list of Point3D
nodeIndices = displayMesh.nodeIndices        # triangle vertex indices
normalVectors = displayMesh.normalVectors    # list of Vector3D
triangleCount = displayMesh.triangleCount
nodeCount = displayMesh.nodeCount
```

### BRepBody Mesh Access

```python
# Get mesh representation of a BRep body
body = root.bRepBodies.item(0)
meshManager = body.meshManager
bestMesh = meshManager.displayMeshes.bestMesh
# or calculate with specific tolerance:
meshCalc = meshManager.createMeshCalculator()
meshCalc.setQuality(adsk.fusion.TriangleMeshQualityOptions.NormalQualityTriangleMesh)
triMesh = meshCalc.calculate()
```

### BRepBody.convert() - NURBS Conversion

```python
# Convert body faces/edges to NURBS geometry
body = root.bRepBodies.item(0)
newBody = body.convert(adsk.fusion.BRepConvertOptions.SurfaceConvertOption)
```

### T-Spline Bodies

**NOT DIRECTLY AVAILABLE via API.** There is no `adsk.fusion.TSplineBody` class or T-Spline creation API. T-Spline operations (Sculpt/Form workspace) are not exposed to the scripting API.

**Workaround for Mesh-to-BRep conversion:**
```python
# Use executeTextCommand to invoke the built-in conversion command
app.executeTextCommand('Commands.Start Mesh2BRepCommand')
app.executeTextCommand('NuCommands.CommitCmd')
```

This is a workaround that triggers the UI command rather than a proper API call. It requires the mesh body to be pre-selected.

---

## 20. Drawing API

### Status: VERY LIMITED

The `adsk.drawing` module exists but provides minimal functionality. You **cannot** programmatically:
- Create drawing views
- Add dimensions to drawings
- Configure title blocks
- Place annotations
- Control drawing sheet settings

### Triggering Drawing Creation (Workaround)

```python
# Execute the built-in "Drawing from Design" command
cmdDef = ui.commandDefinitions.itemById('NewFusionDrawingDocumentCommand')
cmdDef.execute()
# This opens the drawing creation dialog - user must configure manually
```

### What IS Available

The Drawing workspace can be activated:
```python
drawingWS = ui.workspaces.itemById('FusionDrawingEnvironment')
drawingWS.activate()
```

But there are no API objects to manipulate drawing content programmatically.

---

## 21. Simulation & Generative Design API

### Status: NOT AVAILABLE

**Simulation:** There is NO scripting API for the Simulation workspace. You cannot:
- Create simulation studies programmatically
- Set loads, constraints, or materials for simulation
- Run simulations or retrieve results
- Access stress/displacement/factor-of-safety data

**Generative Design:** There is NO scripting API for Generative Design. You cannot:
- Define design spaces, obstacle geometry, or preserve geometry
- Set manufacturing constraints
- Launch generative studies
- Access or compare generated outcomes

**Workaround:** You can activate the workspace:
```python
simWS = ui.workspaces.itemById('SimulationEnvironment')
simWS.activate()
```

But no further programmatic control is possible. These workspaces require appropriate licensing (Commercial, Startup, or Education) even for manual use.

---

## 22. Rendering API

### Status: VERY LIMITED

There is no comprehensive render API. You **cannot** programmatically:
- Configure render settings (resolution, quality, ray depth)
- Change scene environment or HDRI maps
- Set ground plane, background, or shadow settings
- Start/stop renders
- Access rendered images programmatically

### What IS Available

```python
# Activate render workspace
renderWS = ui.workspaces.itemById('FusionRenderEnvironment')
renderWS.activate()

# Appearances CAN be set via API (see Section 17)
# Camera CAN be controlled (see Section 16)
# Viewport screenshot CAN be captured (but NOT a ray-traced render):
viewport = app.activeViewport
viewport.saveAsImageFile('/tmp/viewport_capture.png', 1920, 1080)
```

The `saveAsImageFile` re-renders at the specified resolution (not just a screenshot) but uses the viewport render mode, not the ray-traced renderer.

---

## 23. Units & Preferences API

### Changing Document Units

```python
design = adsk.fusion.Design.cast(app.activeProduct)
unitsManager = design.unitsManager

# Get current default length units
currentUnits = unitsManager.defaultLengthUnits  # e.g., 'mm', 'cm', 'in'

# Change default units
unitsManager.defaultLengthUnits = 'mm'
# Valid values: 'mm', 'cm', 'm', 'in', 'ft'
```

### Internal Units

Fusion always uses **centimeters** internally for lengths and **radians** for angles. All `ValueInput.createByReal()` values are in these internal units. String inputs like `ValueInput.createByString('15 mm')` are automatically converted.

```python
# These are equivalent:
adsk.core.ValueInput.createByReal(1.5)        # 1.5 cm
adsk.core.ValueInput.createByString('15 mm')   # 15 mm = 1.5 cm
adsk.core.ValueInput.createByString('1.5 cm')  # explicit cm
```

### Unit Conversion

```python
um = design.unitsManager

# Convert between units
mm_val = um.convert(1.5, 'cm', 'mm')   # 15.0
inch_val = um.convert(25.4, 'mm', 'in')  # 1.0

# Format value with current units
formatted = um.formatInternalValue(1.5)  # e.g., "15 mm" if default is mm

# Parse user string to internal value
internal = um.evaluateExpression('15 mm', 'cm')  # 1.5
```

### Application Preferences

```python
prefs = app.preferences

# General Preferences
general = prefs.generalPreferences
lang = general.userLanguage  # current language

# Graphics Preferences
graphics = prefs.graphicsPreferences

# Grid Preferences
grid = prefs.gridPreferences
# grid properties include layout, spacing, etc.

# Unit and Value Preferences
unitPrefs = prefs.unitAndValuePreferences

# Material Preferences
matPrefs = prefs.materialPreferences

# Network Preferences
netPrefs = prefs.networkPreferences
```

**Note:** The Preferences API is read-heavy. Not all properties can be set programmatically; some are read-only reflecting the current application state.

---

## 24. Custom Graphics API

Custom Graphics display temporary visual overlays that are NOT part of the design model. They are ideal for visual feedback, annotations, highlights, and interactive tool previews.

### Creating a Graphics Group

```python
root = design.rootComponent
graphics = root.customGraphicsGroups.add()
```

### Drawing Meshes (Triangles)

```python
# Define vertices as flat array [x1,y1,z1, x2,y2,z2, ...]
coordArray = [0,0,0, 10,0,0, 5,10,0, 5,0,10]
coords = adsk.fusion.CustomGraphicsCoordinates.create(coordArray)

# Triangle indices (groups of 3 vertex indices)
indices = [0,1,2, 0,2,3, 1,2,3, 0,1,3]

# Create mesh
mesh = graphics.addMesh(coords, indices, [], [])
```

### Drawing Lines

```python
coords = adsk.fusion.CustomGraphicsCoordinates.create([0,0,0, 10,0,0, 10,10,0, 0,10,0])
lineIndices = [0,1, 1,2, 2,3, 3,0]  # pairs of vertex indices
lines = graphics.addLines(coords, lineIndices, False)  # False = not strip
lines.weight = 2  # line thickness in pixels
```

### Drawing Points

```python
coords = adsk.fusion.CustomGraphicsCoordinates.create([0,0,0, 5,5,0, 10,0,0])
pointIndices = [0, 1, 2]
points = graphics.addPointSet(
    coords, pointIndices,
    adsk.fusion.CustomGraphicsPointTypes.UserDefinedCustomGraphicsPointType,
    '/path/to/marker_image.png'
)
```

### Drawing Curves

```python
# Circle
circle = adsk.core.Circle3D.createByCenter(
    adsk.core.Point3D.create(0, 0, 0),
    adsk.core.Vector3D.create(0, 0, 1),
    5.0)
curveGraphics = graphics.addCurve(circle)

# Also supports: Arc3D, Ellipse3D, EllipticalArc3D, Line3D, NurbsCurve3D
```

### Drawing BRep Bodies as Graphics

```python
body = root.bRepBodies.item(0)
graphicBody = graphics.addBRepBody(body)
```

### Drawing Text

```python
text = 'Hello World'
matrix = adsk.core.Matrix3D.create()
textGraphics = graphics.addText(text, 'Arial', 3, matrix)
# Supports formatting: \L...\l (underline), \O...\o (overstrike),
# \Hn; (height), \Qn; (slant), \Wn; (width), \Tn; (spacing), \P (newline)
```

### Color Effects

```python
# Solid color
red = adsk.core.Color.create(255, 0, 0, 255)
solidColor = adsk.fusion.CustomGraphicsSolidColorEffect.create(red)
mesh.color = solidColor

# Phong material shading
effect = adsk.fusion.CustomGraphicsBasicMaterialColorEffect.create(
    diffuse, ambient, specular, emissive, glossiness, opacity)
mesh.color = effect

# From library appearance
appear = design.appearances.itemByName('Carbon Fiber')
appearEffect = adsk.fusion.CustomGraphicsAppearanceColorEffect.create(appear)
mesh.color = appearEffect

# Per-vertex coloring
coords.colors = [255,0,0,255, 0,255,0,255, 0,0,255,255]  # RGBA per vertex
vertexColor = adsk.fusion.CustomGraphicsVertexColorEffect.create()
mesh.color = vertexColor

# Show-through (X-ray style)
showThrough = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(
    adsk.core.Color.create(255, 0, 0, 255), 0.2)
mesh.color = showThrough

# Reset color
mesh.color = None
```

### Billboarding (Always Face Camera)

```python
billboard = adsk.fusion.CustomGraphicsBillBoard.create(
    adsk.core.Point3D.create(0, 0, 0))
billboard.billBoardStyle = \
    adsk.fusion.CustomGraphicsBillBoardStyles.ScreenBillBoardStyle
textGraphics.billBoarding = billboard
```

### View Scale (Pixel-Sized Graphics)

```python
viewScale = adsk.fusion.CustomGraphicsViewScale.create(
    50,  # pixel size
    adsk.core.Point3D.create(0, 0, 0))  # anchor point
mesh.viewScale = viewScale
```

### View Placement (Screen-Anchored)

```python
placement = adsk.fusion.CustomGraphicsViewPlacement.create(
    adsk.core.Point3D.create(0, 0, 0),
    adsk.fusion.ViewCorners.lowerRightViewCorner,
    adsk.core.Point2D.create(210, 10))
mesh.viewPlacement = placement
```

### Transform

```python
matrix = mesh.transform
matrix.setCell(0, 3, 5.0)  # translate X by 5
mesh.transform = matrix
```

### Visibility and Selection

```python
mesh.isVisible = True
mesh.isSelectable = True
mesh.depthPriority = 1  # higher values draw on top
```

### Cleanup

```python
# Delete a specific graphics group
graphics.deleteMe()

# Delete all custom graphics
while root.customGraphicsGroups.count > 0:
    root.customGraphicsGroups.item(0).deleteMe()

# Refresh viewport to show changes
app.activeViewport.refresh()
```

### Important Notes

- Custom graphics are **transacted** entities. Changes must be made within a transaction context (e.g., inside a command's execute event handler).
- Graphics are "meaningless" to Fusion - they have no effect on the design model.
- The add-in is responsible for all interpretation and lifecycle management.

---

## 25. Data & Cloud API

### Data Panel Hierarchy

```
Application
  +-- data (DataPanel)
        +-- dataProjects (DataProjects)
              +-- DataProject
                    +-- rootFolder (DataFolder)
                          +-- dataFiles (DataFiles)
                          +-- dataFolders (DataFolders)
```

### Accessing the Data Panel

```python
app = adsk.core.Application.get()

# Access data panel
dataPanel = app.data

# List all projects
projects = dataPanel.dataProjects
for i in range(projects.count):
    proj = projects.item(i)
    app.log(f'Project: {proj.name}')
```

### Navigating Folders

```python
project = dataPanel.dataProjects.item(0)
rootFolder = project.rootFolder

# List files in root
for i in range(rootFolder.dataFiles.count):
    f = rootFolder.dataFiles.item(i)
    app.log(f'File: {f.name}, Version: {f.versionNumber}')

# List subfolders
for i in range(rootFolder.dataFolders.count):
    folder = rootFolder.dataFolders.item(i)
    app.log(f'Folder: {folder.name}')
```

### Getting Current Document's Location

```python
doc = app.activeDocument
if doc.isSaved:
    dataFile = doc.dataFile
    parentFolder = dataFile.parentFolder
    project = parentFolder.parentProject
    app.log(f'Saved in: {project.name}/{parentFolder.name}/{dataFile.name} v{dataFile.versionNumber}')
```

### Uploading Files

```python
folder = project.rootFolder  # or any DataFolder

# Upload a file (STL, STEP, etc.) - triggers cloud translation
future = folder.uploadFile('/path/to/file.step')

# The upload is asynchronous - check status via DataFileFuture
# future.isComplete, future.dataFile (when done)
```

**Limitation:** `uploadFile` is NOT supported within Command-related events (transactions cannot contain file uploads).

### Version History

```python
dataFile = doc.dataFile
# dataFile.versionNumber - current version
# dataFile.versions - access to version history (DataFileVersions)
```

---

## 26. Undo & Transaction Management

### Automatic Transaction Grouping in Commands

When you use the Command pattern (commandCreated -> execute event), everything in the `execute` event handler is automatically grouped into a **single undo operation**:

```python
class MyExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent

        # All of these operations become ONE undo step:
        sketch = root.sketches.add(root.xYConstructionPlane)
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), 5)
        prof = sketch.profiles.item(0)
        root.features.extrudeFeatures.addSimple(
            prof,
            adsk.core.ValueInput.createByReal(2),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        # User can undo ALL of this with Ctrl+Z once
```

### Without Commands (Scripts)

Scripts that directly call API methods create **individual undo entries** for each operation. There is no public `beginUndoGroup()` / `endUndoGroup()` method in the Fusion API.

**Best practice:** Use the Command pattern even in scripts to get transaction grouping:

```python
def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Create a temporary command to get transaction grouping
    cmdDef = ui.commandDefinitions.itemById('MyTempCmd')
    if not cmdDef:
        cmdDef = ui.commandDefinitions.addButtonDefinition(
            'MyTempCmd', 'Temp', '')

    onCreated = MyCommandCreatedHandler()
    cmdDef.commandCreated.add(onCreated)
    handlers.append(onCreated)

    adsk.autoTerminate(False)  # Keep script alive during command
    cmdDef.execute()
```

### ExecutePreview for Live Feedback

```python
class MyPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        eventArgs = adsk.core.CommandEventArgs.cast(args)
        # Create preview geometry...
        # If preview is acceptable as final result:
        eventArgs.isValidResult = True  # skips execute, uses preview
```

### Command Lifecycle Events

```
commandCreated -> (dialog shown) -> inputChanged* -> validateInputs*
  -> executePreview* -> execute -> destroy
```

- `execute`: Creates final result, auto-grouped as single undo
- `executePreview`: Temporary preview, rolled back if not `isValidResult`
- `inputChanged`: React to dialog input changes
- `validateInputs`: Enable/disable OK button
- `destroy`: Final cleanup (always fires)

### Limitations

- No public `undo()` or `redo()` methods in the API
- No way to programmatically invoke undo/redo
- No `beginUndoGroup()` / `endUndoGroup()` for scripts
- Document open/close/save operations cannot occur inside a transaction (Command events)
- File upload cannot occur inside a transaction

---

## API Availability Summary

| Feature Area | API Status | Notes |
|---|---|---|
| Design Mode (Parametric/Direct) | **Full** | Read/write `design.designType` |
| Document Management | **Full** | Create, open, save, close, insert |
| Workspace Switching | **Full** | `workspace.activate()` |
| UI Customization | **Full** | Toolbars, panels, buttons, palettes |
| Palettes (HTML dialogs) | **Full** | Bidirectional JS-Python communication |
| Selection/Active Context | **Full** | activeComponent, activeEditObject, camera |
| Materials & Appearances | **Full** | Libraries, apply, edit properties |
| Physical Properties | **Full** | Area, volume, mass, center of mass |
| Timeline | **Full** | Marker, rollback, suppress, groups |
| Custom Graphics | **Full** | Meshes, lines, points, curves, text, billboarding |
| Data/Cloud API | **Full** | Projects, folders, files, upload, versions |
| Units & Preferences | **Partial** | Units full; some prefs read-only |
| Mesh Import | **Partial** | STL/OBJ/3MF import; limited mesh editing |
| Undo/Transactions | **Partial** | Auto-grouping in commands; no manual undo API |
| Drawing API | **Minimal** | Can trigger command; no content manipulation |
| Rendering API | **Minimal** | Appearances yes; render settings/execution no |
| T-Spline/Sculpt | **Not Available** | No API; workaround via text commands |
| Simulation | **Not Available** | No API at all |
| Generative Design | **Not Available** | No API at all |
