# Fusion 360 MCP Server - Expansion Plan
## Advanced Measurement, Query, and Modification Tools

## Overview

This plan outlines the addition of 25+ new tools across 8 categories to provide comprehensive control over Fusion 360 design analysis, measurement, modification, and geometry queries.

**Current State:**
- HTTP Add-In v4.1 with 6 operations
- MCP Server v0.3.0 with 6 tools
- Capabilities: screenshot, camera, tree, element properties, script execution

**Target State:**
- HTTP Add-In v5.0 with 30+ operations
- MCP Server v0.4.0 with 30+ tools
- Full measurement, query, sketch, modification, and analysis capabilities

---

## Tool Categories & Implementation Priority

### Phase 1: Measurement & Analysis (HIGH PRIORITY)
Foundation for understanding existing geometry.

**1.1 fusion_measure_distance**
- Complexity: Low
- Dependencies: None
- Implementation: Direct API calls to measurement functions

**1.2 fusion_measure_angle**
- Complexity: Low
- Dependencies: None
- Implementation: Vector math + Fusion API

**1.3 fusion_get_edge_info**
- Complexity: Medium
- Dependencies: Path resolution system (exists)
- Implementation: Extend path system to support edge indexing

**1.4 fusion_get_face_info**
- Complexity: Medium
- Dependencies: Path resolution system (exists)
- Implementation: Extend path system to support face indexing

**1.5 fusion_select_geometry**
- Complexity: HIGH - requires interactive UI
- Dependencies: Selection event handlers
- Implementation: Async selection with callback

---

### Phase 2: Geometry Query (HIGH PRIORITY)
Intelligent search and filtering of design elements.

**2.1 fusion_find_edges_by_criteria**
- Complexity: Medium
- Dependencies: Edge info system
- Implementation: Iterate all edges, filter by criteria

**2.2 fusion_find_faces_by_criteria**
- Complexity: Medium
- Dependencies: Face info system
- Implementation: Iterate all faces, filter by criteria

**2.3 fusion_get_bounding_geometry**
- Complexity: Medium
- Dependencies: Edge/face info
- Implementation: Topology traversal APIs

---

### Phase 3: Construction Tools (MEDIUM PRIORITY)
Create reference geometry for measurements and modifications.

**3.1 fusion_create_plane**
- Complexity: Medium
- Dependencies: None
- Implementation: ConstructionPlane API

**3.2 fusion_create_axis**
- Complexity: Low
- Dependencies: None
- Implementation: ConstructionAxis API

---

### Phase 4: Transform Tools (MEDIUM PRIORITY)
Non-destructive geometry manipulation.

**4.1 fusion_move_body**
- Complexity: Low
- Dependencies: None
- Implementation: MoveFeature or Transform API

**4.2 fusion_rotate_body**
- Complexity: Low
- Dependencies: None
- Implementation: Transform API

**4.3 fusion_mirror_body**
- Complexity: Low
- Dependencies: None
- Implementation: MirrorFeature API

---

### Phase 5: Body Modification (HIGH COMPLEXITY)
Destructive geometry operations - requires careful timeline management.

**5.1 fusion_split_body**
- Complexity: HIGH
- Dependencies: Construction planes
- Implementation: SplitBodyFeature API
- Risk: Timeline position, body references

**5.2 fusion_extrude_cut**
- Complexity: HIGH
- Dependencies: Sketch system
- Implementation: ExtrudeFeature API
- Risk: Profile selection, extent calculation

**5.3 fusion_extrude_add**
- Complexity: HIGH
- Dependencies: Sketch system
- Implementation: ExtrudeFeature API

**5.4 fusion_boolean_operations**
- Complexity: MEDIUM
- Dependencies: None
- Implementation: CombineFeature API

---

### Phase 6: Sketch Tools (HIGH COMPLEXITY)
Requires understanding of sketch constraints and dimensions.

**6.1 fusion_create_sketch**
- Complexity: MEDIUM
- Dependencies: Plane selection
- Implementation: Sketches.add()

**6.2 fusion_sketch_add_line**
- Complexity: MEDIUM
- Dependencies: Active sketch
- Implementation: SketchLines.addByTwoPoints()

**6.3 fusion_sketch_add_constraint**
- Complexity: HIGH
- Dependencies: Geometry references
- Implementation: GeometricConstraints API

**6.4 fusion_sketch_add_dimension**
- Complexity: HIGH
- Dependencies: Geometry references
- Implementation: SketchDimensions API

---

### Phase 7: Feature/Timeline Tools (MEDIUM PRIORITY)
Timeline and parametric design management.

**7.1 fusion_get_features**
- Complexity: LOW
- Dependencies: None
- Implementation: Iterate component.features

**7.2 fusion_edit_feature**
- Complexity: HIGH
- Dependencies: Feature type detection
- Implementation: Timeline rollback + property modification
- Risk: Breaking downstream features

**7.3 fusion_suppress_feature**
- Complexity: LOW
- Dependencies: None
- Implementation: Feature.isSuppressed property

---

### Phase 8: Visualization/Helper Tools (LOW PRIORITY)
UX enhancements and debugging aids.

**8.1 fusion_highlight_geometry**
- Complexity: MEDIUM
- Dependencies: None
- Implementation: CustomGraphics API or Selection.add()

**8.2 fusion_measure_all_angles**
- Complexity: MEDIUM
- Dependencies: Edge info, face info
- Implementation: Iterate edges/faces, compute angles

**8.3 fusion_get_edge_relationships**
- Complexity: MEDIUM
- Dependencies: Edge info
- Implementation: Topology traversal

---

## Technical Implementation Details

### 1. Edge and Face Indexing System

**Challenge:** Need consistent way to reference specific edges/faces on a body.

