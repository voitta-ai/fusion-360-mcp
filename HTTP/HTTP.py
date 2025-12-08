import adsk.core, adsk.fusion, traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import queue
import time
import base64
import tempfile
import os 

# Queue for operations that need main thread
_operation_queue = queue.Queue()
_results_queue = {}
_custom_event = None
_custom_event_handler = None

def _handle_screenshot(params):
    """Capture viewport screenshot and return as base64"""
    width = params.get('width', 800)
    height = params.get('height', 600)

    # Create temp file
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    temp_path = temp_file.name
    temp_file.close()

    try:
        # Capture screenshot
        app = adsk.core.Application.get()
        app.activeViewport.saveAsImageFile(temp_path, width, height)

        # Read as base64
        with open(temp_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        return {
            'status': 'success',
            'data': {
                'image': image_data,
                'mimeType': 'image/png',
                'width': width,
                'height': height
            }
        }
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

def _handle_get_camera(params):
    """Get current camera position and orientation"""
    app = adsk.core.Application.get()
    camera = app.activeViewport.camera

    return {
        'status': 'success',
        'data': {
            'eye': {
                'x': camera.eye.x,
                'y': camera.eye.y,
                'z': camera.eye.z
            },
            'target': {
                'x': camera.target.x,
                'y': camera.target.y,
                'z': camera.target.z
            },
            'upVector': {
                'x': camera.upVector.x,
                'y': camera.upVector.y,
                'z': camera.upVector.z
            },
            'viewOrientation': camera.viewOrientation,
            'isSmoothTransition': camera.isSmoothTransition,
            'perspectiveAngle': camera.perspectiveAngle if camera.cameraType == 0 else None
        }
    }

def _handle_set_camera(params):
    """Set camera position and orientation"""
    app = adsk.core.Application.get()
    viewport = app.activeViewport
    camera = viewport.camera

    # Update camera properties
    if 'eye' in params:
        eye = params['eye']
        camera.eye = adsk.core.Point3D.create(eye['x'], eye['y'], eye['z'])

    if 'target' in params:
        target = params['target']
        camera.target = adsk.core.Point3D.create(target['x'], target['y'], target['z'])

    if 'upVector' in params:
        up = params['upVector']
        camera.upVector = adsk.core.Vector3D.create(up['x'], up['y'], up['z'])

    if 'viewOrientation' in params:
        camera.viewOrientation = params['viewOrientation']

    if 'isSmoothTransition' in params:
        camera.isSmoothTransition = params['isSmoothTransition']

    # Apply camera
    viewport.camera = camera

    return {'status': 'success', 'message': 'Camera updated'}

def _resolve_element_path(path):
    """
    Resolve element path to object
    Returns: (element, element_type)
    """
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        raise ValueError('No active design')

    root = design.rootComponent
    parts = path.split('/')

    if len(parts) == 0 or parts[0] != 'root':
        raise ValueError('Path must start with "root"')

    current = root
    i = 1

    while i < len(parts):
        part = parts[i]

        # Accept both 'bodies' and 'bRepBodies' for body paths
        if part in ['bodies', 'bRepBodies']:
            if i + 1 >= len(parts):
                raise ValueError('Body name missing')
            body_name = parts[i + 1]

            # Debug: List available bodies
            available_bodies = [body.name for body in current.bRepBodies]

            for body in current.bRepBodies:
                if body.name == body_name:
                    return (body, 'BRepBody')

            # Enhanced error message with available bodies
            raise ValueError(f'Body "{body_name}" not found. Available: {available_bodies}')

        # Accept both 'occurrences' and 'children' for occurrence paths
        elif part in ['occurrences', 'children']:
            if i + 1 >= len(parts):
                raise ValueError('Occurrence name missing')
            occ_name = parts[i + 1]

            # Debug: List available occurrences
            available_occs = [occ.name for occ in current.occurrences]

            found = False
            for occ in current.occurrences:
                if occ.name == occ_name:
                    if i + 2 >= len(parts):
                        return (occ, 'Occurrence')
                    current = occ.component
                    i += 2
                    found = True
                    break

            if not found:
                # Enhanced error message with available occurrences
                raise ValueError(f'Occurrence "{occ_name}" not found. Available: {available_occs}')

            # Skip the i += 1 at the end since we already incremented by 2
            continue

        i += 1

    return (root, 'Component')

def _resolve_geometry_path(path):
    """
    Resolve geometry path (with edges/faces) to object
    Returns: (element, element_type)
    """
    parts = path.split('/')

    # Check if this is a geometry path (ends with edges/X or faces/X)
    if len(parts) >= 2:
        geo_category = parts[-2]

        if geo_category in ['edges', 'faces', 'vertices']:
            # Get parent element
            parent_path = '/'.join(parts[:-2])
            parent, parent_type = _resolve_element_path(parent_path)

            if parent_type != 'BRepBody':
                raise ValueError(f'Geometry parent must be a body, got {parent_type}')

            geo_index = int(parts[-1])

            if geo_category == 'edges':
                if geo_index < 0 or geo_index >= parent.edges.count:
                    raise ValueError(f'Edge index {geo_index} out of range (0-{parent.edges.count-1})')
                return (parent.edges.item(geo_index), 'BRepEdge')

            elif geo_category == 'faces':
                if geo_index < 0 or geo_index >= parent.faces.count:
                    raise ValueError(f'Face index {geo_index} out of range (0-{parent.faces.count-1})')
                return (parent.faces.item(geo_index), 'BRepFace')

            elif geo_category == 'vertices':
                if geo_index < 0 or geo_index >= parent.vertices.count:
                    raise ValueError(f'Vertex index {geo_index} out of range (0-{parent.vertices.count-1})')
                return (parent.vertices.item(geo_index), 'BRepVertex')

    # Not a geometry path, resolve as element
    return _resolve_element_path(path)

def _handle_measure_distance(params):
    """Measure distance between entities"""
    import math

    mode = params.get('mode', 'points')

    if mode == 'points':
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
        edge1, _ = _resolve_geometry_path(params['edge1'])
        edge2, _ = _resolve_geometry_path(params['edge2'])

        # Get start/end points for distance calculation - handle different curve types
        geom1 = edge1.geometry
        geom2 = edge2.geometry

        # Get points for edge 1
        if hasattr(geom1, 'startPoint') and hasattr(geom1, 'endPoint'):
            p1_start = geom1.startPoint
            p1_end = geom1.endPoint
        else:
            # For curves without direct access (Circle, Ellipse, etc.), use evaluator
            evaluator1 = geom1.evaluator
            extents1 = evaluator1.getParameterExtents()
            success, p1_start = evaluator1.getPointAtParameter(extents1[1])  # Start param
            success, p1_end = evaluator1.getPointAtParameter(extents1[2])    # End param

        # Get points for edge 2
        if hasattr(geom2, 'startPoint') and hasattr(geom2, 'endPoint'):
            p2_start = geom2.startPoint
            p2_end = geom2.endPoint
        else:
            # For curves without direct access (Circle, Ellipse, etc.), use evaluator
            evaluator2 = geom2.evaluator
            extents2 = evaluator2.getParameterExtents()
            success, p2_start = evaluator2.getPointAtParameter(extents2[1])  # Start param
            success, p2_end = evaluator2.getPointAtParameter(extents2[2])    # End param

        # Find minimum distance between the four point combinations
        distances = [
            p1_start.distanceTo(p2_start),
            p1_start.distanceTo(p2_end),
            p1_end.distanceTo(p2_start),
            p1_end.distanceTo(p2_end)
        ]
        min_dist = min(distances)

        return {
            'status': 'success',
            'data': {
                'distance': min_dist,
                'edge1_length': edge1.length,
                'edge2_length': edge2.length
            }
        }

    else:
        return {'status': 'error', 'message': f'Unsupported mode: {mode}'}

def _handle_measure_angle(params):
    """Measure angle between entities"""
    import math

    mode = params.get('mode', 'edges')
    units = params.get('units', 'degrees')

    if mode == 'edges':
        edge1, _ = _resolve_geometry_path(params['edge1'])
        edge2, _ = _resolve_geometry_path(params['edge2'])

        # Get edge direction vectors
        geom1 = edge1.geometry
        geom2 = edge2.geometry

        # Get start/end points - handle different curve types
        # Curves with direct startPoint/endPoint access
        if hasattr(geom1, 'startPoint') and hasattr(geom1, 'endPoint'):
            start1 = geom1.startPoint
            end1 = geom1.endPoint
        else:
            # For curves without direct access (Circle, Ellipse, etc.), use evaluator
            evaluator1 = geom1.evaluator
            extents1 = evaluator1.getParameterExtents()
            success, start1 = evaluator1.getPointAtParameter(extents1[1])  # Start param
            success, end1 = evaluator1.getPointAtParameter(extents1[2])    # End param

        if hasattr(geom2, 'startPoint') and hasattr(geom2, 'endPoint'):
            start2 = geom2.startPoint
            end2 = geom2.endPoint
        else:
            # For curves without direct access (Circle, Ellipse, etc.), use evaluator
            evaluator2 = geom2.evaluator
            extents2 = evaluator2.getParameterExtents()
            success, start2 = evaluator2.getPointAtParameter(extents2[1])  # Start param
            success, end2 = evaluator2.getPointAtParameter(extents2[2])    # End param

        # Create direction vectors
        vec1 = start1.vectorTo(end1)
        vec2 = start2.vectorTo(end2)

        # Handle closed curves (like full circles) - use tangent at midpoint instead
        if vec1.length < 0.001:  # Closed curve
            evaluator1 = geom1.evaluator
            extents1 = evaluator1.getParameterExtents()
            mid_param1 = (extents1[1] + extents1[2]) / 2.0
            success, vec1 = evaluator1.getTangent(mid_param1)

        if vec2.length < 0.001:  # Closed curve
            evaluator2 = geom2.evaluator
            extents2 = evaluator2.getParameterExtents()
            mid_param2 = (extents2[1] + extents2[2]) / 2.0
            success, vec2 = evaluator2.getTangent(mid_param2)

        vec1.normalize()
        vec2.normalize()

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
        eval1 = face1.evaluator
        eval2 = face2.evaluator

        # Get normals at face centers
        result1, param_point1 = eval1.getParametersAtPoint(face1.centroid)
        result2, normal1 = eval1.getNormalAtPoint(param_point1)

        result1, param_point2 = eval2.getParametersAtPoint(face2.centroid)
        result2, normal2 = eval2.getNormalAtPoint(param_point2)

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

    else:
        return {'status': 'error', 'message': f'Unsupported mode: {mode}'}

def _get_edge_info(edge, index):
    """Get detailed info about an edge"""
    geom = edge.geometry

    info = {
        'index': index,
        'length': edge.length
    }

    # Get start/end points - handle different curve types
    curve_type = geom.curveType

    # Curves with direct startPoint/endPoint access
    if hasattr(geom, 'startPoint') and hasattr(geom, 'endPoint'):
        start = geom.startPoint
        end = geom.endPoint
    else:
        # For curves without direct access (Circle, Ellipse, etc.), use evaluator
        evaluator = geom.evaluator
        success, start = evaluator.getPointAtParameter(evaluator.getParameterExtents()[1])  # Start param
        success, end = evaluator.getPointAtParameter(evaluator.getParameterExtents()[2])    # End param

    info['start_point'] = {'x': start.x, 'y': start.y, 'z': start.z}
    info['end_point'] = {'x': end.x, 'y': end.y, 'z': end.z}

    # Direction vector (for curves that aren't closed)
    if start.distanceTo(end) > 0.001:  # Not a closed curve
        direction = start.vectorTo(end)
        direction.normalize()
        info['direction'] = {'x': direction.x, 'y': direction.y, 'z': direction.z}
    else:
        info['direction'] = None  # Closed curve (like full circle)

    # Detailed curve type info
    if curve_type == adsk.core.Curve3DTypes.Line3DCurveType:
        info['curve_type'] = 'line'
    elif curve_type == adsk.core.Curve3DTypes.Circle3DCurveType:
        info['curve_type'] = 'circle'
        info['radius'] = geom.radius
    elif curve_type == adsk.core.Curve3DTypes.Arc3DCurveType:
        info['curve_type'] = 'arc'
        info['radius'] = geom.radius
    elif curve_type == adsk.core.Curve3DTypes.Ellipse3DCurveType:
        info['curve_type'] = 'ellipse'
        info['majorRadius'] = geom.majorRadius
        info['minorRadius'] = geom.minorRadius
    elif curve_type == adsk.core.Curve3DTypes.EllipticalArc3DCurveType:
        info['curve_type'] = 'elliptical_arc'
        info['majorRadius'] = geom.majorRadius
        info['minorRadius'] = geom.minorRadius
    elif curve_type == adsk.core.Curve3DTypes.NurbsCurve3DCurveType:
        info['curve_type'] = 'nurbs'
        info['degree'] = geom.degree
    else:
        info['curve_type'] = 'other'

    return info

def _handle_get_edge_info(params):
    """Get edge information"""
    if params.get('list_all'):
        body, _ = _resolve_element_path(params['body_path'])

        edges = []
        for i in range(body.edges.count):
            edge = body.edges.item(i)
            edges.append(_get_edge_info(edge, i))

        return {
            'status': 'success',
            'data': {
                'body': body.name,
                'edge_count': len(edges),
                'edges': edges
            }
        }
    else:
        edge, _ = _resolve_geometry_path(params['path'])
        index = int(params['path'].split('/')[-1])

        return {
            'status': 'success',
            'data': _get_edge_info(edge, index)
        }

def _get_face_info(face, index):
    """Get detailed info about a face"""
    geom = face.geometry

    info = {
        'index': index,
        'area': face.area
    }

    # Centroid
    try:
        centroid = face.centroid
        info['centroid'] = {'x': centroid.x, 'y': centroid.y, 'z': centroid.z}
    except:
        info['centroid'] = None

    # Surface type
    surface_type = geom.surfaceType
    if surface_type == adsk.core.SurfaceTypes.PlaneSurfaceType:
        info['surface_type'] = 'planar'
        normal = geom.normal
        info['normal'] = {'x': normal.x, 'y': normal.y, 'z': normal.z}
    elif surface_type == adsk.core.SurfaceTypes.CylinderSurfaceType:
        info['surface_type'] = 'cylindrical'
        info['radius'] = geom.radius
    elif surface_type == adsk.core.SurfaceTypes.ConeSurfaceType:
        info['surface_type'] = 'conical'
    elif surface_type == adsk.core.SurfaceTypes.SphereSurfaceType:
        info['surface_type'] = 'spherical'
        info['radius'] = geom.radius
    else:
        info['surface_type'] = 'other'

    return info

def _handle_get_face_info(params):
    """Get face information"""
    if params.get('list_all'):
        body, _ = _resolve_element_path(params['body_path'])

        faces = []
        for i in range(body.faces.count):
            face = body.faces.item(i)
            faces.append(_get_face_info(face, i))

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
            'data': _get_face_info(face, index)
        }

