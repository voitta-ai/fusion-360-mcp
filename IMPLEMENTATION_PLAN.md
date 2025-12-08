# Implementation Plan: Native Fusion 360 Capabilities

## Overview
Add native capabilities to the HTTP/MCP chain to support:
1. Screenshot capture
2. Camera controls (get/set)
3. Component/body tree listing
4. View orientation capture

## Architecture Decision

### Chosen Approach: Operation-Based Single Endpoint
Extend the existing POST endpoint to support both arbitrary script execution and native operations via an "operation" discriminator field.

**Request Format:**
```json
{
  "operation": "screenshot | exec | get_tree | get_camera | set_camera",
  "params": { ... },
  "script": "..." // only for "exec" operation
}
```

**Rationale:**
- ✅ Single endpoint - no URL routing needed
- ✅ Backward compatible (defaults to exec if operation not specified)
- ✅ Clean separation between native ops and custom scripts
- ✅ Easy to extend with new operations
- ✅ Keeps existing threading/event model intact

## Implementation Details

### 1. HTTP.py Changes (HTTP/HTTP.py)

#### 1.1 Add Import for Image Handling
```python
import base64
import tempfile
import os
```

#### 1.2 Create Native Operation Handlers
Add helper functions that execute on main thread:

**Screenshot Handler:**
```python
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
```

**Get Camera Handler:**
```python
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
```

**Set Camera Handler:**
```python
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
```

**Get Tree Handler:**
```python
def _handle_get_tree(params):
    """Get complete component/body tree"""
    app = adsk.core.Application.get()
    design = app.activeProduct

    if not design:
        return {'status': 'error', 'message': 'No active design'}

    root = design.rootComponent

    def traverse_occurrence(occ):
        """Recursively traverse occurrence tree"""
        node = {
            'name': occ.name,
            'type': 'occurrence',
            'isVisible': occ.isVisible,
            'isLightBulbOn': occ.isLightBulbOn,
            'bodies': []
        }

        # Get bodies
        for body in occ.bRepBodies:
            node['bodies'].append({
                'name': body.name,
                'type': 'BRepBody',
                'isVisible': body.isVisible,
                'volume': body.volume,
                'area': body.area
            })

        # Recurse into children
        if occ.childOccurrences.count > 0:
            node['children'] = []
            for child in occ.childOccurrences:
                node['children'].append(traverse_occurrence(child))

        return node

    # Build tree
    tree = {
        'name': root.name,
        'type': 'root_component',
        'bodies': []
    }

    # Root bodies
    for body in root.bRepBodies:
        tree['bodies'].append({
            'name': body.name,
            'type': 'BRepBody',
            'isVisible': body.isVisible,
            'volume': body.volume,
            'area': body.area
        })

    # Child occurrences
    if root.occurrences.count > 0:
        tree['children'] = []
        for occ in root.occurrences:
            tree['children'].append(traverse_occurrence(occ))

    return {
        'status': 'success',
        'data': tree
    }
```

#### 1.3 Update MainThreadExecutor
Modify `MainThreadExecutor.notify()` to handle operations:

```python
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
                'app': app, 'ui': ui, 'design': design,
                'root': root, 'adsk': adsk, 'result': None
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
```

#### 1.4 Update AsyncScriptHandler
Modify to pass operation and params:

```python
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

        # Fire custom event
        app = adsk.core.Application.get()
        event_args = {
            'id': operation_id,
            'operation': operation,
            'params': params,
            'script': script_code
        }
        app.fireCustomEvent('FusionScriptExecutor', json.dumps(event_args))

        # ... rest of existing code unchanged
```

### 2. MCP Server Changes (MCP/fusion_mcp_server.py)

#### 2.1 Add New Tools
Update `handle_list_tools()` to expose 4 new tools + keep existing exec tool:

```python
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="execute_fusion_script",
            description="Execute arbitrary Python code in Fusion 360. Use this for custom operations not covered by other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Python code to execute. Has access to: app, ui, design, root, adsk. Set 'result' variable to return data."
                    }
                },
                "required": ["script"]
            }
        ),
        types.Tool(
            name="fusion_screenshot",
            description="Capture a screenshot of the current Fusion 360 viewport. Returns an image.",
            inputSchema={
                "type": "object",
                "properties": {
                    "width": {
                        "type": "integer",
                        "description": "Image width in pixels",
                        "default": 800
                    },
                    "height": {
                        "type": "integer",
                        "description": "Image height in pixels",
                        "default": 600
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_get_camera",
            description="Get the current viewport camera position, orientation, and settings.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="fusion_set_camera",
            description="Set the viewport camera position and orientation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "eye": {
                        "type": "object",
                        "description": "Camera position (eye point)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "target": {
                        "type": "object",
                        "description": "Point the camera is looking at",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "upVector": {
                        "type": "object",
                        "description": "Camera up direction",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "viewOrientation": {
                        "type": "integer",
                        "description": "Standard view orientation (ViewOrientationTypes enum value)"
                    },
                    "isSmoothTransition": {
                        "type": "boolean",
                        "description": "Animate camera transition",
                        "default": True
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_get_tree",
            description="Get the complete component and body tree of the active design. Returns hierarchical structure with all components, occurrences, and bodies.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]
```