**Solution:** Extend existing path system to support numeric indices:
```
Path Format:
  "root/bodies/WingBody/edges/12"
  "root/bodies/WingBody/faces/5"
  "root/occurrences/Component1/bodies/Body1/edges/0"
```

**Implementation in HTTP.py:**
```python
def _resolve_geometry_path(path):
    """
    Resolve path to geometry element (body, edge, face, vertex)
    Returns: (element, element_type)
    """
    parts = path.split('/')

    # Navigate to parent (body or component)
    element, element_type = _resolve_element_path('/'.join(parts[:-2]))

    # Handle geometry-specific indexing
    geo_type = parts[-2]  # 'edges', 'faces', 'vertices'
    geo_index = int(parts[-1])

    if geo_type == 'edges':
        if element_type == 'BRepBody':
            return element.edges.item(geo_index), 'BRepEdge'
    elif geo_type == 'faces':
        if element_type == 'BRepBody':
            return element.faces.item(geo_index), 'BRepFace'
    elif geo_type == 'vertices':
        if element_type == 'BRepBody':
            return element.vertices.item(geo_index), 'BRepVertex'

    raise ValueError(f"Invalid geometry path: {path}")
```

---

### 2. Measurement Operations

**fusion_measure_distance Implementation:**
```python
def _handle_measure_distance(params):
    """
    Measure distance between two entities

    Params:
        mode: 'points' | 'edges' | 'edge_face' | 'faces'
        entity1: path or coordinates
        entity2: path or coordinates

    Returns:
        {
            'distance': float,
            'point1': {x, y, z},
            'point2': {x, y, z},
            'vector': {x, y, z}
        }
    """
    app = adsk.core.Application.get()
    mode = params.get('mode', 'points')

    if mode == 'points':
        # Direct coordinate measurement
        p1 = params['point1']
        p2 = params['point2']
        point1 = adsk.core.Point3D.create(p1['x'], p1['y'], p1['z'])
        point2 = adsk.core.Point3D.create(p2['x'], p2['y'], p2['z'])

        distance = point1.distanceTo(point2)

        return {
            'status': 'success',
            'data': {
                'distance': distance,
                'point1': {'x': point1.x, 'y': point1.y, 'z': point1.z},
                'point2': {'x': point2.x, 'y': point2.y, 'z': point2.z},
                'vector': {
                    'x': point2.x - point1.x,
                    'y': point2.y - point1.y,
                    'z': point2.z - point1.z
                }
            }
        }

    elif mode == 'edges':
        # Minimum distance between two edges
        edge1, _ = _resolve_geometry_path(params['edge1'])
        edge2, _ = _resolve_geometry_path(params['edge2'])

        # Use MeasureManager for edge-to-edge distance
        design = app.activeProduct
        measure_manager = design.measureManager

        # Get minimum distance
        min_distance = measure_manager.measureMinimumDistance(edge1, edge2)

        return {
            'status': 'success',
            'data': {
                'distance': min_distance.value,
                'point1': {
                    'x': min_distance.positionOne.x,
                    'y': min_distance.positionOne.y,
                    'z': min_distance.positionOne.z
                },
                'point2': {
                    'x': min_distance.positionTwo.x,
                    'y': min_distance.positionTwo.y,
                    'z': min_distance.positionTwo.z
                }
            }
        }

    # Similar implementations for edge_face and faces modes...
```

**fusion_measure_angle Implementation:**
```python
def _handle_measure_angle(params):
    """
    Measure angle between two entities

    Params:
        mode: 'edges' | 'faces' | 'edge_face'
        entity1: path to edge or face
        entity2: path to edge or face
        units: 'degrees' | 'radians' (default: degrees)

    Returns:
        {
            'angle': float,
            'units': string,
            'vertex': {x, y, z} (for edges)
        }
    """
    import math

    mode = params.get('mode', 'edges')
    units = params.get('units', 'degrees')

    if mode == 'edges':
        edge1, _ = _resolve_geometry_path(params['edge1'])
        edge2, _ = _resolve_geometry_path(params['edge2'])

        # Get edge tangent vectors at start points
        vec1 = edge1.geometry.startPoint.vectorTo(edge1.geometry.endPoint)
        vec2 = edge2.geometry.startPoint.vectorTo(edge2.geometry.endPoint)

        # Calculate angle between vectors
        angle_rad = vec1.angleTo(vec2)
        angle_deg = math.degrees(angle_rad)

        return {
            'status': 'success',
            'data': {
                'angle': angle_deg if units == 'degrees' else angle_rad,
                'units': units,
                'vector1': {'x': vec1.x, 'y': vec1.y, 'z': vec1.z},
                'vector2': {'x': vec2.x, 'y': vec2.y, 'z': vec2.z}
            }
        }

    elif mode == 'faces':
        face1, _ = _resolve_geometry_path(params['face1'])
        face2, _ = _resolve_geometry_path(params['face2'])

        # Get face normals
        normal1 = face1.geometry.normal
        normal2 = face2.geometry.normal

        # Calculate dihedral angle
        angle_rad = normal1.angleTo(normal2)
        angle_deg = math.degrees(angle_rad)

        return {
            'status': 'success',
            'data': {
                'angle': angle_deg if units == 'degrees' else angle_rad,
                'units': units,
                'type': 'dihedral',
                'normal1': {'x': normal1.x, 'y': normal1.y, 'z': normal1.z},
                'normal2': {'x': normal2.x, 'y': normal2.y, 'z': normal2.z}
            }
        }
```

---

### 3. Edge and Face Information