def _edge_matches_criteria(edge, criteria):
    """Check if edge matches all search criteria"""
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

    # Curve type criteria
    if 'curve_type' in criteria:
        geom = edge.geometry
        curve_type_map = {
            'line': adsk.core.Curve3DTypes.Line3DCurveType,
            'circle': adsk.core.Curve3DTypes.Circle3DCurveType,
            'arc': adsk.core.Curve3DTypes.Arc3DCurveType,
            'ellipse': adsk.core.Curve3DTypes.Ellipse3DCurveType,
            'elliptical_arc': adsk.core.Curve3DTypes.EllipticalArc3DCurveType,
            'spline': adsk.core.Curve3DTypes.NurbsCurve3DCurveType
        }
        if geom.curveType != curve_type_map.get(criteria['curve_type']):
            return False

    # Get edge points for directional tests
    geom = edge.geometry
    if hasattr(geom, 'startPoint') and hasattr(geom, 'endPoint'):
        start_point = geom.startPoint
        end_point = geom.endPoint
    else:
        # Use evaluator for curves without direct access
        evaluator = geom.evaluator
        extents = evaluator.getParameterExtents()
        success, start_point = evaluator.getPointAtParameter(extents[1])
        success, end_point = evaluator.getPointAtParameter(extents[2])

    # Proximity to point criteria
    if 'near_point' in criteria:
        near = criteria['near_point']
        point = adsk.core.Point3D.create(near['x'], near['y'], near['z'])
        radius = near.get('radius', 1.0)

        # Check if edge's midpoint is within radius
        mid_x = (start_point.x + end_point.x) / 2.0
        mid_y = (start_point.y + end_point.y) / 2.0
        mid_z = (start_point.z + end_point.z) / 2.0
        mid_point = adsk.core.Point3D.create(mid_x, mid_y, mid_z)

        if mid_point.distanceTo(point) > radius:
            return False

    # Parallel to direction criteria
    if 'parallel_to' in criteria:
        par = criteria['parallel_to']
        target_dir = adsk.core.Vector3D.create(par['x'], par['y'], par['z'])
        target_dir.normalize()

        # Skip closed curves (circles)
        if start_point.distanceTo(end_point) > 0.001:
            edge_dir = start_point.vectorTo(end_point)
            edge_dir.normalize()

            # Check if parallel (angle close to 0 or 180 degrees)
            angle = edge_dir.angleTo(target_dir)
            tolerance = criteria.get('angle_tolerance', 0.017)  # ~1 degree in radians

            if not (angle < tolerance or abs(angle - math.pi) < tolerance):
                return False

    # Perpendicular to direction criteria
    if 'perpendicular_to' in criteria:
        perp = criteria['perpendicular_to']
        target_dir = adsk.core.Vector3D.create(perp['x'], perp['y'], perp['z'])
        target_dir.normalize()

        # Skip closed curves
        if start_point.distanceTo(end_point) > 0.001:
            edge_dir = start_point.vectorTo(end_point)
            edge_dir.normalize()

            # Check if perpendicular (angle close to 90 degrees)
            angle = edge_dir.angleTo(target_dir)
            tolerance = criteria.get('angle_tolerance', 0.017)  # ~1 degree

            if abs(angle - math.pi/2) > tolerance:
                return False

    return True

