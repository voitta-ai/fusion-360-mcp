#!/usr/bin/env python3
"""
MCP Server for Fusion 360 Control
Allows Claude Desktop to execute Python code in Fusion 360
"""

import asyncio
import json
import requests
from typing import Any
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

# Fusion 360 HTTP server endpoint
FUSION_URL = "http://localhost:8080"

# Create server instance
server = Server("fusion360-mcp")

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
            description="Get the complete design tree with ALL elements: components, occurrences, bodies (BRep & mesh), sketches, construction geometry, features, joints, and parameters. Comprehensive hierarchical structure of the entire design.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="fusion_set_element_properties",
            description="Set properties (visibility, grounding) for any design element. Use paths from fusion_get_tree to identify elements. Examples: 'root/bodies/Body1', 'root/occurrences/Component1', 'root/sketches/Sketch1'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Hierarchical path to element. Accepts paths from fusion_get_tree output. Format: 'root/[category]/[name]' where category is: bodies|bRepBodies, sketches, meshBodies, occurrences|children, constructionPlanes, constructionAxes, constructionPoints. For nested: 'root/children/OccName/bRepBodies/BodyName'"
                    },
                    "isVisible": {
                        "type": "boolean",
                        "description": "Set visibility (true=visible, false=hidden). Applicable to most elements."
                    },
                    "isGrounded": {
                        "type": "boolean",
                        "description": "Set grounding state (true=grounded, false=ungrounded). Only applicable to occurrences."
                    }
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="fusion_measure_distance",
            description="Measure distance between two entities (points, edges). Returns precise measurements with coordinates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["points", "edges"],
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
                        "description": "Path to first edge (for mode='edges'). Format: 'root/bRepBodies/BodyName/edges/0' or from fusion_get_tree + '/edges/INDEX'"
                    },
                    "edge2": {
                        "type": "string",
                        "description": "Path to second edge (for mode='edges'). Format: 'root/bRepBodies/BodyName/edges/1' or from fusion_get_tree + '/edges/INDEX'"
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
                        "enum": ["edges", "faces"],
                        "description": "Type of angle measurement"
                    },
                    "edge1": {
                        "type": "string",
                        "description": "Path to first edge (for edges mode). Format: 'root/bRepBodies/BodyName/edges/0' or from fusion_get_tree + '/edges/INDEX'"
                    },
                    "edge2": {
                        "type": "string",
                        "description": "Path to second edge (for edges mode). Format: 'root/bRepBodies/BodyName/edges/1' or from fusion_get_tree + '/edges/INDEX'"
                    },
                    "face1": {
                        "type": "string",
                        "description": "Path to first face (for faces mode). Format: 'root/bRepBodies/BodyName/faces/0' or from fusion_get_tree + '/faces/INDEX'"
                    },
                    "face2": {
                        "type": "string",
                        "description": "Path to second face (for faces mode). Format: 'root/bRepBodies/BodyName/faces/1' or from fusion_get_tree + '/faces/INDEX'"
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
            description="Get detailed information about edge(s): length, start/end points, direction, curve type. Can list all edges on a body with indices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to specific edge (e.g., 'root/bRepBodies/Body1/edges/5'). Use path from fusion_get_tree + '/edges/INDEX'"
                    },
                    "body_path": {
                        "type": "string",
                        "description": "Path to body (when list_all=true). Example: 'root/bRepBodies/WingBody' or 'root/children/Comp1/bRepBodies/Body1'"
                    },
                    "list_all": {
                        "type": "boolean",
                        "description": "If true, list all edges on the body with their indices",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_get_face_info",
            description="Get detailed information about face(s): area, normal vector, center point, surface type. Can list all faces on a body with indices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to specific face (e.g., 'root/bRepBodies/Body1/faces/3'). Use path from fusion_get_tree + '/faces/INDEX'"
                    },
                    "body_path": {
                        "type": "string",
                        "description": "Path to body (when list_all=true). Example: 'root/bRepBodies/WingBody' or 'root/children/Comp1/bRepBodies/Body1'"
                    },
                    "list_all": {
                        "type": "boolean",
                        "description": "If true, list all faces on the body with their indices",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_find_edges_by_criteria",
            description="Search for edges matching criteria: length, curve type, location, orientation. Returns array of matching edges with full info and paths. Useful for finding specific geometry patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "body_path": {
                        "type": "string",
                        "description": "Path to body to search. Example: 'root/bRepBodies/Body1' or 'root/children/Comp1/bRepBodies/Body1'"
                    },
                    "criteria": {
                        "type": "object",
                        "description": "Search criteria. All specified criteria must match (AND logic).",
                        "properties": {
                            "length_min": {
                                "type": "number",
                                "description": "Minimum edge length in cm"
                            },
                            "length_max": {
                                "type": "number",
                                "description": "Maximum edge length in cm"
                            },
                            "length_equals": {
                                "type": "number",
                                "description": "Exact edge length in cm (with tolerance)"
                            },
                            "length_tolerance": {
                                "type": "number",
                                "description": "Tolerance for length_equals (default: 0.001 cm)",
                                "default": 0.001
                            },
                            "curve_type": {
                                "type": "string",
                                "enum": ["line", "arc", "circle", "ellipse", "elliptical_arc", "spline"],
                                "description": "Type of curve geometry"
                            },
                            "near_point": {
                                "type": "object",
                                "description": "Find edges near this point (checks edge midpoint)",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"},
                                    "radius": {"type": "number", "description": "Search radius in cm"}
                                }
                            },
                            "parallel_to": {
                                "type": "object",
                                "description": "Find edges parallel to this direction vector",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"}
                                }
                            },
                            "perpendicular_to": {
                                "type": "object",
                                "description": "Find edges perpendicular to this direction vector",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"}
                                }
                            },
                            "angle_tolerance": {
                                "type": "number",
                                "description": "Tolerance for parallel/perpendicular checks in radians (default: 0.017 = ~1 degree)",
                                "default": 0.017
                            }
                        }
                    }
                },
                "required": ["body_path"]
            }
        ),
        types.Tool(
            name="fusion_find_faces_by_criteria",
            description="Search for faces matching criteria: area, surface type, normal direction. Returns array of matching faces with full info and paths. Useful for finding specific surface patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "body_path": {
                        "type": "string",
                        "description": "Path to body to search. Example: 'root/bRepBodies/Body1' or 'root/children/Comp1/bRepBodies/Body1'"
                    },
                    "criteria": {
                        "type": "object",
                        "description": "Search criteria. All specified criteria must match (AND logic).",
                        "properties": {
                            "area_min": {
                                "type": "number",
                                "description": "Minimum face area in cm²"
                            },
                            "area_max": {
                                "type": "number",
                                "description": "Maximum face area in cm²"
                            },
                            "area_equals": {
                                "type": "number",
                                "description": "Exact face area in cm² (with tolerance)"
                            },
                            "area_tolerance": {
                                "type": "number",
                                "description": "Tolerance for area_equals (default: 0.001 cm²)",
                                "default": 0.001
                            },
                            "surface_type": {
                                "type": "string",
                                "enum": ["planar", "cylindrical", "conical", "spherical", "toroidal"],
                                "description": "Type of surface geometry"
                            },
                            "normal_direction": {
                                "type": "object",
                                "description": "Find planar faces with normal in this direction",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"}
                                }
                            },
                            "near_point": {
                                "type": "object",
                                "description": "Find faces near this point (checks face centroid)",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"},
                                    "radius": {"type": "number", "description": "Search radius in cm"}
                                }
                            },
                            "angle_tolerance": {
                                "type": "number",
                                "description": "Tolerance for normal direction checks in radians (default: 0.017 = ~1 degree)",
                                "default": 0.017
                            }
                        }
                    }
                },
                "required": ["body_path"]
            }
        ),
        types.Tool(
            name="fusion_create_plane",
            description="Create construction plane: offset from existing plane, at angle, through three points, or perpendicular to edge. Returns path to created plane.",
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
                        "description": "Path to reference plane (for offset/angle modes). Example: 'root/constructionPlanes/XY Plane' or use predefined: 'root/constructionPlanes/XY Plane', 'root/constructionPlanes/XZ Plane', 'root/constructionPlanes/YZ Plane'"
                    },
                    "offset": {
                        "type": "number",
                        "description": "Offset distance in cm (for offset mode)"
                    },
                    "angle": {
                        "type": "number",
                        "description": "Angle in degrees (for angle mode)"
                    },
                    "axis": {
                        "type": "string",
                        "description": "Rotation axis (for angle mode). Can be 'X', 'Y', 'Z' or path to construction axis"
                    },
                    "point1": {
                        "type": "object",
                        "description": "First point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "point2": {
                        "type": "object",
                        "description": "Second point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "point3": {
                        "type": "object",
                        "description": "Third point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "edge": {
                        "type": "string",
                        "description": "Path to edge (for perpendicular mode). Format: 'root/bRepBodies/Body1/edges/0'"
                    },
                    "point": {
                        "type": "object",
                        "description": "Point on plane (for perpendicular mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional name for the plane (default: 'ConstructionPlane')"
                    }
                },
                "required": ["mode"]
            }
        ),
        types.Tool(
            name="fusion_create_axis",
            description="Create construction axis along an edge or perpendicular to face. Returns path to created axis. NOTE: Two-points mode not supported due to Fusion API limitations - create a sketch line first and use edge mode instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["edge", "perpendicular"],
                        "description": "Construction method: 'edge' = along existing edge, 'perpendicular' = normal to face at point"
                    },
                    "edge": {
                        "type": "string",
                        "description": "Path to edge (for edge mode). Format: 'root/bRepBodies/Body1/edges/0'"
                    },
                    "face": {
                        "type": "string",
                        "description": "Path to face (for perpendicular mode). Format: 'root/bRepBodies/Body1/faces/0'"
                    },
                    "point": {
                        "type": "object",
                        "description": "Point on axis (for perpendicular mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional name for the axis (default: 'ConstructionAxis')"
                    }
                },
                "required": ["mode"]
            }
        ),
        types.Tool(
            name="fusion_move_body",
            description="Move a body by a translation vector. Non-destructive transform operation that creates a timeline feature.",
            inputSchema={
                "type": "object",
                "properties": {
                    "body_path": {
                        "type": "string",
                        "description": "Path to body to move. Format: 'root/bRepBodies/BodyName'"
                    },
                    "vector": {
                        "type": "object",
                        "description": "Translation vector (x, y, z) in cm",
                        "properties": {
                            "x": {"type": "number", "description": "X displacement in cm"},
                            "y": {"type": "number", "description": "Y displacement in cm"},
                            "z": {"type": "number", "description": "Z displacement in cm"}
                        },
                        "required": ["x", "y", "z"]
                    }
                },
                "required": ["body_path", "vector"]
            }
        ),
        types.Tool(
            name="fusion_rotate_body",
            description="Rotate a body around an axis by a specified angle. Non-destructive transform operation that creates a timeline feature.",
            inputSchema={
                "type": "object",
                "properties": {
                    "body_path": {
                        "type": "string",
                        "description": "Path to body to rotate. Format: 'root/bRepBodies/BodyName'"
                    },
                    "axis": {
                        "type": "object",
                        "description": "Rotation axis definition",
                        "properties": {
                            "origin": {
                                "type": "object",
                                "description": "Point on the rotation axis",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"}
                                },
                                "required": ["x", "y", "z"]
                            },
                            "direction": {
                                "type": "object",
                                "description": "Axis direction vector (will be normalized)",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"}
                                },
                                "required": ["x", "y", "z"]
                            }
                        },
                        "required": ["origin", "direction"]
                    },
                    "angle": {
                        "type": "number",
                        "description": "Rotation angle in degrees (positive = counter-clockwise when looking along axis direction)"
                    }
                },
                "required": ["body_path", "axis", "angle"]
            }
        ),
        types.Tool(
            name="fusion_mirror_body",
            description="Mirror a body across a plane. Creates a mirrored copy. Non-destructive operation that creates a timeline feature.",
            inputSchema={
                "type": "object",
                "properties": {
                    "body_path": {
                        "type": "string",
                        "description": "Path to body to mirror. Format: 'root/bRepBodies/BodyName'"
                    },
                    "mirror_plane": {
                        "type": "string",
                        "description": "Path to mirror plane. Can be construction plane (e.g., 'root/constructionPlanes/XY Plane') or 'XY'/'XZ'/'YZ' for built-in planes"
                    }
                },
                "required": ["body_path", "mirror_plane"]
            }
        )
    ]

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
        'fusion_get_tree': 'get_tree',
        'fusion_set_element_properties': 'set_element_properties',
        'fusion_measure_distance': 'measure_distance',
        'fusion_measure_angle': 'measure_angle',
        'fusion_get_edge_info': 'get_edge_info',
        'fusion_get_face_info': 'get_face_info',
        'fusion_find_edges_by_criteria': 'find_edges_by_criteria',
        'fusion_find_faces_by_criteria': 'find_faces_by_criteria',
        'fusion_create_plane': 'create_plane',
        'fusion_create_axis': 'create_axis',
        'fusion_move_body': 'move_body',
        'fusion_rotate_body': 'rotate_body',
        'fusion_mirror_body': 'mirror_body'
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

async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="fusion360-mcp",
                server_version="0.7.1",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