**fusion_get_edge_info Implementation:**
```python
def _handle_get_edge_info(params):
    """
    Get detailed information about an edge

    Params:
        path: path to edge (e.g., "root/bodies/Body1/edges/5")
        OR
        body_path: path to body
        list_all: true to list all edges

    Returns:
        Single edge info or array of all edges
    """
    if params.get('list_all'):
        # List all edges on a body
        body, _ = _resolve_element_path(params['body_path'])

        edges = []
        for i, edge in enumerate(body.edges):
            edges.append(_get_single_edge_info(edge, i))

        return {
            'status': 'success',
            'data': {
                'body': body.name,
                'edge_count': len(edges),
                'edges': edges
            }
        }
    else:
        # Single edge
        edge, _ = _resolve_geometry_path(params['path'])
        index = int(params['path'].split('/')[-1])

        return {
            'status': 'success',
            'data': _get_single_edge_info(edge, index)
        }

def _get_single_edge_info(edge, index):
    """Extract all info from a single edge"""
    geom = edge.geometry

    info = {
        'index': index,
        'length': edge.length,
        'curve_type': geom.curveType,
        'is_closed': geom.isClosed if hasattr(geom, 'isClosed') else False
    }

    # Start/end points (if not closed)
    if not info['is_closed']:
        start = geom.startPoint
        end = geom.endPoint

        info['start_point'] = {'x': start.x, 'y': start.y, 'z': start.z}
        info['end_point'] = {'x': end.x, 'y': end.y, 'z': end.z}

        # Direction vector
        direction = start.vectorTo(end)
        direction.normalize()
        info['direction'] = {'x': direction.x, 'y': direction.y, 'z': direction.z}

    # Curve-specific properties
    if geom.curveType == adsk.core.Curve3DTypes.Line3DCurveType:
        info['geometry_type'] = 'line'
    elif geom.curveType == adsk.core.Curve3DTypes.Circle3DCurveType:
        info['geometry_type'] = 'circle'
        info['radius'] = geom.radius
        center = geom.center
        info['center'] = {'x': center.x, 'y': center.y, 'z': center.z}
    elif geom.curveType == adsk.core.Curve3DTypes.Arc3DCurveType:
        info['geometry_type'] = 'arc'
        info['radius'] = geom.radius
        center = geom.center
        info['center'] = {'x': center.x, 'y': center.y, 'z': center.z}
        info['start_angle'] = geom.startAngle
        info['end_angle'] = geom.endAngle
    else:
        info['geometry_type'] = 'other'

    return info
```

**fusion_get_face_info Implementation:**
```python
def _handle_get_face_info(params):
    """
    Get detailed information about a face

    Params:
        path: path to face (e.g., "root/bodies/Body1/faces/3")
        OR
        body_path: path to body
        list_all: true to list all faces

    Returns:
        Single face info or array of all faces
    """
    if params.get('list_all'):
        body, _ = _resolve_element_path(params['body_path'])

        faces = []
        for i, face in enumerate(body.faces):
            faces.append(_get_single_face_info(face, i))

        return {
            'status': 'success',
            'data': {
                'body': body.name,
                'face_count': len(faces),
                'faces': faces
            }
        }
    else:
        face, _ = _resolve_geometry_path(params['path'])
        index = int(params['path'].split('/')[-1])

        return {
            'status': 'success',
            'data': _get_single_face_info(face, index)
        }

def _get_single_face_info(face, index):
    """Extract all info from a single face"""
    geom = face.geometry

    info = {
        'index': index,
        'area': face.area,
        'surface_type': geom.surfaceType
    }

    # Centroid
    try:
        centroid = face.centroid
        info['centroid'] = {'x': centroid.x, 'y': centroid.y, 'z': centroid.z}
    except:
        info['centroid'] = None

    # Surface-specific properties
    if geom.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
        info['geometry_type'] = 'planar'
        normal = geom.normal
        info['normal'] = {'x': normal.x, 'y': normal.y, 'z': normal.z}
        origin = geom.origin
        info['origin'] = {'x': origin.x, 'y': origin.y, 'z': origin.z}

    elif geom.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType:
        info['geometry_type'] = 'cylindrical'
        info['radius'] = geom.radius
        origin = geom.origin
        info['origin'] = {'x': origin.x, 'y': origin.y, 'z': origin.z}
        axis = geom.axis
        info['axis'] = {'x': axis.x, 'y': axis.y, 'z': axis.z}

    elif geom.surfaceType == adsk.core.SurfaceTypes.ConeSurfaceType:
        info['geometry_type'] = 'conical'
        info['radius'] = geom.radius
        info['half_angle'] = geom.halfAngle
        origin = geom.origin
        info['origin'] = {'x': origin.x, 'y': origin.y, 'z': origin.z}
        axis = geom.axis
        info['axis'] = {'x': axis.x, 'y': axis.y, 'z': axis.z}

    elif geom.surfaceType == adsk.core.SurfaceTypes.SphereSurfaceType:
        info['geometry_type'] = 'spherical'
        info['radius'] = geom.radius
        origin = geom.origin
        info['origin'] = {'x': origin.x, 'y': origin.y, 'z': origin.z}

    elif geom.surfaceType == adsk.core.SurfaceTypes.TorusSurfaceType:
        info['geometry_type'] = 'toroidal'
        info['major_radius'] = geom.majorRadius
        info['minor_radius'] = geom.minorRadius

    else:
        info['geometry_type'] = 'other'

    # Edge loop count
    info['loop_count'] = face.loops.count

    return info
```

---

### 4. Geometry Query/Search