def _handle_find_edges_by_criteria(params):
    """Find edges matching search criteria"""
    body, _ = _resolve_element_path(params['body_path'])
    criteria = params.get('criteria', {})

    matching_edges = []

    for i in range(body.edges.count):
        edge = body.edges.item(i)
        if _edge_matches_criteria(edge, criteria):
            edge_info = _get_edge_info(edge, i)
            edge_info['path'] = f"{params['body_path']}/edges/{i}"
            matching_edges.append(edge_info)

    return {
        'status': 'success',
        'data': {
            'body': body.name,
            'match_count': len(matching_edges),
            'edges': matching_edges
        }
    }

def _face_matches_criteria(face, criteria):
    """Check if face matches all search criteria"""
    import math

    # Area criteria
    if 'area_min' in criteria:
        if face.area < criteria['area_min']:
            return False

    if 'area_max' in criteria:
        if face.area > criteria['area_max']:
            return False

    if 'area_equals' in criteria:
        tolerance = criteria.get('area_tolerance', 0.001)
        if abs(face.area - criteria['area_equals']) > tolerance:
            return False

    # Surface type criteria
    if 'surface_type' in criteria:
        geom = face.geometry
        surface_type_map = {
            'planar': adsk.core.SurfaceTypes.PlaneSurfaceType,
            'cylindrical': adsk.core.SurfaceTypes.CylinderSurfaceType,
            'conical': adsk.core.SurfaceTypes.ConeSurfaceType,
            'spherical': adsk.core.SurfaceTypes.SphereSurfaceType,
            'toroidal': adsk.core.SurfaceTypes.TorusSurfaceType
        }
        if geom.surfaceType != surface_type_map.get(criteria['surface_type']):
            return False

    # Normal direction criteria (for planar faces)
    if 'normal_direction' in criteria:
        geom = face.geometry

        # Only apply to planar faces
        if geom.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
            norm_crit = criteria['normal_direction']
            target_normal = adsk.core.Vector3D.create(norm_crit['x'], norm_crit['y'], norm_crit['z'])
            target_normal.normalize()

            face_normal = geom.normal

            # Check if normals are aligned
            angle = face_normal.angleTo(target_normal)
            tolerance = criteria.get('angle_tolerance', 0.017)  # ~1 degree

            if not (angle < tolerance or abs(angle - math.pi) < tolerance):
                return False

    # Proximity to point criteria
    if 'near_point' in criteria:
        near = criteria['near_point']
        point = adsk.core.Point3D.create(near['x'], near['y'], near['z'])
        radius = near.get('radius', 1.0)

        # Check if face centroid is within radius
        try:
            centroid = face.centroid
            if centroid.distanceTo(point) > radius:
                return False
        except:
            # Face may not have valid centroid
            return False

    return True

