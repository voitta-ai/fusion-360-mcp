# Fusion 360 MCP Server — Complete Reference

**Version:** 0.13.0
**Architecture:** MCP Server (stdio) → HTTP Add-In (localhost:8080) → Fusion 360 API

---

## Architecture

```
Claude / LLM (MCP Client)
  → MCP Server (fusion_mcp_server.py, stdio)
    → HTTP POST to localhost:8080
      → HTTP Add-In (HTTP.py, runs inside Fusion 360)
        → Operation handler on main thread
      ← JSON response
    ← Formatted text/image content
```

All operations execute on Fusion 360's main thread via a custom event queue for thread safety.

---

## Path Format Reference

All geometry in the server is addressed by hierarchical paths:

```
root/bRepBodies/BodyName                    → BRepBody
root/bRepBodies/BodyName/faces/0            → BRepFace (by index)
root/bRepBodies/BodyName/edges/3            → BRepEdge (by index)
root/bRepBodies/BodyName/vertices/1         → BRepVertex (by index)
root/sketches/SketchName                    → Sketch
root/constructionPlanes/PlaneName           → ConstructionPlane
root/constructionAxes/AxisName              → ConstructionAxis
root/occurrences/ComponentName:1            → Occurrence
root/children/ComponentName:1/bRepBodies/B  → Body inside component
```

**Axis shortcuts:** `'X'`, `'Y'`, `'Z'` → construction axes
**Plane shortcuts:** `'XY'`, `'XZ'`, `'YZ'` → construction planes
**Units:** All dimensions in **cm** (Fusion 360 default). Angles in **degrees** unless noted.

---

## Tool Catalog

### Viewing & Screenshots

| Tool | Description |
|------|-------------|
| `fusion_screenshot` | Capture viewport as PNG (width, height) |
| `fusion_screenshot_multiview` | Capture front/right/top/iso views in one call |
| `fusion_get_camera` | Get camera eye, target, upVector, orientation |
| `fusion_set_camera` | Set camera position with optional smooth transition |

### Design Tree & State

| Tool | Description |
|------|-------------|
| `fusion_get_tree` | Full hierarchical tree: bodies, sketches, features, joints, transforms, bounding boxes, physical properties |
| `fusion_set_element_properties` | Set visibility, grounding, opacity, selectability |
| `fusion_get_design_type` | Query Parametric vs Direct mode |
| `fusion_set_design_type` | Switch design modes |
| `fusion_get_features` | List all timeline features with type and suppression state |

### Measurement & Spatial Analysis

| Tool | Description |
|------|-------------|
| `fusion_measure_distance` | Distance between points or edges → distance, coordinates, direction vector |
| `fusion_measure_angle` | Angle between edges or faces → degrees, radians, direction vectors |
| `fusion_measure_all_angles` | Batch measure all angles between edges/faces in a body |
| `fusion_get_edge_info` | Edge details: length, start/end points, direction, curve type (line/arc/circle/ellipse/spline) |
| `fusion_get_face_info` | Face details: area, centroid, surface type (planar/cylindrical/conical/spherical), normal, radius |
| `fusion_get_edge_relationships` | Topology: connected edges, adjacent faces |

### Geometry Search

| Tool | Description |
|------|-------------|
| `fusion_find_edges_by_criteria` | Search by length, curve type, proximity, direction (parallel_to, perpendicular_to) |
| `fusion_find_faces_by_criteria` | Search by area, surface type, normal direction, proximity |

### Sketch Tools

| Tool | Description |
|------|-------------|
| `fusion_create_sketch` | Create sketch on plane **or planar face** (supports `'XY'`/`'XZ'`/`'YZ'`, construction planes, and face paths like `root/bRepBodies/Body1/faces/0`) |
| `fusion_sketch_add_line` | Add line (two points) |
| `fusion_sketch_add_circle` | Add circle (center+radius or three points) |
| `fusion_sketch_add_arc` | Add arc (three points or center+start+sweep) |
| `fusion_sketch_add_rectangle` | Add rectangle (two points or center point) |
| `fusion_sketch_add_point` | Add sketch point |
| `fusion_sketch_add_constraint` | Geometric constraints: horizontal, vertical, parallel, perpendicular, tangent, equal, concentric, coincident, midpoint |
| `fusion_sketch_add_dimension` | Parametric dimensions: distance, linear, radius, diameter, angle |

### Feature Operations