**fusion_find_edges_by_criteria Implementation:**
```python
def _handle_find_edges_by_criteria(params):
    """
    Find edges matching criteria

    Params:
        body_path: path to body to search
        criteria: {
            length_min: float (optional)
            length_max: float (optional)
            length_equals: float with tolerance (optional)
            curve_type: 'line' | 'arc' | 'circle' | 'spline' (optional)
            near_point: {x, y, z, radius} (optional)
            parallel_to: {x, y, z} direction vector (optional)
            perpendicular_to: {x, y, z} direction vector (optional)
        }

    Returns:
        Array of matching edges with their info and paths
    """
    import math

    body, _ = _resolve_element_path(params['body_path'])
    criteria = params.get('criteria', {})

    matching_edges = []

    for i, edge in enumerate(body.edges):
        if _edge_matches_criteria(edge, criteria):
            edge_info = _get_single_edge_info(edge, i)
            edge_info['path'] = f"{params['body_path']}/edges/{i}"
            matching_edges.append(edge_info)

    return {
        'status': 'success',
        'data': {
            'match_count': len(matching_edges),
            'edges': matching_edges
        }
    }

def _edge_matches_criteria(edge, criteria):
    """Check if edge matches all criteria"""
    import math

    # Length criteria
    if 'length_min' in criteria:
        if edge.length < criteria['length_min']:
            return False

    if 'length_max' in criteria:
        if edge.length > criteria['length_max']:
            return False

    if 'length_equals' in criteria:
        tolerance = criteria.get('length_tolerance', 0.001)
        if abs(edge.length - criteria['length_equals']) > tolerance:
            return False

    # Curve type
    if 'curve_type' in criteria:
        geom = edge.geometry
        curve_type_map = {
            'line': adsk.core.Curve3DTypes.Line3DCurveType,
            'circle': adsk.core.Curve3DTypes.Circle3DCurveType,
            'arc': adsk.core.Curve3DTypes.Arc3DCurveType,
            'spline': adsk.core.Curve3DTypes.NurbsCurve3DCurveType
        }
        if geom.curveType != curve_type_map.get(criteria['curve_type']):
            return False

    # Proximity to point
    if 'near_point' in criteria:
        near = criteria['near_point']
        point = adsk.core.Point3D.create(near['x'], near['y'], near['z'])
        radius = near.get('radius', 1.0)

        # Check if edge's midpoint is within radius
        if not edge.geometry.isClosed:
            mid_param = (edge.geometry.startParameter + edge.geometry.endParameter) / 2
            mid_point = edge.geometry.evaluator.getPointAtParameter(mid_param)[1]

            if mid_point.distanceTo(point) > radius:
                return False

    # Parallel to direction
    if 'parallel_to' in criteria:
        par = criteria['parallel_to']
        target_dir = adsk.core.Vector3D.create(par['x'], par['y'], par['z'])
        target_dir.normalize()

        if not edge.geometry.isClosed:
            edge_dir = edge.geometry.startPoint.vectorTo(edge.geometry.endPoint)
            edge_dir.normalize()

            # Check if parallel (angle close to 0 or 180)
            angle = edge_dir.angleTo(target_dir)
            tolerance = criteria.get('angle_tolerance', 0.01)  # ~0.57 degrees

            if not (angle < tolerance or abs(angle - math.pi) < tolerance):
                return False

    # Perpendicular to direction
    if 'perpendicular_to' in criteria:
        perp = criteria['perpendicular_to']
        target_dir = adsk.core.Vector3D.create(perp['x'], perp['y'], perp['z'])
        target_dir.normalize()

        if not edge.geometry.isClosed:
            edge_dir = edge.geometry.startPoint.vectorTo(edge.geometry.endPoint)
            edge_dir.normalize()

            # Check if perpendicular (angle close to 90)
            angle = edge_dir.angleTo(target_dir)
            tolerance = criteria.get('angle_tolerance', 0.01)

            if abs(angle - math.pi/2) > tolerance:
                return False

    return True
```

---

### 5. Interactive Selection (COMPLEX)

**Challenge:** Need async selection with user interaction in viewport.

**fusion_select_geometry Implementation:**
```python
def _handle_select_geometry(params):
    """
    Interactive geometry selection in viewport

    Params:
        type: 'edge' | 'face' | 'vertex' | 'point'
        multiple: true/false (allow multiple selections)
        prompt: "Select the leading edge..." (user prompt)

    Returns:
        {
            'selections': [
                {
                    'type': 'edge',
                    'path': 'root/bodies/Body1/edges/12',
                    'info': {...edge info...}
                }
            ]
        }

    NOTE: This is ASYNC - may need different handling than other operations
    """
    app = adsk.core.Application.get()
    ui = app.userInterface

    sel_type = params.get('type', 'face')
    multiple = params.get('multiple', False)
    prompt = params.get('prompt', f'Select {sel_type}(s)')

    # Map type to Fusion selection filter
    filter_map = {
        'edge': 'LinearEdges,CircularEdges,SketchCurves',
        'face': 'PlanarFaces,CylindricalFaces,Faces',
        'vertex': 'Vertices,SketchPoints',
        'point': 'SketchPoints,ConstructionPoints'
    }

    try:
        if multiple:
            # Multiple selection
            selections = ui.selectEntity(prompt, filter_map[sel_type])
            # NOTE: This blocks until user makes selection or cancels

            results = []
            for i in range(selections.count):
                entity = selections.item(i).entity
                result = _describe_selected_entity(entity)
                results.append(result)

            return {
                'status': 'success',
                'data': {
                    'count': len(results),
                    'selections': results
                }
            }
        else:
            # Single selection
            selection = ui.selectEntity(prompt, filter_map[sel_type])

            if selection:
                result = _describe_selected_entity(selection.entity)

                return {
                    'status': 'success',
                    'data': result
                }
            else:
                return {
                    'status': 'cancelled',
                    'message': 'User cancelled selection'
                }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

def _describe_selected_entity(entity):
    """Convert selected entity to path + info"""
    # This is COMPLEX - need to reverse-engineer path from entity
    # May need to traverse from root component to find entity

    entity_type = entity.objectType

    if 'BRepEdge' in entity_type:
        # Find which body this edge belongs to
        parent_body = entity.body
        edge_index = _find_edge_index(parent_body, entity)
        body_path = _find_body_path(parent_body)

        return {
            'type': 'edge',
            'path': f"{body_path}/edges/{edge_index}",
            'info': _get_single_edge_info(entity, edge_index)
        }

    elif 'BRepFace' in entity_type:
        parent_body = entity.body
        face_index = _find_face_index(parent_body, entity)
        body_path = _find_body_path(parent_body)

        return {
            'type': 'face',
            'path': f"{body_path}/faces/{face_index}",
            'info': _get_single_face_info(entity, face_index)
        }

    # ... similar for other entity types

def _find_edge_index(body, target_edge):
    """Find index of edge in body's edge collection"""
    for i, edge in enumerate(body.edges):
        if edge == target_edge:
            return i
    return -1

def _find_body_path(body):
    """Reverse-engineer path to body from root component"""
    # This requires traversing from root to find the body
    app = adsk.core.Application.get()
    design = app.activeProduct
    root = design.rootComponent

    # Check root bodies
    for b in root.bRepBodies:
        if b == body:
            return f"root/bodies/{body.name}"

    # Check occurrences
    for occ in root.allOccurrences:
        for b in occ.bRepBodies:
            if b == body:
                return f"root/occurrences/{occ.name}/bodies/{body.name}"

    return None
```

