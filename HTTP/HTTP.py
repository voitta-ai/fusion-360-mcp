import adsk.core, adsk.fusion, traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import queue
import time
import base64
import tempfile
import os
import math 

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

def _find_body_path(body, root):
    """Helper to find the path to a body in the design tree"""
    # Check root bodies
    for i in range(root.bRepBodies.count):
        if root.bRepBodies.item(i) == body:
            return f"root/bRepBodies/{body.name}"

    # Check occurrence bodies
    for occ in root.allOccurrences:
        for i in range(occ.bRepBodies.count):
            if occ.bRepBodies.item(i) == body:
                return f"root/occurrences/{occ.name}/bRepBodies/{body.name}"

    return f"root/bRepBodies/{body.name}"  # Fallback

def _handle_split_body(params):
    """Split a body using a plane or face as the splitting tool"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get body to split
        body, _ = _resolve_element_path(params['body_path'])

        # Get split tool (can be plane or face)
        split_tool_path = params['split_tool']
        split_tool = None

        # Check for built-in plane shortcuts FIRST
        if split_tool_path == 'XY':
            split_tool = root.xYConstructionPlane
        elif split_tool_path == 'XZ':
            split_tool = root.xZConstructionPlane
        elif split_tool_path == 'YZ':
            split_tool = root.yZConstructionPlane
        # Check for custom construction planes
        elif split_tool_path.startswith('root/constructionPlanes/'):
            plane_name = split_tool_path.split('/')[-1]
            for p in root.constructionPlanes:
                if p.name == plane_name:
                    split_tool = p
                    break
            if split_tool is None:
                raise ValueError(f'Construction plane "{plane_name}" not found')
        # Check for face path (edges/faces geometry)
        elif '/faces/' in split_tool_path:
            split_tool, _ = _resolve_geometry_path(split_tool_path)
        else:
            # Try general element resolution as fallback
            split_tool, _ = _resolve_element_path(split_tool_path)

        if split_tool is None:
            return {
                'status': 'error',
                'message': f'Could not resolve split tool: {split_tool_path}'
            }

        # Create split body feature (always keeps both halves)
        split_features = root.features.splitBodyFeatures
        split_input = split_features.createInput(body, split_tool, True)
        split_feature = split_features.add(split_input)

        # Get resulting bodies
        resulting_bodies = []
        for result_body in split_feature.bodies:
            resulting_bodies.append({
                'name': result_body.name,
                'path': _find_body_path(result_body, root),
                'volume': result_body.volume,
                'area': result_body.area
            })

        return {
            'status': 'success',
            'data': {
                'original_body': params['body_path'],
                'split_tool': split_tool_path,
                'feature_name': split_feature.name,
                'resulting_bodies': resulting_bodies
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to split body: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_boolean_operation(params):
    """Perform boolean operation (join, cut, intersect) on bodies"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get target body (the body being operated on)
        target_body, _ = _resolve_element_path(params['target_body'])

        # Get tool body (the body used for the operation)
        tool_body, _ = _resolve_element_path(params['tool_body'])

        # Get operation type
        operation = params['operation'].lower()
        operation_map = {
            'join': adsk.fusion.FeatureOperations.JoinFeatureOperation,
            'cut': adsk.fusion.FeatureOperations.CutFeatureOperation,
            'intersect': adsk.fusion.FeatureOperations.IntersectFeatureOperation
        }

        if operation not in operation_map:
            return {
                'status': 'error',
                'message': f'Invalid operation: {operation}. Must be one of: join, cut, intersect'
            }

        feature_operation = operation_map[operation]

        # Get keep_tool parameter (default False - tool body is consumed)
        keep_tool = params.get('keep_tool', False)

        # Create combine feature
        combine_features = root.features.combineFeatures

        # Create object collection for tool bodies
        tool_bodies = adsk.core.ObjectCollection.create()
        tool_bodies.add(tool_body)

        # Create combine input
        combine_input = combine_features.createInput(target_body, tool_bodies)
        combine_input.operation = feature_operation
        combine_input.isKeepToolBodies = keep_tool

        # Execute combine
        combine_feature = combine_features.add(combine_input)

        # Get resulting body (for join/intersect, it's the modified target; for cut, target is modified)
        result_body = target_body  # The target body is modified in place

        return {
            'status': 'success',
            'data': {
                'target_body': params['target_body'],
                'tool_body': params['tool_body'],
                'operation': operation,
                'keep_tool': keep_tool,
                'feature_name': combine_feature.name,
                'result_body': {
                    'name': result_body.name,
                    'path': _find_body_path(result_body, root),
                    'volume': result_body.volume,
                    'area': result_body.area
                }
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to perform boolean operation: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_create_extrude(params):
    """Create an extrusion feature from a sketch profile"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        # Get profiles from sketch
        if sketch.profiles.count == 0:
            return {'status': 'error', 'message': f'No closed profiles found in sketch "{sketch_name}"'}

        # Get profile index (-1 means all profiles)
        profile_index = params.get('profile_index', 0)

        if profile_index == -1:
            # Use all profiles
            profiles = adsk.core.ObjectCollection.create()
            for i in range(sketch.profiles.count):
                profiles.add(sketch.profiles.item(i))
            profile = profiles
        else:
            if profile_index >= sketch.profiles.count:
                return {
                    'status': 'error',
                    'message': f'Profile index {profile_index} out of range. Sketch has {sketch.profiles.count} profile(s)'
                }
            profile = sketch.profiles.item(profile_index)

        # Get parameters
        extent_type = params.get('extent_type', 'distance')
        direction = params.get('direction', 'one_side')
        distance = params.get('distance', 1.0)  # in cm
        distance_two = params.get('distance_two', distance)
        taper_angle = params.get('taper_angle', 0)  # in degrees
        taper_angle_two = params.get('taper_angle_two', 0)
        operation = params.get('operation', 'new_body')

        # Map operation to FeatureOperations enum
        operation_map = {
            'new_body': adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            'join': adsk.fusion.FeatureOperations.JoinFeatureOperation,
            'cut': adsk.fusion.FeatureOperations.CutFeatureOperation,
            'intersect': adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            'new_component': adsk.fusion.FeatureOperations.NewComponentFeatureOperation
        }

        if operation not in operation_map:
            return {
                'status': 'error',
                'message': f'Invalid operation: {operation}. Must be one of: {list(operation_map.keys())}'
            }

        feature_operation = operation_map[operation]

        # Create extrude features collection
        extrude_features = root.features.extrudeFeatures

        # Create extrude input
        extrude_input = extrude_features.createInput(profile, feature_operation)

        # Convert taper angles to radians
        import math
        taper_rad = math.radians(taper_angle)
        taper_rad_two = math.radians(taper_angle_two)

        # Set extent based on type and direction
        if extent_type == 'distance':
            distance_value = adsk.core.ValueInput.createByReal(distance)
            taper_value = adsk.core.ValueInput.createByReal(taper_rad)
            taper_value_two = adsk.core.ValueInput.createByReal(taper_rad_two)

            if direction == 'symmetric':
                # Symmetric extrusion
                # setSymmetricExtent(distance, isFullLength) - no direct taper param
                extrude_input.setSymmetricExtent(distance_value, True)
                # Set taper after if needed (through extentOne)
                if taper_angle != 0 and extrude_input.extentOne:
                    extrude_input.extentOne.taperAngle = taper_value

            elif direction == 'two_sides':
                # Two-sided asymmetric extrusion
                distance_value_two = adsk.core.ValueInput.createByReal(distance_two)
                side_one = adsk.fusion.DistanceExtentDefinition.create(distance_value)
                side_two = adsk.fusion.DistanceExtentDefinition.create(distance_value_two)
                # setTwoSidesExtent(extentOne, extentTwo)
                extrude_input.setTwoSidesExtent(side_one, side_two)
                # Set taper angles after
                if taper_angle != 0 and extrude_input.extentOne:
                    extrude_input.extentOne.taperAngle = taper_value
                if taper_angle_two != 0 and extrude_input.extentTwo:
                    extrude_input.extentTwo.taperAngle = taper_value_two

            else:
                # One-sided extrusion (default)
                # Use setOneSideExtent for taper support: (extent, direction, taperAngle)
                dist_extent = adsk.fusion.DistanceExtentDefinition.create(distance_value)
                extrude_input.setOneSideExtent(dist_extent, adsk.fusion.ExtentDirections.PositiveExtentDirection, taper_value)

        elif extent_type == 'to_object':
            # Extrude to a face or plane
            to_entity_path = params.get('to_entity')
            if not to_entity_path:
                return {'status': 'error', 'message': 'to_entity path required for to_object extent type'}

            # Resolve the target entity - try geometry path first (for faces)
            to_entity = None
            try:
                to_entity, entity_type = _resolve_geometry_path(to_entity_path)
            except:
                pass

            if to_entity is None:
                # Try as construction plane or other element
                # Handle shortcut names for construction planes
                if to_entity_path in ['XY', 'XZ', 'YZ']:
                    if to_entity_path == 'XY':
                        to_entity = root.xYConstructionPlane
                    elif to_entity_path == 'XZ':
                        to_entity = root.xZConstructionPlane
                    elif to_entity_path == 'YZ':
                        to_entity = root.yZConstructionPlane
                elif 'constructionPlanes' in to_entity_path:
                    # Get construction plane by name
                    plane_name = to_entity_path.split('/')[-1]
                    for plane in root.constructionPlanes:
                        if plane.name == plane_name:
                            to_entity = plane
                            break
                else:
                    to_entity, entity_type = _resolve_element_path(to_entity_path)

            if to_entity is None:
                return {'status': 'error', 'message': f'Could not resolve to_entity: {to_entity_path}'}

            to_extent = adsk.fusion.ToEntityExtentDefinition.create(to_entity, False)
            extrude_input.setOneSideExtent(to_extent, adsk.fusion.ExtentDirections.PositiveExtentDirection)

        elif extent_type == 'through_all':
            # Through all in one direction (requires existing bodies to go through)
            extrude_input.setAllExtent(adsk.fusion.ExtentDirections.PositiveExtentDirection)

        elif extent_type == 'all':
            # Through all in both directions - use two-sided with AllExtentDefinition
            # Note: This requires existing geometry to extrude through
            all_extent_one = adsk.fusion.AllExtentDefinition.create()
            all_extent_two = adsk.fusion.AllExtentDefinition.create()
            extrude_input.setTwoSidesExtent(all_extent_one, all_extent_two)

        # Set target body for join/cut/intersect operations
        if operation in ['join', 'cut', 'intersect']:
            target_body_path = params.get('target_body')
            if target_body_path:
                target_body, _ = _resolve_element_path(target_body_path)
                # participantBodies expects a Python list of BRepBody, not ObjectCollection
                extrude_input.participantBodies = [target_body]

        # Create the extrude feature
        extrude_feature = extrude_features.add(extrude_input)

        # Collect created bodies
        bodies_created = []
        for i in range(extrude_feature.bodies.count):
            body = extrude_feature.bodies.item(i)
            bodies_created.append({
                'name': body.name,
                'path': _find_body_path(body, root),
                'volume': body.volume,
                'area': body.area
            })

        return {
            'status': 'success',
            'data': {
                'feature_name': extrude_feature.name,
                'sketch': sketch_name,
                'profile_count': sketch.profiles.count if profile_index == -1 else 1,
                'extent_type': extent_type,
                'direction': direction,
                'distance': distance,
                'distance_two': distance_two if direction == 'two_sides' else None,
                'taper_angle': taper_angle,
                'taper_angle_two': taper_angle_two if direction == 'two_sides' else None,
                'operation': operation,
                'bodies_created': bodies_created
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to create extrude: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_create_sketch(params):
    """Create a new sketch on a plane"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get the plane to sketch on
        plane_path = params['plane']
        name = params.get('name', 'Sketch')

        # Resolve plane - support XY/XZ/YZ shortcuts
        if plane_path == 'XY':
            plane = root.xYConstructionPlane
        elif plane_path == 'XZ':
            plane = root.xZConstructionPlane
        elif plane_path == 'YZ':
            plane = root.yZConstructionPlane
        elif plane_path.startswith('root/constructionPlanes/'):
            plane_name = plane_path.split('/')[-1]
            plane = None
            for p in root.constructionPlanes:
                if p.name == plane_name:
                    plane = p
                    break
            if plane is None:
                raise ValueError(f'Construction plane "{plane_name}" not found')
        else:
            plane, _ = _resolve_element_path(plane_path)

        # Create sketch
        sketch = root.sketches.add(plane)
        sketch.name = name

        return {
            'status': 'success',
            'data': {
                'sketch_path': f'root/sketches/{sketch.name}',
                'name': sketch.name,
                'plane': plane_path
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to create sketch: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_sketch_add_line(params):
    """Add a line to a sketch"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        # Get points
        p1_data = params['point1']
        p2_data = params['point2']

        # Create points in sketch coordinates
        p1 = adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data.get('z', 0))
        p2 = adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data.get('z', 0))

        # Add line
        line = sketch.sketchCurves.sketchLines.addByTwoPoints(p1, p2)

        return {
            'status': 'success',
            'data': {
                'sketch': sketch_name,
                'element_type': 'line',
                'start_point': {'x': line.startSketchPoint.geometry.x, 'y': line.startSketchPoint.geometry.y},
                'end_point': {'x': line.endSketchPoint.geometry.x, 'y': line.endSketchPoint.geometry.y},
                'length': line.length
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to add line: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_sketch_add_circle(params):
    """Add a circle to a sketch"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        mode = params.get('mode', 'center_radius')

        if mode == 'center_radius':
            # Circle by center point and radius
            center_data = params['center']
            radius = params['radius']

            center = adsk.core.Point3D.create(center_data['x'], center_data['y'], center_data.get('z', 0))

            circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(center, radius)

            return {
                'status': 'success',
                'data': {
                    'sketch': sketch_name,
                    'element_type': 'circle',
                    'center': {'x': circle.centerSketchPoint.geometry.x, 'y': circle.centerSketchPoint.geometry.y},
                    'radius': circle.radius
                }
            }

        elif mode == 'three_points':
            # Circle through three points
            p1_data = params['point1']
            p2_data = params['point2']
            p3_data = params['point3']

            p1 = adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data.get('z', 0))
            p2 = adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data.get('z', 0))
            p3 = adsk.core.Point3D.create(p3_data['x'], p3_data['y'], p3_data.get('z', 0))

            circle = sketch.sketchCurves.sketchCircles.addByThreePoints(p1, p2, p3)

            return {
                'status': 'success',
                'data': {
                    'sketch': sketch_name,
                    'element_type': 'circle',
                    'center': {'x': circle.centerSketchPoint.geometry.x, 'y': circle.centerSketchPoint.geometry.y},
                    'radius': circle.radius
                }
            }

        else:
            return {'status': 'error', 'message': f'Unknown circle mode: {mode}'}

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to add circle: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_sketch_add_arc(params):
    """Add an arc to a sketch"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        mode = params.get('mode', 'three_points')

        if mode == 'three_points':
            # Arc through three points
            p1_data = params['point1']
            p2_data = params['point2']
            p3_data = params['point3']

            p1 = adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data.get('z', 0))
            p2 = adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data.get('z', 0))
            p3 = adsk.core.Point3D.create(p3_data['x'], p3_data['y'], p3_data.get('z', 0))

            arc = sketch.sketchCurves.sketchArcs.addByThreePoints(p1, p2, p3)

            return {
                'status': 'success',
                'data': {
                    'sketch': sketch_name,
                    'element_type': 'arc',
                    'center': {'x': arc.centerSketchPoint.geometry.x, 'y': arc.centerSketchPoint.geometry.y},
                    'start_point': {'x': arc.startSketchPoint.geometry.x, 'y': arc.startSketchPoint.geometry.y},
                    'end_point': {'x': arc.endSketchPoint.geometry.x, 'y': arc.endSketchPoint.geometry.y},
                    'radius': arc.radius,
                    'length': arc.length
                }
            }

        elif mode == 'center_start_end':
            # Arc by center, start point, and sweep angle
            center_data = params['center']
            start_data = params['start']
            sweep_angle = params['sweep_angle']  # in degrees

            import math
            center = adsk.core.Point3D.create(center_data['x'], center_data['y'], center_data.get('z', 0))
            start = adsk.core.Point3D.create(start_data['x'], start_data['y'], start_data.get('z', 0))

            arc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(center, start, math.radians(sweep_angle))

            return {
                'status': 'success',
                'data': {
                    'sketch': sketch_name,
                    'element_type': 'arc',
                    'center': {'x': arc.centerSketchPoint.geometry.x, 'y': arc.centerSketchPoint.geometry.y},
                    'start_point': {'x': arc.startSketchPoint.geometry.x, 'y': arc.startSketchPoint.geometry.y},
                    'end_point': {'x': arc.endSketchPoint.geometry.x, 'y': arc.endSketchPoint.geometry.y},
                    'radius': arc.radius,
                    'length': arc.length,
                    'sweep_angle': sweep_angle
                }
            }

        else:
            return {'status': 'error', 'message': f'Unknown arc mode: {mode}'}

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to add arc: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_sketch_add_rectangle(params):
    """Add a rectangle to a sketch"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        mode = params.get('mode', 'two_points')

        if mode == 'two_points':
            # Rectangle by two corner points
            p1_data = params['point1']
            p2_data = params['point2']

            p1 = adsk.core.Point3D.create(p1_data['x'], p1_data['y'], p1_data.get('z', 0))
            p2 = adsk.core.Point3D.create(p2_data['x'], p2_data['y'], p2_data.get('z', 0))

            lines = sketch.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)

            # Get the 4 lines of the rectangle
            line_info = []
            for line in lines:
                line_info.append({
                    'start': {'x': line.startSketchPoint.geometry.x, 'y': line.startSketchPoint.geometry.y},
                    'end': {'x': line.endSketchPoint.geometry.x, 'y': line.endSketchPoint.geometry.y}
                })

            return {
                'status': 'success',
                'data': {
                    'sketch': sketch_name,
                    'element_type': 'rectangle',
                    'corner1': p1_data,
                    'corner2': p2_data,
                    'lines': line_info,
                    'line_count': lines.count
                }
            }

        elif mode == 'center_point':
            # Rectangle by center point and corner point
            center_data = params['center']
            corner_data = params['corner']

            center = adsk.core.Point3D.create(center_data['x'], center_data['y'], center_data.get('z', 0))
            corner = adsk.core.Point3D.create(corner_data['x'], corner_data['y'], corner_data.get('z', 0))

            lines = sketch.sketchCurves.sketchLines.addCenterPointRectangle(center, corner)

            # Get the 4 lines of the rectangle
            line_info = []
            for line in lines:
                line_info.append({
                    'start': {'x': line.startSketchPoint.geometry.x, 'y': line.startSketchPoint.geometry.y},
                    'end': {'x': line.endSketchPoint.geometry.x, 'y': line.endSketchPoint.geometry.y}
                })

            return {
                'status': 'success',
                'data': {
                    'sketch': sketch_name,
                    'element_type': 'rectangle',
                    'center': center_data,
                    'corner': corner_data,
                    'lines': line_info,
                    'line_count': lines.count
                }
            }

        else:
            return {'status': 'error', 'message': f'Unknown rectangle mode: {mode}'}

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to add rectangle: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_sketch_add_point(params):
    """Add a point to a sketch"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        # Get point coordinates
        x = params['x']
        y = params['y']
        z = params.get('z', 0)

        # Create point
        point = adsk.core.Point3D.create(x, y, z)
        sketch_point = sketch.sketchPoints.add(point)

        return {
            'status': 'success',
            'data': {
                'sketch': sketch_name,
                'element_type': 'point',
                'coordinates': {
                    'x': sketch_point.geometry.x,
                    'y': sketch_point.geometry.y,
                    'z': sketch_point.geometry.z
                }
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to add point: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_sketch_add_constraint(params):
    """Add a geometric constraint to a sketch"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        constraint_type = params['constraint_type']

        # Helper function to get sketch entity by index
        def get_sketch_entity(entity_index, entity_type):
            if entity_type == 'line':
                if entity_index < sketch.sketchCurves.sketchLines.count:
                    return sketch.sketchCurves.sketchLines.item(entity_index)
            elif entity_type == 'circle':
                if entity_index < sketch.sketchCurves.sketchCircles.count:
                    return sketch.sketchCurves.sketchCircles.item(entity_index)
            elif entity_type == 'arc':
                if entity_index < sketch.sketchCurves.sketchArcs.count:
                    return sketch.sketchCurves.sketchArcs.item(entity_index)
            elif entity_type == 'point':
                if entity_index < sketch.sketchPoints.count:
                    return sketch.sketchPoints.item(entity_index)
            return None

        constraints = sketch.geometricConstraints
        constraint = None

        # Apply constraint based on type
        if constraint_type == 'horizontal':
            entity = get_sketch_entity(params['entity_index'], params.get('entity_type', 'line'))
            if entity:
                constraint = constraints.addHorizontal(entity)

        elif constraint_type == 'vertical':
            entity = get_sketch_entity(params['entity_index'], params.get('entity_type', 'line'))
            if entity:
                constraint = constraints.addVertical(entity)

        elif constraint_type == 'parallel':
            entity1 = get_sketch_entity(params['entity1_index'], params.get('entity1_type', 'line'))
            entity2 = get_sketch_entity(params['entity2_index'], params.get('entity2_type', 'line'))
            if entity1 and entity2:
                constraint = constraints.addParallel(entity1, entity2)

        elif constraint_type == 'perpendicular':
            entity1 = get_sketch_entity(params['entity1_index'], params.get('entity1_type', 'line'))
            entity2 = get_sketch_entity(params['entity2_index'], params.get('entity2_type', 'line'))
            if entity1 and entity2:
                constraint = constraints.addPerpendicular(entity1, entity2)

        elif constraint_type == 'tangent':
            entity1 = get_sketch_entity(params['entity1_index'], params['entity1_type'])
            entity2 = get_sketch_entity(params['entity2_index'], params['entity2_type'])
            if entity1 and entity2:
                constraint = constraints.addTangent(entity1, entity2)

        elif constraint_type == 'coincident':
            point1 = get_sketch_entity(params['point1_index'], 'point')
            # Support both point-to-point and point-to-curve coincident
            if 'point2_index' in params:
                # Point-to-point coincident
                point2 = get_sketch_entity(params['point2_index'], 'point')
                if point1 and point2:
                    constraint = constraints.addCoincident(point1, point2)
            elif 'entity2_index' in params:
                # Point-to-curve coincident
                entity2 = get_sketch_entity(params['entity2_index'], params['entity2_type'])
                if point1 and entity2:
                    constraint = constraints.addCoincident(point1, entity2)

        elif constraint_type == 'concentric':
            entity1 = get_sketch_entity(params['entity1_index'], params['entity1_type'])
            entity2 = get_sketch_entity(params['entity2_index'], params['entity2_type'])
            if entity1 and entity2:
                constraint = constraints.addConcentric(entity1, entity2)

        elif constraint_type == 'midpoint':
            point = get_sketch_entity(params['point_index'], 'point')
            line = get_sketch_entity(params['line_index'], 'line')
            if point and line:
                constraint = constraints.addMidPoint(point, line)

        elif constraint_type == 'equal':
            entity1 = get_sketch_entity(params['entity1_index'], params['entity1_type'])
            entity2 = get_sketch_entity(params['entity2_index'], params['entity2_type'])
            if entity1 and entity2:
                constraint = constraints.addEqual(entity1, entity2)

        else:
            return {'status': 'error', 'message': f'Unknown constraint type: {constraint_type}'}

        if constraint is None:
            return {'status': 'error', 'message': 'Failed to create constraint - invalid entities'}

        return {
            'status': 'success',
            'data': {
                'sketch': sketch_name,
                'constraint_type': constraint_type,
                'is_healthy': constraint.isValid
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to add constraint: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_sketch_add_dimension(params):
    """Add a dimension constraint to a sketch"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get sketch
        sketch_path = params['sketch_path']
        sketch_name = sketch_path.split('/')[-1]

        sketch = None
        for s in root.sketches:
            if s.name == sketch_name:
                sketch = s
                break

        if sketch is None:
            return {'status': 'error', 'message': f'Sketch "{sketch_name}" not found'}

        dimension_type = params['dimension_type']
        value = params['value']

        # Helper function to get sketch entity by index
        def get_sketch_entity(entity_index, entity_type):
            if entity_type == 'line':
                if entity_index < sketch.sketchCurves.sketchLines.count:
                    return sketch.sketchCurves.sketchLines.item(entity_index)
            elif entity_type == 'circle':
                if entity_index < sketch.sketchCurves.sketchCircles.count:
                    return sketch.sketchCurves.sketchCircles.item(entity_index)
            elif entity_type == 'arc':
                if entity_index < sketch.sketchCurves.sketchArcs.count:
                    return sketch.sketchCurves.sketchArcs.item(entity_index)
            elif entity_type == 'point':
                if entity_index < sketch.sketchPoints.count:
                    return sketch.sketchPoints.item(entity_index)
            return None

        dimensions = sketch.sketchDimensions
        dimension = None

        # Apply dimension based on type
        if dimension_type == 'distance':
            # Distance between two points
            point1 = get_sketch_entity(params['point1_index'], 'point')
            point2 = get_sketch_entity(params['point2_index'], 'point')
            if point1 and point2:
                text_point = adsk.core.Point3D.create(
                    (point1.geometry.x + point2.geometry.x) / 2,
                    (point1.geometry.y + point2.geometry.y) / 2,
                    0
                )
                dimension = dimensions.addDistanceDimension(
                    point1, point2,
                    adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                    text_point
                )

        elif dimension_type == 'linear':
            # Linear dimension for a line
            line = get_sketch_entity(params['line_index'], 'line')
            if line:
                text_point = adsk.core.Point3D.create(
                    (line.startSketchPoint.geometry.x + line.endSketchPoint.geometry.x) / 2,
                    (line.startSketchPoint.geometry.y + line.endSketchPoint.geometry.y) / 2 + 1,
                    0
                )
                dimension = dimensions.addDistanceDimension(
                    line.startSketchPoint, line.endSketchPoint,
                    adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                    text_point
                )

        elif dimension_type == 'radius':
            # Radius dimension for circle or arc
            entity = None
            if 'circle_index' in params:
                entity = get_sketch_entity(params['circle_index'], 'circle')
            elif 'arc_index' in params:
                entity = get_sketch_entity(params['arc_index'], 'arc')

            if entity:
                text_point = adsk.core.Point3D.create(
                    entity.centerSketchPoint.geometry.x + entity.radius,
                    entity.centerSketchPoint.geometry.y,
                    0
                )
                dimension = dimensions.addRadialDimension(entity, text_point)

        elif dimension_type == 'diameter':
            # Diameter dimension for circle or arc
            entity = None
            if 'circle_index' in params:
                entity = get_sketch_entity(params['circle_index'], 'circle')
            elif 'arc_index' in params:
                entity = get_sketch_entity(params['arc_index'], 'arc')

            if entity:
                text_point = adsk.core.Point3D.create(
                    entity.centerSketchPoint.geometry.x + entity.radius,
                    entity.centerSketchPoint.geometry.y,
                    0
                )
                dimension = dimensions.addDiameterDimension(entity, text_point)

        elif dimension_type == 'angle':
            # Angular dimension between two lines
            line1 = get_sketch_entity(params['line1_index'], 'line')
            line2 = get_sketch_entity(params['line2_index'], 'line')
            if line1 and line2:
                text_point = adsk.core.Point3D.create(0, 0, 0)
                dimension = dimensions.addAngularDimension(line1, line2, text_point)

        else:
            return {'status': 'error', 'message': f'Unknown dimension type: {dimension_type}'}

        if dimension is None:
            return {'status': 'error', 'message': 'Failed to create dimension - invalid entities'}

        # Set the dimension value
        dimension.parameter.value = value

        return {
            'status': 'success',
            'data': {
                'sketch': sketch_name,
                'dimension_type': dimension_type,
                'value': dimension.parameter.value,
                'parameter_name': dimension.parameter.name
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to add dimension: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_get_features(params):
    """Get all features from the timeline"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get component path if specified, default to root
        component = root
        component_path = params.get('component_path', 'root')

        if component_path != 'root':
            # Parse component path
            parts = component_path.split('/')
            if len(parts) > 2 and parts[1] in ['children', 'occurrences']:
                comp_name = parts[2]
                for occ in root.occurrences:
                    if occ.name == comp_name:
                        component = occ.component
                        break

        features_list = []

        # Iterate through all feature types
        for i in range(component.features.count):
            feature = component.features.item(i)

            # Get feature type name
            feature_type = type(feature).__name__.replace('Feature', '')

            # Get timeline object for this feature
            timeline_obj = None
            for j in range(design.timeline.count):
                tl = design.timeline.item(j)
                if tl.entity == feature:
                    timeline_obj = tl
                    break

            feature_info = {
                'index': i,
                'name': feature.name,
                'type': feature_type,
                'isSuppressed': feature.isSuppressed if hasattr(feature, 'isSuppressed') else None,
                'timelineIndex': timeline_obj.index if timeline_obj else None,
                'timelinePosition': timeline_obj.index if timeline_obj else None,
                'isRolledBack': timeline_obj.isRolledBack if timeline_obj else None
            }

            # Add health state if available
            if hasattr(feature, 'healthState'):
                feature_info['healthState'] = 'healthy' if feature.healthState == 0 else 'warning' if feature.healthState == 1 else 'error'

            # Add feature-specific properties
            if hasattr(feature, 'operation'):
                feature_info['operation'] = ['NewBodyFeatureOperation', 'JoinFeatureOperation', 'CutFeatureOperation', 'IntersectFeatureOperation'][feature.operation]

            features_list.append(feature_info)

        return {
            'status': 'success',
            'data': {
                'component': component.name,
                'component_path': component_path,
                'feature_count': len(features_list),
                'timeline_marker': design.timeline.markerPosition,
                'features': features_list
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to get features: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_suppress_feature(params):
    """Suppress or unsuppress a feature in the timeline"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get component
        component = root
        component_path = params.get('component_path', 'root')

        if component_path != 'root':
            parts = component_path.split('/')
            if len(parts) > 2 and parts[1] in ['children', 'occurrences']:
                comp_name = parts[2]
                for occ in root.occurrences:
                    if occ.name == comp_name:
                        component = occ.component
                        break

        # Get feature by index or name
        feature = None
        feature_identifier = params.get('feature_index')
        if feature_identifier is not None:
            # Get by index
            if feature_identifier < component.features.count:
                feature = component.features.item(feature_identifier)
        else:
            # Get by name
            feature_name = params.get('feature_name')
            if feature_name:
                for i in range(component.features.count):
                    feat = component.features.item(i)
                    if feat.name == feature_name:
                        feature = feat
                        break

        if not feature:
            return {'status': 'error', 'message': 'Feature not found'}

        # Check if feature supports suppression
        if not hasattr(feature, 'isSuppressed'):
            return {'status': 'error', 'message': f'Feature "{feature.name}" does not support suppression'}

        # Set suppression state
        suppress = params.get('suppress', True)
        feature.isSuppressed = suppress

        return {
            'status': 'success',
            'data': {
                'feature_name': feature.name,
                'feature_type': type(feature).__name__.replace('Feature', ''),
                'isSuppressed': feature.isSuppressed,
                'healthState': 'healthy' if hasattr(feature, 'healthState') and feature.healthState == 0 else 'warning' if hasattr(feature, 'healthState') and feature.healthState == 1 else 'error'
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to suppress feature: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_edit_feature(params):
    """Edit feature parameters"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    try:
        # Get component
        component = root
        component_path = params.get('component_path', 'root')

        if component_path != 'root':
            parts = component_path.split('/')
            if len(parts) > 2 and parts[1] in ['children', 'occurrences']:
                comp_name = parts[2]
                for occ in root.occurrences:
                    if occ.name == comp_name:
                        component = occ.component
                        break

        # Get feature by index or name
        feature = None
        feature_identifier = params.get('feature_index')
        if feature_identifier is not None:
            if feature_identifier < component.features.count:
                feature = component.features.item(feature_identifier)
        else:
            feature_name = params.get('feature_name')
            if feature_name:
                for i in range(component.features.count):
                    feat = component.features.item(i)
                    if feat.name == feature_name:
                        feature = feat
                        break

        if not feature:
            return {'status': 'error', 'message': 'Feature not found'}

        # Get parameters to edit
        edits = params.get('edits', {})
        applied_edits = {}

        # Common editable properties
        if 'name' in edits:
            feature.name = edits['name']
            applied_edits['name'] = feature.name

        # Feature-specific edits using parameters
        feature_type = type(feature).__name__

        # ExtrudeFeature
        if 'ExtrudeFeature' in feature_type:
            if 'distance' in edits:
                extent = feature.extentDefinition
                if hasattr(extent, 'distance') and hasattr(extent.distance, 'value'):
                    extent.distance.value = edits['distance']
                    applied_edits['distance'] = extent.distance.value

            if 'taper_angle' in edits:
                if hasattr(feature, 'taperAngle') and hasattr(feature.taperAngle, 'value'):
                    feature.taperAngle.value = edits['taper_angle']
                    applied_edits['taper_angle'] = feature.taperAngle.value

        # RevolveFeature
        elif 'RevolveFeature' in feature_type:
            if 'angle' in edits:
                if hasattr(feature, 'angle') and hasattr(feature.angle, 'value'):
                    feature.angle.value = edits['angle']
                    applied_edits['angle'] = feature.angle.value

        # FilletFeature
        elif 'FilletFeature' in feature_type:
            if 'radius' in edits:
                # Modify radius parameters
                for i in range(feature.edgeSets.count):
                    edge_set = feature.edgeSets.item(i)
                    if hasattr(edge_set, 'radius') and hasattr(edge_set.radius, 'value'):
                        edge_set.radius.value = edits['radius']
                        applied_edits['radius'] = edge_set.radius.value
                        break  # Only modify first edge set

        # ChamferFeature
        elif 'ChamferFeature' in feature_type:
            if 'distance' in edits:
                # ChamferFeature uses 'edgeSets', not 'chamferEdgeSets'
                for i in range(feature.edgeSets.count):
                    edge_set = feature.edgeSets.item(i)
                    if hasattr(edge_set, 'distance') and hasattr(edge_set.distance, 'value'):
                        edge_set.distance.value = edits['distance']
                        applied_edits['distance'] = edge_set.distance.value
                        break  # Only modify first edge set

        return {
            'status': 'success',
            'data': {
                'feature_name': feature.name,
                'feature_type': feature_type.replace('Feature', ''),
                'applied_edits': applied_edits,
                'healthState': 'healthy' if hasattr(feature, 'healthState') and feature.healthState == 0 else 'warning'
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to edit feature: {str(e)}',
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

def _handle_highlight_geometry(params):
    """Highlight specific geometry elements in the viewport"""
    app = adsk.core.Application.get()
    design = app.activeProduct
    ui = app.userInterface

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    try:
        # Get paths to highlight
        paths = params.get('paths', [])
        if isinstance(paths, str):
            paths = [paths]

        clear_selection = params.get('clear_selection', True)

        # Clear existing selection if requested
        if clear_selection:
            ui.activeSelections.clear()

        highlighted_elements = []

        # Add each element to selection
        for path in paths:
            try:
                element, element_type = _resolve_element_path(path)

                # Add to selection to highlight
                ui.activeSelections.add(element)

                highlighted_elements.append({
                    'path': path,
                    'type': element_type,
                    'name': element.name if hasattr(element, 'name') else 'Unnamed'
                })
            except Exception as e:
                highlighted_elements.append({
                    'path': path,
                    'error': str(e)
                })

        return {
            'status': 'success',
            'data': {
                'highlighted_count': len([h for h in highlighted_elements if 'error' not in h]),
                'elements': highlighted_elements
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to highlight geometry: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_measure_all_angles(params):
    """Measure all angles between edges or faces in a body"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    try:
        body_path = params.get('body_path')
        mode = params.get('mode', 'edges')  # 'edges' or 'faces'
        min_angle = params.get('min_angle', 0)  # in degrees
        max_angle = params.get('max_angle', 180)  # in degrees

        body, _ = _resolve_element_path(body_path)

        if not hasattr(body, 'edges') or not hasattr(body, 'faces'):
            return {'status': 'error', 'message': 'Element is not a body'}

        angles = []

        if mode == 'edges':
            # Measure angles between connected edges
            # Track edge pairs to avoid duplicates
            measured_pairs = set()

            for i in range(body.edges.count):
                edge1 = body.edges.item(i)

                # Find connected edges through vertices
                for vertex in [edge1.startVertex, edge1.endVertex]:
                    # Get all edges at this vertex that belong to the same body
                    for j in range(body.edges.count):
                        if i == j:
                            continue

                        edge2 = body.edges.item(j)

                        # Check if edge2 is connected to this vertex
                        if edge2.startVertex != vertex and edge2.endVertex != vertex:
                            continue

                        # Skip if we already measured this pair (order-independent)
                        pair_key = tuple(sorted([i, j]))
                        if pair_key in measured_pairs:
                            continue
                        measured_pairs.add(pair_key)

                        # Get tangent vectors at the vertex point for both edges
                        try:
                            # Get curve evaluators
                            eval1 = edge1.evaluator
                            eval2 = edge2.evaluator

                            # Get parameter at vertex point
                            result1, param1 = eval1.getParameterAtPoint(vertex.geometry)
                            result2, param2 = eval2.getParameterAtPoint(vertex.geometry)

                            if result1 and result2:
                                # Get tangent vectors at vertex
                                result1, tangent1 = eval1.getTangent(param1)
                                result2, tangent2 = eval2.getTangent(param2)

                                if result1 and result2:
                                    # Calculate angle between tangents
                                    dot_product = tangent1.dotProduct(tangent2)
                                    # Clamp to [-1, 1] to avoid math domain errors
                                    dot_product = max(-1.0, min(1.0, dot_product))
                                    angle_rad = math.acos(abs(dot_product))
                                    angle_deg = math.degrees(angle_rad)

                                    if min_angle <= angle_deg <= max_angle:
                                        angles.append({
                                            'edge1_index': i,
                                            'edge2_index': j,
                                            'angle_degrees': round(angle_deg, 2),
                                            'angle_radians': round(angle_rad, 4),
                                            'vertex': {
                                                'x': vertex.geometry.x,
                                                'y': vertex.geometry.y,
                                                'z': vertex.geometry.z
                                            }
                                        })
                        except Exception as e:
                            # Skip edges that fail tangent calculation
                            pass

        elif mode == 'faces':
            # Measure angles between adjacent faces
            for i in range(body.faces.count):
                face1 = body.faces.item(i)

                # Find adjacent faces through shared edges
                for edge in face1.edges:
                    for face2 in edge.faces:
                        if face2 == face1:
                            continue

                        # Find face2 index manually (BRepFaces doesn't have .index() method)
                        face2_index = -1
                        for j in range(body.faces.count):
                            if body.faces.item(j) == face2:
                                face2_index = j
                                break

                        if face2_index == -1:
                            continue

                        # Skip if we already measured this pair
                        already_measured = any(
                            a.get('face1_index') == face2_index and a.get('face2_index') == i
                            for a in angles
                        )
                        if already_measured:
                            continue

                        # Get face normals
                        if hasattr(face1.geometry, 'normal') and hasattr(face2.geometry, 'normal'):
                            evaluator1 = face1.evaluator
                            evaluator2 = face2.evaluator

                            # Get normals at face centers
                            result1, params1 = evaluator1.getParameterAtPoint(face1.pointOnFace)
                            result2, params2 = evaluator2.getParameterAtPoint(face2.pointOnFace)

                            if result1 and result2:
                                # params1/params2 are Point2D objects - pass them directly
                                result1, normal1 = evaluator1.getNormalAtParameter(params1)
                                result2, normal2 = evaluator2.getNormalAtParameter(params2)

                                if result1 and result2:
                                    # Calculate angle between normals
                                    dot_product = normal1.dotProduct(normal2)
                                    dot_product = max(-1.0, min(1.0, dot_product))
                                    angle_rad = math.acos(abs(dot_product))
                                    angle_deg = math.degrees(angle_rad)

                                    if min_angle <= angle_deg <= max_angle:
                                        angles.append({
                                            'face1_index': i,
                                            'face2_index': face2_index,
                                            'angle_degrees': round(angle_deg, 2),
                                            'angle_radians': round(angle_rad, 4)
                                        })

        return {
            'status': 'success',
            'data': {
                'body_path': body_path,
                'mode': mode,
                'angle_count': len(angles),
                'angles': angles
            }
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to measure angles: {str(e)}',
            'traceback': traceback.format_exc()
        }

def _handle_get_edge_relationships(params):
    """Get topology relationships for a specific edge"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    try:
        edge_path = params.get('edge_path')

        # Parse edge path manually (e.g., 'root/bRepBodies/Body1/edges/4')
        # _resolve_element_path doesn't handle /edges/INDEX, so we parse it ourselves
        if '/edges/' not in edge_path:
            return {'status': 'error', 'message': 'Invalid edge path - must contain /edges/INDEX'}

        parts = edge_path.split('/edges/')
        if len(parts) != 2:
            return {'status': 'error', 'message': 'Invalid edge path format'}

        body_path = parts[0]
        try:
            edge_index = int(parts[1])
        except ValueError:
            return {'status': 'error', 'message': 'Edge index must be an integer'}

        # Get the body
        body, body_type = _resolve_element_path(body_path)

        if body_type != 'BRepBody':
            return {'status': 'error', 'message': f'Path does not point to a BRepBody (got {body_type})'}

        # Get the edge from the body
        if edge_index < 0 or edge_index >= body.edges.count:
            return {'status': 'error', 'message': f'Edge index {edge_index} out of range (body has {body.edges.count} edges)'}

        edge = body.edges.item(edge_index)

        # Get edge geometry info
        edge_info = {
            'path': edge_path,
            'length': edge.length,
            'start_vertex': {
                'x': edge.startVertex.geometry.x,
                'y': edge.startVertex.geometry.y,
                'z': edge.startVertex.geometry.z
            },
            'end_vertex': {
                'x': edge.endVertex.geometry.x,
                'y': edge.endVertex.geometry.y,
                'z': edge.endVertex.geometry.z
            }
        }

        # Get curve type
        geom = edge.geometry
        if isinstance(geom, adsk.core.Line3D):
            edge_info['curve_type'] = 'line'
            # Line3D doesn't have .direction, compute from start/end points
            start = geom.startPoint
            end = geom.endPoint
            dir_vec = adsk.core.Vector3D.create(
                end.x - start.x,
                end.y - start.y,
                end.z - start.z
            )
            dir_vec.normalize()
            edge_info['direction'] = {
                'x': dir_vec.x,
                'y': dir_vec.y,
                'z': dir_vec.z
            }
        elif isinstance(geom, adsk.core.Arc3D):
            edge_info['curve_type'] = 'arc'
            edge_info['radius'] = geom.radius
        elif isinstance(geom, adsk.core.Circle3D):
            edge_info['curve_type'] = 'circle'
            edge_info['radius'] = geom.radius
        else:
            edge_info['curve_type'] = type(geom).__name__

        # Get connected edges through vertices
        connected_edges_start = []
        connected_edges_end = []

        # Get edges connected at start vertex
        for connected_edge in edge.startVertex.edges:
            if connected_edge != edge:
                # Find edge index manually (BRepEdges doesn't have .index() method)
                idx = -1
                for j in range(body.edges.count):
                    if body.edges.item(j) == connected_edge:
                        idx = j
                        break

                if idx != -1:
                    connected_edges_start.append({
                        'index': idx,
                        'path': f'{body_path}/edges/{idx}',
                        'length': connected_edge.length
                    })

        # Get edges connected at end vertex
        for connected_edge in edge.endVertex.edges:
            if connected_edge != edge:
                # Find edge index manually (BRepEdges doesn't have .index() method)
                idx = -1
                for j in range(body.edges.count):
                    if body.edges.item(j) == connected_edge:
                        idx = j
                        break

                if idx != -1:
                    connected_edges_end.append({
                        'index': idx,
                        'path': f'{body_path}/edges/{idx}',
                        'length': connected_edge.length
                    })

        edge_info['connected_at_start'] = connected_edges_start
        edge_info['connected_at_end'] = connected_edges_end

        # Get adjacent faces
        adjacent_faces = []
        for face in edge.faces:
            # Find face index manually (BRepFaces doesn't have .index() method)
            face_idx = -1
            for j in range(body.faces.count):
                if body.faces.item(j) == face:
                    face_idx = j
                    break

            if face_idx != -1:
                adjacent_faces.append({
                    'index': face_idx,
                    'path': f'{body_path}/faces/{face_idx}',
                    'area': face.area
                })

        edge_info['adjacent_faces'] = adjacent_faces
        edge_info['face_count'] = len(adjacent_faces)

        return {
            'status': 'success',
            'data': edge_info
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to get edge relationships: {str(e)}',
            'traceback': traceback.format_exc()
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
            elif operation == 'split_body':
                result = _handle_split_body(event_args.get('params', {}))
            elif operation == 'boolean_operation':
                result = _handle_boolean_operation(event_args.get('params', {}))
            elif operation == 'create_sketch':
                result = _handle_create_sketch(event_args.get('params', {}))
            elif operation == 'sketch_add_line':
                result = _handle_sketch_add_line(event_args.get('params', {}))
            elif operation == 'sketch_add_circle':
                result = _handle_sketch_add_circle(event_args.get('params', {}))
            elif operation == 'sketch_add_arc':
                result = _handle_sketch_add_arc(event_args.get('params', {}))
            elif operation == 'sketch_add_rectangle':
                result = _handle_sketch_add_rectangle(event_args.get('params', {}))
            elif operation == 'sketch_add_point':
                result = _handle_sketch_add_point(event_args.get('params', {}))
            elif operation == 'sketch_add_constraint':
                result = _handle_sketch_add_constraint(event_args.get('params', {}))
            elif operation == 'sketch_add_dimension':
                result = _handle_sketch_add_dimension(event_args.get('params', {}))
            elif operation == 'get_features':
                result = _handle_get_features(event_args.get('params', {}))
            elif operation == 'suppress_feature':
                result = _handle_suppress_feature(event_args.get('params', {}))
            elif operation == 'edit_feature':
                result = _handle_edit_feature(event_args.get('params', {}))
            elif operation == 'highlight_geometry':
                result = _handle_highlight_geometry(event_args.get('params', {}))
            elif operation == 'measure_all_angles':
                result = _handle_measure_all_angles(event_args.get('params', {}))
            elif operation == 'get_edge_relationships':
                result = _handle_get_edge_relationships(event_args.get('params', {}))
            elif operation == 'create_extrude':
                result = _handle_create_extrude(event_args.get('params', {}))
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
            'Fusion Script Executor v5.8.4\n\n'
            'FIXED v5.8.4: Added missing math import for measure_all_angles\n'
            'FIXED v5.8.3: measure_all_angles edge mode - restructured edge pair finding logic\n'
            'FIXED v5.8.2: get_edge_relationships Line3D direction, measure_all_angles Point2D/tangent API fixes\n'
            'FIXED v5.8.1: measure_all_angles and get_edge_relationships - fixed .index() errors and path parsing\n'
            'NEW v5.8.0: Visualization/Helper tools - highlight geometry, measure all angles, edge relationships\n'
            'NEW v5.7.0: Feature/Timeline tools - get features, suppress features, edit feature parameters\n'
            'NEW v5.6.0: Sketch constraints and dimensions - geometric constraints, parametric dimensions\n'
            'NEW v5.5.2: Added point tool to sketch tools\n'
            'FIXED v5.5.1: Arc response now returns working properties (start/end points, length)\n'
            'NEW v5.5.0: Sketch tools - create sketch, add lines, circles, arcs, rectangles\n'
            'FIXED v5.4.2: Simplified split_body - always keeps both halves\n'
            'FIXED v5.4.1: split_body now supports XY/XZ/YZ shortcuts and face paths\n'
            'v5.4: Body modification - split body, boolean operations\n'
            'v5.3: Transform tools - move, rotate, mirror bodies\n'
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