#### 2.2 Update Tool Handler
Modify `handle_call_tool()` to route to appropriate operations and handle images:

```python
@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution"""

    # Map tool name to operation
    operation_map = {
        'execute_fusion_script': 'exec',
        'fusion_screenshot': 'screenshot',
        'fusion_get_camera': 'get_camera',
        'fusion_set_camera': 'set_camera',
        'fusion_get_tree': 'get_tree'
    }

    if name not in operation_map:
        raise ValueError(f"Unknown tool: {name}")

    operation = operation_map[name]

    # Build request payload
    payload = {"operation": operation}

    if operation == 'exec':
        payload['script'] = arguments.get('script', '')
    else:
        payload['params'] = arguments or {}

    try:
        response = requests.post(
            FUSION_URL,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()

            # Handle image response
            if operation == 'screenshot' and result.get('status') == 'success':
                data = result['data']
                return [
                    types.ImageContent(
                        type="image",
                        data=data['image'],
                        mimeType=data['mimeType']
                    ),
                    types.TextContent(
                        type="text",
                        text=f"Screenshot captured: {data['width']}x{data['height']}"
                    )
                ]

            # Handle regular JSON response
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        else:
            error_data = response.json()
            return [types.TextContent(
                type="text",
                text=f"Error: {error_data.get('error', 'Unknown error')}\n\nTraceback:\n{error_data.get('traceback', 'N/A')}"
            )]

    except requests.exceptions.ConnectionError:
        return [types.TextContent(
            type="text",
            text="Error: Cannot connect to Fusion 360. Make sure the HTTP Add-In is running."
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]
```

## Implementation Steps

1. **Backup existing files**
   - Copy `HTTP/HTTP.py` to `HTTP/HTTP.py.backup`
   - Copy `MCP/fusion_mcp_server.py` to `MCP/fusion_mcp_server.py.backup`

2. **Implement HTTP.py changes**
   - Add imports (base64, tempfile, os)
   - Add 4 handler functions
   - Update MainThreadExecutor.notify()
   - Update AsyncScriptHandler.do_POST()

3. **Implement MCP changes**
   - Update handle_list_tools() with 5 tools
   - Update handle_call_tool() with routing and image handling

4. **Test each capability**
   - Test screenshot capture and image return
   - Test get_camera returns correct data
   - Test set_camera updates viewport
   - Test get_tree returns full hierarchy
   - Test backward compatibility with execute_fusion_script

5. **Update version numbers**
   - Bump HTTP add-in version in startup message
   - Bump MCP server version in InitializationOptions

## Testing Plan

### Unit Tests (Manual)

**Screenshot:**
```python
# Claude calls fusion_screenshot with width=1024, height=768
# Expected: Returns PNG image 1024x768
```

**Get Camera:**
```python
# Claude calls fusion_get_camera
# Expected: Returns JSON with eye, target, upVector, viewOrientation
```

**Set Camera:**
```python
# Claude calls fusion_set_camera with new eye position
# Expected: Viewport camera moves to new position
```

**Get Tree:**
```python
# In design with 3 components, 2 bodies each
# Claude calls fusion_get_tree
# Expected: Returns tree with 3 children, each with 2 bodies
```

**Backward Compatibility:**
```python
# Claude calls execute_fusion_script with old-style script
# Expected: Still works as before
```

## Risk Assessment

**Low Risk:**
- Screenshot: Read-only operation, temp file cleanup
- Get Camera: Read-only operation
- Get Tree: Read-only operation

**Medium Risk:**
- Set Camera: Modifies viewport state (but non-destructive, user can pan/zoom back)

**Mitigation:**
- All operations maintain existing thread-safety model
- Error handling wraps all new operations
- Temp files cleaned up in finally blocks
- Backward compatibility preserved

## Future Enhancements

Potential additions:
- `fusion_fit_view` - Fit all geometry in view
- `fusion_export_stl` - Export design to STL
- `fusion_get_selection` - Get currently selected entities
- `fusion_highlight_entity` - Highlight specific component/body

## API References

- [Viewport.saveAsImageFile](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Viewport_saveAsImageFile.htm)
- [Camera Object](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Camera.htm)
- [Components and Occurrences](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ComponentsProxies_UM.htm)
- [MCP Schema Reference](https://modelcontextprotocol.io/specification/2025-06-18/schema)