---

### 6. Construction Tools

**fusion_create_plane Implementation:**
```python
def _handle_create_plane(params):
    """
    Create construction plane

    Params:
        mode: 'offset' | 'angle' | 'three_points' | 'perpendicular'

        For offset:
            reference_plane: path to existing plane
            offset: distance in cm

        For angle:
            reference_plane: path
            axis: path to axis or {x,y,z} vector
            angle: degrees

        For three_points:
            point1: {x, y, z}
            point2: {x, y, z}
            point3: {x, y, z}

        For perpendicular:
            edge: path to edge
            point: {x, y, z} point on plane

        name: optional name for plane

    Returns:
        {
            'plane_path': 'root/constructionPlanes/PlaneName',
            'origin': {x, y, z},
            'normal': {x, y, z}
        }
    """
    app = adsk.core.Application.get()
    design = app.activeProduct
    root = design.rootComponent

    mode = params.get('mode', 'offset')
    name = params.get('name', 'ConstructionPlane')

    planes = root.constructionPlanes

    if mode == 'offset':
        # Offset from existing plane
        ref_plane, _ = _resolve_element_path(params['reference_plane'])
        offset = params.get('offset', 0)

        plane_input = planes.createInput()
        plane_input.setByOffset(ref_plane, adsk.core.ValueInput.createByReal(offset))
        plane = planes.add(plane_input)
        plane.name = name

        return {
            'status': 'success',
            'data': {
                'plane_path': f"root/constructionPlanes/{plane.name}",
                'name': plane.name,
                'offset': offset
            }
        }

    elif mode == 'three_points':
        # Plane through three points
        p1_data = params['point1']
        p2_data = params['point2']
        p3_data = params['point3']

        p1 = adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data['z'])
        p2 = adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data['z'])
        p3 = adsk.core.Point3D.create(p3_data['x'], p3_data['y'], p3_data['z'])

        plane_input = planes.createInput()
        plane_input.setByThreePoints(p1, p2, p3)
        plane = planes.add(plane_input)
        plane.name = name

        # Calculate normal
        v1 = p1.vectorTo(p2)
        v2 = p1.vectorTo(p3)
        normal = v1.crossProduct(v2)
        normal.normalize()

        return {
            'status': 'success',
            'data': {
                'plane_path': f"root/constructionPlanes/{plane.name}",
                'name': plane.name,
                'origin': p1_data,
                'normal': {'x': normal.x, 'y': normal.y, 'z': normal.z}
            }
        }

    # ... other modes
```

---

### 7. Body Modification

**fusion_split_body Implementation:**
```python
def _handle_split_body(params):
    """
    Split a body with a plane or face

    Params:
        body_path: path to body to split
        split_tool: path to plane or face
        keep_both: true/false (default true)

    Returns:
        {
            'original_body': path,
            'new_bodies': [paths...],
            'feature_name': string
        }

    WARNING: This modifies the design and creates a timeline feature
    """
    app = adsk.core.Application.get()
    design = app.activeProduct
    root = design.rootComponent

    # Get body to split
    body, _ = _resolve_element_path(params['body_path'])

    # Get split tool (plane or face)
    split_tool, tool_type = _resolve_element_path(params['split_tool'])

    keep_both = params.get('keep_both', True)

    # Create split body feature
    split_features = root.features.splitBodyFeatures

    # Create input
    split_input = split_features.createInput(
        body,  # body to split
        split_tool,  # splitting tool
        not keep_both  # if true, keeps both sides; if false, removes one side
    )

    # Execute split
    split_feature = split_features.add(split_input)

    # Get resulting bodies
    new_body_paths = []
    for body in split_feature.bodies:
        # Find path to new body
        path = _find_body_path(body)
        new_body_paths.append(path)

    return {
        'status': 'success',
        'data': {
            'feature_name': split_feature.name,
            'body_count': len(new_body_paths),
            'bodies': new_body_paths
        }
    }
```

