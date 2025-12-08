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

            if part == 'bodies':
                # Next part is body name
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Body name missing after "bodies"'}
                body_name = parts[i + 1]
                for body in current.bRepBodies:
                    if body.name == body_name:
                        element = body
                        break
                if not element:
                    return {'status': 'error', 'message': f'Body "{body_name}" not found'}
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

            elif part == 'occurrences':
                if i + 1 >= len(parts):
                    return {'status': 'error', 'message': 'Occurrence name missing'}
                occ_name = parts[i + 1]
                found_occ = None
                for occ in current.occurrences:
                    if occ.name == occ_name:
                        found_occ = occ
                        break
                if not found_occ:
                    return {'status': 'error', 'message': f'Occurrence "{occ_name}" not found'}

                # If this is the last element, we're targeting the occurrence itself
                if i + 2 >= len(parts):
                    element = found_occ
                    break

                # Otherwise, continue navigating into the occurrence's component
                current = found_occ.component
                i += 2
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
            'Fusion Script Executor v4.1\n\n'
            'Native operations: screenshot, camera, tree, visibility/grounding\n'
            'All operations execute on Fusion\'s main thread!\n\n'
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