| Tool | Description |
|------|-------------|
| `fusion_create_extrude` | Extrude sketch profile. Extent: distance, to_object, through_all, all. Direction: one_side, two_sides, symmetric. Taper angles. Operations: new_body, join, cut, intersect, new_component |
| `fusion_create_revolve` | **NEW** Revolve profile around axis (sketch line or construction axis). Angle 0–360°. Same operations as extrude |
| `fusion_create_fillet` | **NEW** Round edges. Constant radius, tangent chain option |
| `fusion_create_chamfer` | **NEW** Bevel edges. Equal or asymmetric (distance + distance2) |
| `fusion_create_shell` | **NEW** Hollow out body. Select faces to remove, set wall thickness (inside or outside) |
| `fusion_create_hole` | **NEW** Drill hole on face. Types: simple, counterbore, countersink. Tip angle, depth |
| `fusion_create_rectangular_pattern` | **NEW** Pattern features/bodies in 1 or 2 directions. Spacing or extent mode |
| `fusion_create_circular_pattern` | **NEW** Pattern features/bodies around an axis. Count, angle, symmetric option |
| `fusion_suppress_feature` | Toggle feature suppression |
| `fusion_edit_feature` | Modify feature params (extrude distance, revolve angle, fillet radius, chamfer distance) |
| `fusion_delete_feature` | Remove feature from timeline |

### Construction Geometry

| Tool | Description |
|------|-------------|
| `fusion_create_plane` | Modes: offset, angle, three_points, perpendicular |
| `fusion_create_axis` | Modes: edge, perpendicular |

### Body Operations

| Tool | Description |
|------|-------------|
| `fusion_move_body` | Translate body by vector |
| `fusion_rotate_body` | Rotate body around axis |
| `fusion_mirror_body` | Mirror body across plane |
| `fusion_split_body` | Split body using plane or face |
| `fusion_boolean_operation` | Join, cut, or intersect two bodies |

### Assembly & Joints

| Tool | Description |
|------|-------------|
| `fusion_create_joint` | 7 motion types: rigid, revolute, slider, cylindrical, ball, planar, pin_slot |
| `fusion_create_as_built_joint` | Joint from pre-positioned occurrences |
| `fusion_drive_joint` | Move joint to position (rotation, slide, pitch/yaw/roll). Optional animation |
| `fusion_set_joint_limits` | Set min/max/rest on joint DOFs |
| `fusion_modify_joint` | Rename, lock/unlock, suppress, flip, change motion type |
| `fusion_delete_joint` | Remove joint |
| `fusion_create_joint_origin` | Reusable joint connection point |
| `fusion_create_rigid_group` | Lock multiple occurrences together |
| `fusion_create_motion_link` | Synchronize motion between joints (e.g., 360° rotation = 10cm slide) |
| `fusion_get_joint_details` | Query joint axis, geometry, health, motion values |
| `fusion_get_grounding_state` | Check occurrence grounding |

### Component Management

| Tool | Description |
|------|-------------|
| `fusion_create_component` | Create empty component at position |
| `fusion_copy_occurrence` | Duplicate component instance |
| `fusion_move_occurrence` | Translate occurrence (relative or absolute) |
| `fusion_rotate_occurrence` | Rotate occurrence |
| `fusion_set_occurrence_transform` | Set full 4×4 transform matrix or reset to identity |
| `fusion_delete_occurrence` | Remove occurrence |

### Utility

| Tool | Description |
|------|-------------|
| `execute_fusion_script` | Run arbitrary Python with access to app, ui, design, root, adsk |
| `fusion_highlight_geometry` | Select/highlight elements in viewport |
| `fusion_undo` | Undo last operation |
| `fusion_set_server` / `fusion_get_server` | Configure remote Fusion 360 connection |

---

## Common Workflows

### Iterative Modeling (sketch on existing face)
```
1. fusion_create_sketch(plane="XY")           → create base sketch
2. fusion_sketch_add_rectangle(...)            → draw profile
3. fusion_create_extrude(distance=5)           → create base body
4. fusion_find_faces_by_criteria(normal={z:1}) → find top face
5. fusion_create_sketch(plane="root/bRepBodies/Body1/faces/2")  → sketch ON top face
6. fusion_sketch_add_circle(...)               → draw hole profile
7. fusion_create_extrude(operation="cut")      → cut hole through body
```

### Measure → Act → Verify Loop
```
1. fusion_get_face_info(body_path)             → get face centroids and normals
2. fusion_measure_distance(point1, point2)     → get exact dimension
3. fusion_create_fillet(edge_paths, radius)     → perform operation
4. fusion_screenshot_multiview()               → verify from 4 angles
```

### Pattern Workflow
```
1. Create a single feature (hole, extrude, etc.)
2. fusion_get_features()                       → get feature name
3. fusion_create_circular_pattern(input="Hole1", axis="Z", count=6)
```

---

## Response Format

All operations return:
```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "error description",
  "traceback": "Python traceback on error"
}
```

Mutating operations (extrude, revolve, fillet, etc.) return created/affected bodies with volume, area, and path.

---

## Notes for LLM Integration

1. **Always measure before placing** — use `fusion_get_face_info` and `fusion_measure_distance` to get exact coordinates. Never estimate positions.
2. **Use multiview screenshots** — `fusion_screenshot_multiview` gives front/right/top/iso in one call, far better for spatial understanding than a single angle.
3. **Decompose 3D into 2D** — select a face, sketch on it, then extrude. Don't try to reason about 3D coordinates directly.
4. **Check your work** — after each major operation, take a screenshot and read the tree to verify state.
5. **Use find_faces/edges_by_criteria** — instead of guessing face indices, search by normal direction, area, or proximity.