**fusion_extrude_cut/add Implementation:**
```python
def _handle_extrude(params):
    """
    Extrude a profile (add or cut)

    Params:
        operation: 'add' | 'cut' | 'intersect'
        profile_path: path to sketch profile or face
        distance: extrude distance (can be negative)
        direction: 'symmetric' | 'one_side' | 'two_sides'
        taper_angle: optional taper in degrees

    Returns:
        {
            'feature_name': string,
            'bodies': [paths to affected/created bodies]
        }
    """
    app = adsk.core.Application.get()
    design = app.activeProduct
    root = design.rootComponent

    operation = params.get('operation', 'add')
    distance = params.get('distance', 1.0)

    # Get profile (sketch profile or face)
    profile, profile_type = _resolve_element_path(params['profile_path'])

    # Create extrude feature
    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    # Set operation type
    if operation == 'add':
        extrude_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    elif operation == 'cut':
        extrude_input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    elif operation == 'intersect':
        extrude_input.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation

    # Set extent
    distance_value = adsk.core.ValueInput.createByReal(distance)
    extrude_input.setDistanceExtent(False, distance_value)

    # Optional taper
    if 'taper_angle' in params:
        taper = params['taper_angle']
        extrude_input.taperAngle = adsk.core.ValueInput.createByReal(math.radians(taper))

    # Execute extrude
    extrude_feature = extrudes.add(extrude_input)

    # Get resulting bodies
    body_paths = []
    for body in extrude_feature.bodies:
        path = _find_body_path(body)
        body_paths.append(path)

    return {
        'status': 'success',
        'data': {
            'feature_name': extrude_feature.name,
            'bodies': body_paths
        }
    }
```

---

## MCP Server Tool Definitions

### Phase 1 Tools (Measurement & Analysis)

```python
types.Tool(
    name="fusion_measure_distance",
    description="Measure distance between two entities (points, edges, faces). Returns precise measurements with coordinates.",
    inputSchema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["points", "edges", "edge_face", "faces"],
                "description": "Type of measurement"
            },
            "point1": {
                "type": "object",
                "description": "First point coordinates (for mode='points')",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"}
                }
            },
            "point2": {
                "type": "object",
                "description": "Second point coordinates (for mode='points')",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"}
                }
            },
            "edge1": {
                "type": "string",
                "description": "Path to first edge (for mode='edges')"
            },
            "edge2": {
                "type": "string",
                "description": "Path to second edge (for mode='edges')"
            }
        },
        "required": ["mode"]
    }
),

types.Tool(
    name="fusion_measure_angle",
    description="Measure angle between two edges or faces. Returns angle in degrees or radians.",
    inputSchema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["edges", "faces", "edge_face"],
                "description": "Type of angle measurement"
            },
            "edge1": {
                "type": "string",
                "description": "Path to first edge (for edges mode)"
            },
            "edge2": {
                "type": "string",
                "description": "Path to second edge (for edges mode)"
            },
            "face1": {
                "type": "string",
                "description": "Path to first face (for faces mode)"
            },
            "face2": {
                "type": "string",
                "description": "Path to second face (for faces mode)"
            },
            "units": {
                "type": "string",
                "enum": ["degrees", "radians"],
                "default": "degrees"
            }
        },
        "required": ["mode"]
    }
),

types.Tool(
    name="fusion_get_edge_info",
    description="Get detailed information about edge(s): length, start/end points, direction, curve type. Can list all edges on a body.",
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to specific edge (e.g., 'root/bodies/Body1/edges/5')"
            },
            "body_path": {
                "type": "string",
                "description": "Path to body (when list_all=true)"
            },
            "list_all": {
                "type": "boolean",
                "description": "If true, list all edges on the body",
                "default": False
            }
        }
    }
),

types.Tool(
    name="fusion_get_face_info",
    description="Get detailed information about face(s): area, normal vector, center point, surface type. Can list all faces on a body.",
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to specific face (e.g., 'root/bodies/Body1/faces/3')"
            },
            "body_path": {
                "type": "string",
                "description": "Path to body (when list_all=true)"
            },
            "list_all": {
                "type": "boolean",
                "description": "If true, list all faces on the body",
                "default": False
            }
        }
    }
),

types.Tool(
    name="fusion_select_geometry",
    description="Interactive selection of geometry in viewport. User clicks to select edges, faces, or vertices. BLOCKING operation.",
    inputSchema={
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["edge", "face", "vertex", "point"],
                "description": "Type of geometry to select"
            },
            "multiple": {
                "type": "boolean",
                "description": "Allow multiple selections",
                "default": False
            },
            "prompt": {
                "type": "string",
                "description": "Message shown to user during selection",
                "default": "Select geometry"
            }
        },
        "required": ["type"]
    }
)
```

### Phase 2 Tools (Geometry Query)

```python
types.Tool(
    name="fusion_find_edges_by_criteria",
    description="Search for edges matching criteria: length, curve type, location, orientation. Returns array of matching edges with full info.",
    inputSchema={
        "type": "object",
        "properties": {
            "body_path": {
                "type": "string",
                "description": "Path to body to search"
            },
            "criteria": {
                "type": "object",
                "description": "Search criteria",
                "properties": {
                    "length_min": {"type": "number"},
                    "length_max": {"type": "number"},
                    "length_equals": {"type": "number"},
                    "length_tolerance": {"type": "number", "default": 0.001},
                    "curve_type": {
                        "type": "string",
                        "enum": ["line", "arc", "circle", "spline"]
                    },
                    "near_point": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"},
                            "radius": {"type": "number"}
                        }
                    },
                    "parallel_to": {
                        "type": "object",
                        "description": "Direction vector {x,y,z}",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "perpendicular_to": {
                        "type": "object",
                        "description": "Direction vector {x,y,z}",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    }
                }
            }
        },
        "required": ["body_path"]
    }
),

types.Tool(
    name="fusion_find_faces_by_criteria",
    description="Search for faces matching criteria: area, normal direction, surface type. Returns array of matching faces.",
    inputSchema={
        "type": "object",
        "properties": {
            "body_path": {
                "type": "string",
                "description": "Path to body to search"
            },
            "criteria": {
                "type": "object",
                "properties": {
                    "area_min": {"type": "number"},
                    "area_max": {"type": "number"},
                    "surface_type": {
                        "type": "string",
                        "enum": ["planar", "cylindrical", "conical", "spherical", "toroidal"]
                    },
                    "normal_direction": {
                        "type": "object",
                        "description": "Faces with normal in this direction",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    }
                }
            }
        },
        "required": ["body_path"]
    }
)
```