def _handle_create_plane(params):
    """Create construction plane"""
    import math

    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent
    mode = params.get('mode', 'offset')
    name = params.get('name', 'ConstructionPlane')

    planes = root.constructionPlanes

    try:
        if mode == 'offset':
            # Offset from existing plane
            ref_plane_path = params.get('reference_plane')
            offset = params.get('offset', 0.0)

            # Resolve reference plane - handle built-in planes specially
            # Check if it's a reference to XY/XZ/YZ built-in planes
            if 'XY Plane' in ref_plane_path or ref_plane_path.endswith('/XY') or ref_plane_path == 'XY':
                ref_plane = root.xYConstructionPlane
            elif 'XZ Plane' in ref_plane_path or ref_plane_path.endswith('/XZ') or ref_plane_path == 'XZ':
                ref_plane = root.xZConstructionPlane
            elif 'YZ Plane' in ref_plane_path or ref_plane_path.endswith('/YZ') or ref_plane_path == 'YZ':
                ref_plane = root.yZConstructionPlane
            elif ref_plane_path.startswith('root/constructionPlanes/'):
                # FIX v5.3.1: Handle custom construction planes by direct collection search
                # _resolve_element_path doesn't work correctly for construction planes
                plane_name = ref_plane_path.split('/')[-1]
                ref_plane = None
                for p in root.constructionPlanes:
                    if p.name == plane_name:
                        ref_plane = p
                        break
                if ref_plane is None:
                    raise ValueError(f'Construction plane "{plane_name}" not found. Available: {[p.name for p in root.constructionPlanes]}')
            else:
                # Other path types - try standard resolution
                ref_plane, _ = _resolve_element_path(ref_plane_path)

            # Create plane input
            plane_input = planes.createInput()
            offset_value = adsk.core.ValueInput.createByReal(offset)
            plane_input.setByOffset(ref_plane, offset_value)

            # Add plane
            plane = planes.add(plane_input)
            plane.name = name

            return {
                'status': 'success',
                'data': {
                    'plane_path': f"root/constructionPlanes/{plane.name}",
                    'name': plane.name,
                    'mode': 'offset',
                    'offset': offset
                }
            }

        elif mode == 'three_points':
            # Plane through three points
            # Note: ConstructionPoints require specific environment. Use sketch points instead.
            p1_data = params['point1']
            p2_data = params['point2']
            p3_data = params['point3']

            # Create temporary sketch for points
            temp_sketch = root.sketches.add(root.xYConstructionPlane)
            temp_sketch.name = f"_temp_sketch_for_{name}"

            # Add sketch points
            pt1_obj = temp_sketch.sketchPoints.add(adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data['z']))
            pt2_obj = temp_sketch.sketchPoints.add(adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data['z']))
            pt3_obj = temp_sketch.sketchPoints.add(adsk.core.Point3D.create(p3_data['x'], p3_data['y'], p3_data['z']))

            # Create plane using sketch points
            plane_input = planes.createInput()
            plane_input.setByThreePoints(pt1_obj, pt2_obj, pt3_obj)
            plane = planes.add(plane_input)
            plane.name = name

            # Calculate normal vector for return data
            p1 = adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data['z'])
            p2 = adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data['z'])
            p3 = adsk.core.Point3D.create(p3_data['x'], p3_data['y'], p3_data['z'])
            v1 = p1.vectorTo(p2)
            v2 = p1.vectorTo(p3)
            normal = v1.crossProduct(v2)
            normal.normalize()

            return {
                'status': 'success',
                'data': {
                    'plane_path': f"root/constructionPlanes/{plane.name}",
                    'name': plane.name,
                    'mode': 'three_points',
                    'origin': p1_data,
                    'normal': {'x': normal.x, 'y': normal.y, 'z': normal.z}
                }
            }

        elif mode == 'angle':
            # Plane at angle from reference plane around axis
            ref_plane_path = params.get('reference_plane')
            angle_deg = params.get('angle', 0.0)

            # Resolve reference plane - handle built-in planes specially
            if 'XY Plane' in ref_plane_path or ref_plane_path.endswith('/XY') or ref_plane_path == 'XY':
                ref_plane = root.xYConstructionPlane
            elif 'XZ Plane' in ref_plane_path or ref_plane_path.endswith('/XZ') or ref_plane_path == 'XZ':
                ref_plane = root.xZConstructionPlane
            elif 'YZ Plane' in ref_plane_path or ref_plane_path.endswith('/YZ') or ref_plane_path == 'YZ':
                ref_plane = root.yZConstructionPlane
            else:
                # Custom construction plane
                ref_plane, _ = _resolve_element_path(ref_plane_path)

            # Get axis (either path to construction axis or X/Y/Z)
            axis_spec = params.get('axis', 'X')

            if isinstance(axis_spec, str):
                # Named axis (X, Y, Z)
                if axis_spec.upper() == 'X':
                    axis = root.xConstructionAxis
                elif axis_spec.upper() == 'Y':
                    axis = root.yConstructionAxis
                elif axis_spec.upper() == 'Z':
                    axis = root.zConstructionAxis
                else:
                    # Path to construction axis
                    axis, _ = _resolve_element_path(axis_spec)
            else:
                # Should be a path
                axis, _ = _resolve_element_path(axis_spec)

            plane_input = planes.createInput()
            angle_value = adsk.core.ValueInput.createByReal(math.radians(angle_deg))
            # Correct parameter order: setByAngle(linearEntity, angle, planarEntity)
            plane_input.setByAngle(axis, angle_value, ref_plane)
            plane = planes.add(plane_input)
            plane.name = name

            return {
                'status': 'success',
                'data': {
                    'plane_path': f"root/constructionPlanes/{plane.name}",
                    'name': plane.name,
                    'mode': 'angle',
                    'angle': angle_deg
                }
            }

        elif mode == 'perpendicular':
            # Plane perpendicular to edge at point
            # Note: Fusion API doesn't have a direct "perpendicular to edge at point" method
            # Use setByDistanceOnPath which creates a plane perpendicular to the edge
            edge_path = params['edge']
            point_data = params.get('point', {})

            # Resolve edge
            edge, _ = _resolve_geometry_path(edge_path)

            # setByDistanceOnPath creates a plane perpendicular to edge's path
            # The distance parameter controls position along the edge
            # For now, create at edge start (distance=0)
            plane_input = planes.createInput()
            plane_input.setByDistanceOnPath(edge, adsk.core.ValueInput.createByReal(0))
            plane = planes.add(plane_input)
            plane.name = name

            return {
                'status': 'success',
                'data': {
                    'plane_path': f"root/constructionPlanes/{plane.name}",
                    'name': plane.name,
                    'mode': 'perpendicular',
                    'note': 'Plane created perpendicular to edge at start point (distance=0)'
                }
            }

        else:
            return {'status': 'error', 'message': f'Unknown mode: {mode}'}

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to create plane: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_create_axis(params):
    """Create construction axis"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent
    mode = params.get('mode', 'two_points')
    name = params.get('name', 'ConstructionAxis')

    axes = root.constructionAxes

    try:
        if mode == 'two_points':
            # Axis through two points
            # Note: ConstructionPoints require specific environment. Use sketch line approach.
            p1_data = params['point1']
            p2_data = params['point2']

            # Create temporary sketch with line
            temp_sketch = root.sketches.add(root.xYConstructionPlane)
            temp_sketch.name = f"_temp_sketch_for_{name}"

            pt1 = adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data['z'])
            pt2 = adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data['z'])

            # Create sketch line
            line = temp_sketch.sketchCurves.sketchLines.addByTwoPoints(pt1, pt2)

            # Create axis from the line's geometry (converts to infinite line)
            axis_input = axes.createInput()
            line_geom = line.geometry
            infinite_line = line_geom.asInfiniteLine()
            axis_input.setByLine(infinite_line)
            axis = axes.add(axis_input)
            axis.name = name

            # Calculate direction vector for return data
            direction = pt1.vectorTo(pt2)
            direction.normalize()

            return {
                'status': 'success',
                'data': {
                    'axis_path': f"root/constructionAxes/{axis.name}",
                    'name': axis.name,
                    'mode': 'two_points',
                    'origin': p1_data,
                    'direction': {'x': direction.x, 'y': direction.y, 'z': direction.z}
                }
            }

        elif mode == 'edge':
            # Axis along edge
            edge_path = params['edge']
            edge, _ = _resolve_geometry_path(edge_path)

            axis_input = axes.createInput()
            axis_input.setByEdge(edge)  # Fixed: was setByLine, should be setByEdge
            axis = axes.add(axis_input)
            axis.name = name

            return {
                'status': 'success',
                'data': {
                    'axis_path': f"root/constructionAxes/{axis.name}",
                    'name': axis.name,
                    'mode': 'edge'
                }
            }

        elif mode == 'perpendicular':
            # Axis perpendicular to face at point
            face_path = params['face']
            point_data = params['point']

            face, _ = _resolve_geometry_path(face_path)
            point = adsk.core.Point3D.create(point_data['x'], point_data['y'], point_data['z'])

            axis_input = axes.createInput()
            axis_input.setByNormalToFaceAtPoint(face, point)
            axis = axes.add(axis_input)
            axis.name = name

            return {
                'status': 'success',
                'data': {
                    'axis_path': f"root/constructionAxes/{axis.name}",
                    'name': axis.name,
                    'mode': 'perpendicular',
                    'point': point_data
                }
            }

        else:
            return {'status': 'error', 'message': f'Unknown mode: {mode}'}

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to create axis: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_move_body(params):
    """Move a body by a vector using MoveFeature"""
    import math

    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get body to move
        body, _ = _resolve_element_path(params['body_path'])

        # Get translation vector
        vector_data = params['vector']
        vector = adsk.core.Vector3D.create(
            vector_data['x'],
            vector_data['y'],
            vector_data['z']
        )

        # Create transform matrix for translation
        transform = adsk.core.Matrix3D.create()
        transform.translation = vector

        # Create move feature
        move_features = root.features.moveFeatures
        bodies_collection = adsk.core.ObjectCollection.create()
        bodies_collection.add(body)

        move_input = move_features.createInput(bodies_collection, transform)
        move_feature = move_features.add(move_input)

        return {
            'status': 'success',
            'data': {
                'body_path': params['body_path'],
                'translation': {
                    'x': vector.x,
                    'y': vector.y,
                    'z': vector.z
                },
                'feature_name': move_feature.name
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to move body: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_rotate_body(params):
    """Rotate a body around an axis by an angle"""
    import math

    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get body to rotate
        body, _ = _resolve_element_path(params['body_path'])

        # Get rotation axis
        axis_data = params['axis']
        origin_data = axis_data['origin']
        direction_data = axis_data['direction']

        origin = adsk.core.Point3D.create(
            origin_data['x'],
            origin_data['y'],
            origin_data['z']
        )

        direction = adsk.core.Vector3D.create(
            direction_data['x'],
            direction_data['y'],
            direction_data['z']
        )
        direction.normalize()

        # Get angle (convert degrees to radians)
        angle_deg = params['angle']
        angle_rad = math.radians(angle_deg)

        # Create rotation axis
        axis_line = adsk.core.InfiniteLine3D.create(origin, direction)

        # Create transform matrix for rotation
        transform = adsk.core.Matrix3D.create()
        transform.setToRotation(angle_rad, direction, origin)

        # Create move feature (move features handle both translation and rotation)
        move_features = root.features.moveFeatures
        bodies_collection = adsk.core.ObjectCollection.create()
        bodies_collection.add(body)

        move_input = move_features.createInput(bodies_collection, transform)
        move_feature = move_features.add(move_input)

        return {
            'status': 'success',
            'data': {
                'body_path': params['body_path'],
                'angle': angle_deg,
                'axis': {
                    'origin': origin_data,
                    'direction': direction_data
                },
                'feature_name': move_feature.name
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to rotate body: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_mirror_body(params):
    """Mirror a body across a plane"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get body to mirror
        body, _ = _resolve_element_path(params['body_path'])

        # Get mirror plane
        mirror_plane, _ = _resolve_element_path(params['mirror_plane'])

        # Create mirror feature
        mirror_features = root.features.mirrorFeatures

        # Create object collection for bodies to mirror
        input_entities = adsk.core.ObjectCollection.create()
        input_entities.add(body)

        # Create mirror input
        mirror_input = mirror_features.createInput(input_entities, mirror_plane)

        # Execute mirror
        mirror_feature = mirror_features.add(mirror_input)

        # Get the created mirrored body
        mirrored_bodies = []
        for new_body in mirror_feature.bodies:
            mirrored_bodies.append({
                'name': new_body.name,
                'volume': new_body.volume,
                'area': new_body.area
            })

        return {
            'status': 'success',
            'data': {
                'original_body': params['body_path'],
                'mirror_plane': params['mirror_plane'],
                'feature_name': mirror_feature.name,
                'mirrored_bodies': mirrored_bodies
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to mirror body: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_find_faces_by_criteria(params):
    """Find faces matching search criteria"""
    body, _ = _resolve_element_path(params['body_path'])
    criteria = params.get('criteria', {})

    matching_faces = []

    for i in range(body.faces.count):
        face = body.faces.item(i)
        if _face_matches_criteria(face, criteria):
            face_info = _get_face_info(face, i)
            face_info['path'] = f"{params['body_path']}/faces/{i}"
            matching_faces.append(face_info)

    return {
        'status': 'success',
        'data': {
            'body': body.name,
            'match_count': len(matching_faces),
            'faces': matching_faces
        }
    }

def _handle_set_element_properties(params):
    """Set properties (visibility, grounding) for design elements"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    # Get parameters
    element_path = params.get('path', '')
    is_visible = params.get('isVisible', None)
    is_grounded = params.get('isGrounded', None)

    if not element_path:
        return {'status': 'error', 'message': 'No element path provided'}

    # Parse path (e.g., "root/occurrences/OccName/bodies/BodyName")
    parts = element_path.split('/')

    if len(parts) == 0 or parts[0] != 'root':
        return {'status': 'error', 'message': 'Path must start with "root"'}

    try:
        current = root
        element = None
        i = 1

        while i < len(parts):
            part = parts[i]

            # Accept both 'bodies' and 'bRepBodies'
            if part in ['bodies', 'bRepBodies']:
                # Next part is body name
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Body name missing after "bodies"'}
                body_name = parts[i + 1]
                available_bodies = [body.name for body in current.bRepBodies]
                for body in current.bRepBodies:
                    if body.name == body_name:
                        element = body
                        break
                if not element:
                    return {'status': 'error', 'message': f'Body "{body_name}" not found. Available: {available_bodies}'}
                break

            elif part == 'sketches':
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Sketch name missing after "sketches"'}
                sketch_name = parts[i + 1]
                for sketch in current.sketches:
                    if sketch.name == sketch_name:
                        element = sketch
                        break
                if not element:
                    return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}
                break

            elif part == 'meshBodies':
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Mesh body name missing'}
                mesh_name = parts[i + 1]
                for mesh in current.meshBodies:
                    if mesh.name == mesh_name:
                        element = mesh
                        break
                if not element:
                    return {'status': 'error', 'message': f'Mesh body "{mesh_name}" not found'}
                break

            # Accept both 'occurrences' and 'children'
            elif part in ['occurrences', 'children']:
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Occurrence name missing'}
                occ_name = parts[i + 1]
                available_occs = [occ.name for occ in current.occurrences]
                found_occ = None
                for occ in current.occurrences:
                    if occ.name == occ_name:
                        found_occ = occ
                        break
                if not found_occ:
                    return {'status': 'error', 'message': f'Occurrence "{occ_name}" not found. Available: {available_occs}'}

                # If this is the last element, we're targeting the occurrence itself
                if i + 2 >= len(parts):
                    element = found_occ
                    break

                # Otherwise, continue navigating into the occurrence's component
                current = found_occ.component
                i += 2
                # Don't increment i again at the end of the while loop
                continue

            elif part == 'constructionPlanes':
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Construction plane name missing'}
                plane_name = parts[i + 1]
                for plane in current.constructionPlanes:
                    if plane.name == plane_name:
                        element = plane
                        break
                if not element:
                    return {'status': 'error', 'message': f'Construction plane "{plane_name}" not found'}
                break

            elif part == 'constructionAxes':
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Construction axis name missing'}
                axis_name = parts[i + 1]
                for axis in current.constructionAxes:
                    if axis.name == axis_name:
                        element = axis
                        break
                if not element:
                    return {'status': 'error', 'message': f'Construction axis "{axis_name}" not found'}
                break

            elif part == 'constructionPoints':
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Construction point name missing'}
                point_name = parts[i + 1]
                for point in current.constructionPoints:
                    if point.name == point_name:
                        element = point
                        break
                if not element:
                    return {'status': 'error', 'message': f'Construction point "{point_name}" not found'}
                break

            else:
                return {'status': 'error', 'message': f'Unknown path segment: "{part}"'}

            i += 1

        # If element is still None, we're targeting root component
        if element is None:
            element = root

        # Apply properties
        updated = []

        if is_visible is not None:
            # For occurrences, use isLightBulbOn instead of isVisible (which is read-only)
            if element.__class__.__name__ == 'Occurrence':
                element.isLightBulbOn = is_visible
                updated.append(f'visibility (lightbulb) set to {is_visible}')
            elif hasattr(element, 'isVisible'):
                element.isVisible = is_visible
                updated.append(f'visibility set to {is_visible}')
            else:
                return {'status': 'error', 'message': 'Element does not support visibility control'}

        if is_grounded is not None:
            if hasattr(element, 'isGrounded'):
                element.isGrounded = is_grounded
                updated.append(f'grounded set to {is_grounded}')
            else:
                return {'status': 'error', 'message': 'Element does not support grounding (only occurrences can be grounded)'}

        if not updated:
            return {'status': 'error', 'message': 'No properties specified to update'}

        return {
            'status': 'success',
            'message': f'Updated: {", ".join(updated)}',
            'path': element_path
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to update element: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_get_tree(params):
    """Get complete component/body tree with ALL elements"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    def safe_get(obj, attr, default=None):
        """Safely get attribute with fallback"""
        try:
            return getattr(obj, attr)
        except:
            return default

    def get_component_data(comp):
        """Extract all data from a component"""
        data = {
            'name': comp.name,
            'bRepBodies': [],
            'meshBodies': [],
            'sketches': [],
            'constructionPlanes': [],
            'constructionAxes': [],
            'constructionPoints': [],
            'features': []
        }

        # BRep Bodies
        for body in comp.bRepBodies:
            try:
                volume = body.volume
            except:
                volume = None
            try:
                area = body.area
            except:
                area = None

            data['bRepBodies'].append({
                'name': body.name,
                'isVisible': body.isVisible,
                'isSolid': body.isSolid,
                'volume': volume,
                'area': area
            })

        # Mesh Bodies
        for mesh in comp.meshBodies:
            data['meshBodies'].append({
                'name': mesh.name,
                'isVisible': mesh.isVisible,
                'triangleCount': safe_get(mesh, 'triangleCount', 0)
            })

        # Sketches
        for sketch in comp.sketches:
            data['sketches'].append({
                'name': sketch.name,
                'isVisible': sketch.isVisible,
                'isComputeDeferred': sketch.isComputeDeferred,
                'profileCount': sketch.profiles.count,
                'curveCount': sketch.sketchCurves.count
            })

        # Construction Planes
        for plane in comp.constructionPlanes:
            data['constructionPlanes'].append({
                'name': plane.name,
                'isVisible': plane.isVisible
            })

        # Construction Axes
        for axis in comp.constructionAxes:
            data['constructionAxes'].append({
                'name': axis.name,
                'isVisible': axis.isVisible
            })

        # Construction Points
        for point in comp.constructionPoints:
            data['constructionPoints'].append({
                'name': point.name,
                'isVisible': point.isVisible
            })

        # Features
        features = comp.features
        for feature_list in [features.extrudeFeatures, features.revolveFeatures,
                            features.loftFeatures, features.sweepFeatures,
                            features.filletFeatures, features.chamferFeatures,
                            features.holeFeatures, features.threadFeatures,
                            features.mirrorFeatures, features.circularPatternFeatures,
                            features.rectangularPatternFeatures]:
            for feature in feature_list:
                data['features'].append({
                    'name': safe_get(feature, 'name', 'Unnamed'),
                    'type': feature.classType().split('::')[-1],
                    'isSuppressed': safe_get(feature, 'isSuppressed', False)
                })

        return data

    def traverse_occurrence(occ):
        """Recursively traverse occurrence tree"""
        comp = occ.component
        comp_data = get_component_data(comp)

        node = {
            'name': occ.name,
            'type': 'occurrence',
            'isVisible': occ.isVisible,
            'isLightBulbOn': occ.isLightBulbOn,
            'component': comp_data
        }

        # Recurse into children
        if occ.childOccurrences.count > 0:
            node['children'] = []
            for child in occ.childOccurrences:
                node['children'].append(traverse_occurrence(child))

        return node

    # Build root tree
    tree = {
        'name': root.name,
        'type': 'root_component',
        'designType': 'Parametric' if safe_get(design, 'designType', None) == 0 else 'Direct/Mesh',
        'component': get_component_data(root),
        'joints': [],
        'asBuiltJoints': [],
        'parameters': []
    }

    # Joints
    for joint in root.joints:
        tree['joints'].append({
            'name': safe_get(joint, 'name', 'Unnamed'),
            'isSuppressed': safe_get(joint, 'isSuppressed', False),
            'jointMotion': safe_get(joint.jointMotion, 'jointType', None)
        })

    # AsBuilt Joints
    for joint in root.asBuiltJoints:
        tree['asBuiltJoints'].append({
            'name': safe_get(joint, 'name', 'Unnamed')
        })

    # User Parameters (only for parametric designs)
    try:
        for param in design.userParameters:
            tree['parameters'].append({
                'name': param.name,
                'expression': param.expression,
                'value': safe_get(param, 'value', None),
                'unit': safe_get(param, 'unit', None),
                'comment': safe_get(param, 'comment', '')
            })
    except:
        # Non-parametric design (mesh/direct modeling) - no user parameters
        pass

    # Child occurrences
    if root.occurrences.count > 0:
        tree['children'] = []
        for occ in root.occurrences:
            tree['children'].append(traverse_occurrence(occ))

    return {
        'status': 'success',
        'data': tree
    }

class MainThreadExecutor(adsk.core.CustomEventHandler):
    """Executes operations on Fusion's main thread"""
    def notify(self, args):
        try:
            event_args = json.loads(args.additionalInfo)
            operation_id = event_args['id']
            operation = event_args.get('operation', 'exec')

            result = None

            # Route to appropriate handler
            if operation == 'exec':
                # Existing script execution
                script_code = event_args['script']
                app = adsk.core.Application.get()
                ui = app.userInterface
                design = app.activeProduct
                root = design.rootComponent if design else None

                context = {
                    'app': app,
                    'ui': ui,
                    'design': design,
                    'root': root,
                    'adsk': adsk,
                    'result': None
                }
                exec(script_code, context)
                result = context.get('result', {'status': 'ok'})

            elif operation == 'screenshot':
                result = _handle_screenshot(event_args.get('params', {}))
            elif operation == 'get_camera':
                result = _handle_get_camera(event_args.get('params', {}))
            elif operation == 'set_camera':
                result = _handle_set_camera(event_args.get('params', {}))
            elif operation == 'get_tree':
                result = _handle_get_tree(event_args.get('params', {}))
            elif operation == 'set_element_properties':
                result = _handle_set_element_properties(event_args.get('params', {}))
            elif operation == 'measure_distance':
                result = _handle_measure_distance(event_args.get('params', {}))
            elif operation == 'measure_angle':
                result = _handle_measure_angle(event_args.get('params', {}))
            elif operation == 'get_edge_info':
                result = _handle_get_edge_info(event_args.get('params', {}))
            elif operation == 'get_face_info':
                result = _handle_get_face_info(event_args.get('params', {}))
            elif operation == 'find_edges_by_criteria':
                result = _handle_find_edges_by_criteria(event_args.get('params', {}))
            elif operation == 'find_faces_by_criteria':
                result = _handle_find_faces_by_criteria(event_args.get('params', {}))
            elif operation == 'create_plane':
                result = _handle_create_plane(event_args.get('params', {}))
            elif operation == 'create_axis':
                result = _handle_create_axis(event_args.get('params', {}))
            elif operation == 'move_body':
                result = _handle_move_body(event_args.get('params', {}))
            elif operation == 'rotate_body':
                result = _handle_rotate_body(event_args.get('params', {}))
            elif operation == 'mirror_body':
                result = _handle_mirror_body(event_args.get('params', {}))
            else:
                result = {'status': 'error', 'error': f'Unknown operation: {operation}'}

            _results_queue[operation_id] = {
                'status': 'success',
                'result': result
            }

        except Exception as e:
            _results_queue[operation_id] = {
                'status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc()
            }

class AsyncScriptHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)

            operation = data.get('operation', 'exec')
            params = data.get('params', {})
            script_code = data.get('script', '')
            operation_id = data.get('id', str(time.time()))
            timeout = data.get('timeout', 30)

            # Fire custom event to execute on main thread
            app = adsk.core.Application.get()
            event_args = {
                'id': operation_id,
                'operation': operation,
                'params': params,
                'script': script_code
            }
            app.fireCustomEvent('FusionScriptExecutor', json.dumps(event_args))
            
            # Wait for result (with timeout)
            start_time = time.time()
            while operation_id not in _results_queue:
                time.sleep(0.1)
                if time.time() - start_time > timeout:
                    self.send_json_response({
                        'status': 'timeout',
                        'message': f'Operation timed out after {timeout}s'
                    }, 408)
                    return
            
            # Get result
            result = _results_queue.pop(operation_id)
            
            if result['status'] == 'error':
                self.send_json_response(result, 500)
            else:
                self.send_json_response(result['result'], 200)
            
        except Exception as e:
            self.send_json_response({
                'status': 'server_error',
                'error': str(e),
                'traceback': traceback.format_exc()
            }, 500)
    
    def send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass

def run(context):
    global _server, _server_thread, _custom_event, _custom_event_handler
    
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        # Register custom event for main thread execution
        _custom_event = app.registerCustomEvent('FusionScriptExecutor')
        _custom_event_handler = MainThreadExecutor()
        _custom_event.add(_custom_event_handler)
        
        # Start HTTP server
        _server = HTTPServer(('localhost', 8080), AsyncScriptHandler)
        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()
        
        ui.messageBox(
            'Fusion Script Executor v5.3.1\n\n'
            'FIXED v5.3.1: Custom construction planes now work as offset references\n'
            'NEW v5.3.0: Transform tools - move, rotate, mirror bodies\n'
            'FIXED v5.2.2: ConstructionPoint environment errors - using sketch geometry\n'
            'v5.2: Construction tools (planes, axes)\n'
            'v5.1: Geometry search (find edges/faces by criteria)\n'
            'v5.0: Measurement tools (distance, angle, edge/face inspection)\n\n'
            'All operations execute on Fusion\'s main thread!\n'
            'Endpoint: http://localhost:8080'
        )
        
    except Exception as e:
        if ui:
            ui.messageBox(f'Failed:\n{traceback.format_exc()}')

def stop(context):
    global _server, _custom_event, _custom_event_handler
    
    try:
        if _server:
            _server.shutdown()
        
        if _custom_event and _custom_event_handler:
            _custom_event.remove(_custom_event_handler)
            app = adsk.core.Application.get()
            app.unregisterCustomEvent('FusionScriptExecutor')
    except:
        pass