### Phase 3 Tools (Construction)

```python
types.Tool(
    name="fusion_create_plane",
    description="Create construction plane: offset from existing, at angle, through three points, or perpendicular to edge.",
    inputSchema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["offset", "angle", "three_points", "perpendicular"],
                "description": "Construction method"
            },
            "reference_plane": {
                "type": "string",
                "description": "Path to reference plane (for offset/angle modes)"
            },
            "offset": {
                "type": "number",
                "description": "Offset distance in cm (for offset mode)"
            },
            "point1": {"type": "object"},
            "point2": {"type": "object"},
            "point3": {"type": "object"},
            "name": {
                "type": "string",
                "description": "Name for the plane",
                "default": "ConstructionPlane"
            }
        },
        "required": ["mode"]
    }
)
```

### Phase 4 Tools (Transform)

```python
types.Tool(
    name="fusion_move_body",
    description="Move a body by vector or to specific location. Non-destructive transform.",
    inputSchema={
        "type": "object",
        "properties": {
            "body_path": {"type": "string"},
            "vector": {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"}
                }
            }
        },
        "required": ["body_path", "vector"]
    }
),

types.Tool(
    name="fusion_rotate_body",
    description="Rotate a body around axis by angle.",
    inputSchema={
        "type": "object",
        "properties": {
            "body_path": {"type": "string"},
            "axis": {
                "type": "object",
                "description": "Rotation axis origin and direction",
                "properties": {
                    "origin": {"type": "object"},
                    "direction": {"type": "object"}
                }
            },
            "angle": {
                "type": "number",
                "description": "Rotation angle in degrees"
            }
        },
        "required": ["body_path", "axis", "angle"]
    }
)
```

### Phase 5 Tools (Modification)

```python
types.Tool(
    name="fusion_split_body",
    description="Split a body with a plane or face. Creates timeline feature. WARNING: Modifies design.",
    inputSchema={
        "type": "object",
        "properties": {
            "body_path": {
                "type": "string",
                "description": "Path to body to split"
            },
            "split_tool": {
                "type": "string",
                "description": "Path to plane or face used for splitting"
            },
            "keep_both": {
                "type": "boolean",
                "description": "Keep both sides of split",
                "default": True
            }
        },
        "required": ["body_path", "split_tool"]
    }
),

types.Tool(
    name="fusion_extrude",
    description="Extrude a profile to add/cut/intersect material. Creates timeline feature. Requires sketch profile or face.",
    inputSchema={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add", "cut", "intersect"],
                "description": "Type of extrude operation"
            },
            "profile_path": {
                "type": "string",
                "description": "Path to sketch profile or face"
            },
            "distance": {
                "type": "number",
                "description": "Extrude distance (negative for opposite direction)"
            },
            "taper_angle": {
                "type": "number",
                "description": "Optional taper angle in degrees"
            }
        },
        "required": ["operation", "profile_path", "distance"]
    }
)
```

---

## Implementation Checklist

### Phase 1: Measurement & Analysis (2-3 days)
- [ ] Implement edge/face indexing system in `_resolve_geometry_path()`
- [ ] Add `_handle_measure_distance()` with all 4 modes
- [ ] Add `_handle_measure_angle()` with all 3 modes
- [ ] Add `_handle_get_edge_info()` with list_all support
- [ ] Add `_handle_get_face_info()` with list_all support
- [ ] Add `_handle_select_geometry()` (COMPLEX - interactive)
- [ ] Add 5 new MCP tools to `handle_list_tools()`
- [ ] Update operation routing in `MainThreadExecutor.notify()`
- [ ] Test each measurement tool independently
- [ ] Test edge/face listing on complex geometry
- [ ] Test interactive selection workflow

### Phase 2: Geometry Query (1-2 days)
- [ ] Add `_edge_matches_criteria()` helper function
- [ ] Add `_handle_find_edges_by_criteria()` with all criteria types
- [ ] Add `_face_matches_criteria()` helper function
- [ ] Add `_handle_find_faces_by_criteria()` with all criteria types
- [ ] Add 2 new MCP tools
- [ ] Test search with various criteria combinations
- [ ] Test performance on large bodies (100+ edges/faces)

### Phase 3: Construction Tools (1 day)
- [ ] Add `_handle_create_plane()` with 4 modes
- [ ] Add `_handle_create_axis()`
- [ ] Add 2 new MCP tools
- [ ] Test plane creation in various scenarios
- [ ] Verify planes appear in tree

### Phase 4: Transform Tools (1 day)
- [ ] Add `_handle_move_body()`
- [ ] Add `_handle_rotate_body()`
- [ ] Add `_handle_mirror_body()`
- [ ] Add 3 new MCP tools
- [ ] Test transforms preserve body properties
- [ ] Test undo/redo works correctly

### Phase 5: Body Modification (2-3 days - HIGH RISK)
- [ ] Add `_handle_split_body()`
- [ ] Add `_handle_extrude()` with operation modes
- [ ] Add `_handle_boolean_operations()`
- [ ] Add 3 new MCP tools
- [ ] Test on simple geometry first
- [ ] Test timeline behavior
- [ ] Test with parametric vs non-parametric designs
- [ ] Add extensive error handling

### Phase 6: Sketch Tools (3-4 days - HIGH COMPLEXITY)
- [ ] Add `_handle_create_sketch()`
- [ ] Add `_handle_sketch_add_line()`
- [ ] Add `_handle_sketch_add_constraint()`
- [ ] Add `_handle_sketch_add_dimension()`
- [ ] Add 4 new MCP tools
- [ ] Test sketch creation workflow
- [ ] Test constraints don't over-constrain
- [ ] Test dimensions update correctly

### Phase 7: Feature/Timeline (1-2 days)
- [ ] Add `_handle_get_features()`
- [ ] Add `_handle_edit_feature()` (COMPLEX - timeline)
- [ ] Add `_handle_suppress_feature()`
- [ ] Add 3 new MCP tools
- [ ] Test feature editing doesn't break design
- [ ] Test suppression cascades correctly

### Phase 8: Visualization/Helpers (1 day)
- [ ] Add `_handle_highlight_geometry()`
- [ ] Add `_handle_measure_all_angles()`
- [ ] Add `_handle_get_edge_relationships()`
- [ ] Add 3 new MCP tools
- [ ] Test highlighting is visible
- [ ] Test relationship detection accuracy

---

## Risk Assessment & Mitigation

### High Risk Operations

**1. Interactive Selection (`fusion_select_geometry`)**
- **Risk:** Blocks MCP server while waiting for user input, may timeout
- **Mitigation:**
  - Implement with generous timeout (60+ seconds)
  - Consider async/callback pattern if blocking is problematic
  - Add cancellation support

**2. Timeline-Modifying Operations (split, extrude, edit_feature)**
- **Risk:** Can break downstream features in parametric designs
- **Mitigation:**
  - Always document that these are destructive
  - Recommend user saves design before using
  - Consider adding "dry run" mode that simulates without committing
  - Return detailed error messages if feature fails

**3. Sketch Constraints (`fusion_sketch_add_constraint`)**
- **Risk:** Over-constraining sketch, breaking existing constraints
- **Mitigation:**
  - Check constraint health before/after adding
  - Return constraint status in response
  - Allow "try" mode that rolls back if over-constrained

### Medium Risk Operations

**4. Path Resolution for Edge/Face Indices**
- **Risk:** Indices may change if geometry is modified
- **Mitigation:**
  - Document that indices are ephemeral
  - Recommend using `fusion_find_edges_by_criteria` for robust selection
  - Consider adding stable ID system in future

**5. Performance on Large Designs**
- **Risk:** Iterating 1000+ edges/faces may be slow
- **Mitigation:**
  - Add pagination support for large result sets
  - Add timeout warnings to documentation
  - Consider caching edge/face info

---

## Documentation Requirements

For each new tool, document:

1. **Purpose** - What does it do?
2. **Use Cases** - When would you use it?
3. **Limitations** - What can't it do?
4. **Risk Level** - Read-only vs modifying
5. **Example Workflows** - Step-by-step usage
6. **Error Scenarios** - Common failures and solutions

Example workflow documentation:

```markdown
## Workflow: Measure Wing Sweep Angle

**Goal:** Measure the sweep angle of an aircraft wing leading edge.

**Steps:**
1. Use `fusion_get_tree` to see the design structure
2. Use `fusion_get_edge_info` with `list_all=true` on wing body to see all edges
3. Use `fusion_find_edges_by_criteria` to find longest edges (likely leading/trailing edge)
4. Verify correct edge with `fusion_screenshot` and `fusion_highlight_geometry`
5. Use `fusion_measure_angle` with mode='edges' to measure sweep angle between leading edge and reference axis
6. Use `fusion_create_plane` perpendicular to leading edge for further analysis

**Alternative:**
- Use `fusion_select_geometry` to interactively click the leading edge
- Use the returned path directly in `fusion_measure_angle`
```

---

## Testing Strategy

### Unit Tests (Per Operation)
Each handler function should be tested with:
- Valid inputs
- Invalid inputs (wrong types, missing params)
- Edge cases (empty bodies, zero-length edges, etc.)
- Performance tests on large geometry

### Integration Tests
Test workflows that combine multiple operations:
- Measure → Create Plane → Split
- Find Edges → Highlight → Measure
- Select → Get Info → Create Sketch

### Regression Tests
After implementation, create test suite:
- Test against known design files
- Verify measurements match Fusion UI measurements
- Verify splits produce expected body count
- Verify sketches are fully constrained

---

## Version Planning

**v5.0 (Phase 1-2 Complete):**
- Measurement tools
- Geometry query tools
- Edge/face indexing system
- Read-only operations only
- Est. completion: 1 week

**v5.1 (Phase 3-4 Complete):**
- Construction tools
- Transform tools
- Still non-destructive
- Est. completion: +3 days

**v5.2 (Phase 5 Complete):**
- Body modification tools
- First destructive operations
- Extensive error handling
- Est. completion: +1 week

**v6.0 (All Phases Complete):**
- Sketch tools
- Feature timeline tools
- Full parametric design support
- Comprehensive documentation
- Est. completion: +2 weeks

---

## API References

- [MeasureManager](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/MeasureManager.htm)
- [BRepEdge](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepEdge.htm)
- [BRepFace](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepFace.htm)
- [Sketches](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Sketches.htm)
- [ExtrudeFeature](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExtrudeFeature.htm)
- [SplitBodyFeature](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SplitBodyFeature.htm)
- [ConstructionPlanes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ConstructionPlanes.htm)
- [GeometricConstraints](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/GeometricConstraints.htm)
- [Timeline](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Timeline.htm)

---

## Notes

- This plan dramatically expands capabilities from 6 to 30+ tools
- Implementation should be incremental, testing each phase before proceeding
- Phase 1-2 (measurement/query) provides immediate value with low risk
- Phase 5-6 (modification/sketch) requires extensive testing due to complexity
- Consider user feedback after Phase 1-2 before implementing later phases
- Total estimated implementation time: 3-4 weeks
