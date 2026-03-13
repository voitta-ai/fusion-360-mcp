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

# Fusion 360 HTTP server endpoint (mutable for runtime configuration)
_fusion_server = "localhost"
_fusion_port = 8080

# Aliases that map to localhost
LOCAL_ALIASES = {
    'local', 'localhost', 'local computer', 'this computer',
    'here', 'self', 'this machine', 'my computer'
}

def get_fusion_url():
    """Get the current Fusion server URL"""
    return f"http://{_fusion_server}:{_fusion_port}"

def set_fusion_server(server: str):
    """Set the Fusion server address"""
    global _fusion_server
    # Normalize and check for local aliases
    normalized = server.strip().lower()
    if normalized in LOCAL_ALIASES:
        _fusion_server = "localhost"
    else:
        _fusion_server = server.strip()
    return _fusion_server

def is_local_server():
    """Check if currently connected to localhost"""
    return _fusion_server.lower() in ('localhost', '127.0.0.1')

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
        ),
        types.Tool(
            name="fusion_split_body",
            description="Split a body using a plane or face as the splitting tool. Creates two separate bodies from the original. Modifies the design timeline.",
            inputSchema={
                "type": "object",
                "properties": {
                    "body_path": {
                        "type": "string",
                        "description": "Path to body to split. Format: 'root/bRepBodies/BodyName'"
                    },
                    "split_tool": {
                        "type": "string",
                        "description": "Path to splitting tool. Can be construction plane (e.g., 'root/constructionPlanes/Plane1' or 'XY'/'XZ'/'YZ') or face path (e.g., 'root/bRepBodies/Body/faces/0')"
                    }
                },
                "required": ["body_path", "split_tool"]
            }
        ),
        types.Tool(
            name="fusion_boolean_operation",
            description="Perform boolean operation (join, cut, intersect) between two bodies. Modifies the target body and optionally consumes the tool body. Modifies the design timeline.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_body": {
                        "type": "string",
                        "description": "Path to target body (the body being modified). Format: 'root/bRepBodies/BodyName'"
                    },
                    "tool_body": {
                        "type": "string",
                        "description": "Path to tool body (the body used for the operation). Format: 'root/bRepBodies/BodyName'"
                    },
                    "operation": {
                        "type": "string",
                        "description": "Boolean operation type",
                        "enum": ["join", "cut", "intersect"]
                    },
                    "keep_tool": {
                        "type": "boolean",
                        "description": "If true, keep the tool body after operation. If false, tool body is consumed. Default: false",
                        "default": False
                    }
                },
                "required": ["target_body", "tool_body", "operation"]
            }
        ),
        types.Tool(
            name="fusion_create_extrude",
            description="Create an extrusion feature from a sketch profile. Supports all extent types, directions, operations, and taper angles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch containing the profile. Format: 'root/sketches/SketchName'"
                    },
                    "profile_index": {
                        "type": "integer",
                        "description": "Index of profile to extrude (default: 0, use -1 for all profiles)",
                        "default": 0
                    },
                    "extent_type": {
                        "type": "string",
                        "enum": ["distance", "to_object", "through_all", "all"],
                        "description": "Extent type: distance (by value), to_object (up to face/plane), through_all (through entire model), all (both directions through all)",
                        "default": "distance"
                    },
                    "distance": {
                        "type": "number",
                        "description": "Extrusion distance in cm (required for 'distance' extent_type)"
                    },
                    "to_entity": {
                        "type": "string",
                        "description": "Path to face or plane for 'to_object' extent. Format: 'root/bRepBodies/Body/faces/0' or 'root/constructionPlanes/Plane1'"
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["one_side", "two_sides", "symmetric"],
                        "description": "Direction mode: one_side (positive direction), two_sides (asymmetric both directions), symmetric (equal both directions)",
                        "default": "one_side"
                    },
                    "distance_two": {
                        "type": "number",
                        "description": "Second side distance in cm (for 'two_sides' direction)"
                    },
                    "taper_angle": {
                        "type": "number",
                        "description": "Taper/draft angle in degrees (default: 0)",
                        "default": 0
                    },
                    "taper_angle_two": {
                        "type": "number",
                        "description": "Second side taper angle in degrees (for 'two_sides' direction)",
                        "default": 0
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["new_body", "join", "cut", "intersect", "new_component"],
                        "description": "Operation type: new_body, join, cut, intersect with existing body, or new_component",
                        "default": "new_body"
                    },
                    "target_body": {
                        "type": "string",
                        "description": "Path to target body for join/cut/intersect operations. Format: 'root/bRepBodies/BodyName'"
                    }
                },
                "required": ["sketch_path"]
            }
        ),
        types.Tool(
            name="fusion_create_sketch",
            description="Create a new sketch on a construction plane. Sketches can then have geometry added via sketch_add_* tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plane": {
                        "type": "string",
                        "description": "Path to construction plane. Can use shortcuts 'XY', 'XZ', 'YZ' or full path like 'root/constructionPlanes/Plane1'"
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional name for the sketch (default: 'Sketch')",
                        "default": "Sketch"
                    }
                },
                "required": ["plane"]
            }
        ),
        types.Tool(
            name="fusion_sketch_add_line",
            description="Add a line to an existing sketch. Requires sketch_path from fusion_create_sketch or fusion_get_tree.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch. Format: 'root/sketches/SketchName'"
                    },
                    "point1": {
                        "type": "object",
                        "description": "Start point in sketch coordinates (x, y)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        },
                        "required": ["x", "y"]
                    },
                    "point2": {
                        "type": "object",
                        "description": "End point in sketch coordinates (x, y)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        },
                        "required": ["x", "y"]
                    }
                },
                "required": ["sketch_path", "point1", "point2"]
            }
        ),
        types.Tool(
            name="fusion_sketch_add_circle",
            description="Add a circle to an existing sketch. Supports center+radius or 3-point circle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch. Format: 'root/sketches/SketchName'"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["center_radius", "three_points"],
                        "description": "Circle creation mode",
                        "default": "center_radius"
                    },
                    "center": {
                        "type": "object",
                        "description": "Center point (for center_radius mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "radius": {
                        "type": "number",
                        "description": "Circle radius in cm (for center_radius mode)"
                    },
                    "point1": {
                        "type": "object",
                        "description": "First point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "point2": {
                        "type": "object",
                        "description": "Second point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "point3": {
                        "type": "object",
                        "description": "Third point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    }
                },
                "required": ["sketch_path"]
            }
        ),
        types.Tool(
            name="fusion_sketch_add_arc",
            description="Add an arc to an existing sketch. Supports 3-point arc or center+start+sweep arc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch. Format: 'root/sketches/SketchName'"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["three_points", "center_start_end"],
                        "description": "Arc creation mode",
                        "default": "three_points"
                    },
                    "point1": {
                        "type": "object",
                        "description": "First/start point",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "point2": {
                        "type": "object",
                        "description": "Second/mid point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "point3": {
                        "type": "object",
                        "description": "Third/end point (for three_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "center": {
                        "type": "object",
                        "description": "Center point (for center_start_end mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "start": {
                        "type": "object",
                        "description": "Start point (for center_start_end mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "sweep_angle": {
                        "type": "number",
                        "description": "Sweep angle in degrees (for center_start_end mode)"
                    }
                },
                "required": ["sketch_path"]
            }
        ),
        types.Tool(
            name="fusion_sketch_add_rectangle",
            description="Add a rectangle to an existing sketch. Supports two-corner or center-corner rectangle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch. Format: 'root/sketches/SketchName'"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["two_points", "center_point"],
                        "description": "Rectangle creation mode",
                        "default": "two_points"
                    },
                    "point1": {
                        "type": "object",
                        "description": "First corner (for two_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "point2": {
                        "type": "object",
                        "description": "Opposite corner (for two_points mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "center": {
                        "type": "object",
                        "description": "Center point (for center_point mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    },
                    "corner": {
                        "type": "object",
                        "description": "Corner point (for center_point mode)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"}
                        }
                    }
                },
                "required": ["sketch_path"]
            }
        ),
        types.Tool(
            name="fusion_sketch_add_point",
            description="Add a point to an existing sketch at specified coordinates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch. Format: 'root/sketches/SketchName'"
                    },
                    "x": {
                        "type": "number",
                        "description": "X coordinate of the point"
                    },
                    "y": {
                        "type": "number",
                        "description": "Y coordinate of the point"
                    },
                    "z": {
                        "type": "number",
                        "description": "Z coordinate of the point (defaults to 0 for 2D sketches)",
                        "default": 0
                    }
                },
                "required": ["sketch_path", "x", "y"]
            }
        ),
        types.Tool(
            name="fusion_sketch_add_constraint",
            description="Add a geometric constraint to sketch entities. Supports horizontal, vertical, parallel, perpendicular, tangent, coincident, concentric, midpoint, and equal constraints.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch. Format: 'root/sketches/SketchName'"
                    },
                    "constraint_type": {
                        "type": "string",
                        "description": "Type of constraint",
                        "enum": ["horizontal", "vertical", "parallel", "perpendicular", "tangent", "coincident", "concentric", "midpoint", "equal"]
                    },
                    "entity_index": {
                        "type": "integer",
                        "description": "Index of entity for single-entity constraints (horizontal, vertical)"
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity for single-entity constraints",
                        "enum": ["line", "circle", "arc", "point"]
                    },
                    "entity1_index": {
                        "type": "integer",
                        "description": "Index of first entity for two-entity constraints"
                    },
                    "entity1_type": {
                        "type": "string",
                        "description": "Type of first entity",
                        "enum": ["line", "circle", "arc", "point"]
                    },
                    "entity2_index": {
                        "type": "integer",
                        "description": "Index of second entity for two-entity constraints"
                    },
                    "entity2_type": {
                        "type": "string",
                        "description": "Type of second entity",
                        "enum": ["line", "circle", "arc", "point"]
                    },
                    "point_index": {
                        "type": "integer",
                        "description": "Index of point for midpoint constraint"
                    },
                    "point1_index": {
                        "type": "integer",
                        "description": "Index of point for coincident constraint. Use with point2_index (point-to-point) or entity2_index+entity2_type (point-to-curve)"
                    },
                    "point2_index": {
                        "type": "integer",
                        "description": "Index of second point for point-to-point coincident constraint"
                    },
                    "line_index": {
                        "type": "integer",
                        "description": "Index of line for midpoint constraint"
                    }
                },
                "required": ["sketch_path", "constraint_type"]
            }
        ),
        types.Tool(
            name="fusion_sketch_add_dimension",
            description="Add a dimension constraint to sketch entities. Supports distance, linear, radius, diameter, and angle dimensions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sketch_path": {
                        "type": "string",
                        "description": "Path to sketch. Format: 'root/sketches/SketchName'"
                    },
                    "dimension_type": {
                        "type": "string",
                        "description": "Type of dimension",
                        "enum": ["distance", "linear", "radius", "diameter", "angle"]
                    },
                    "value": {
                        "type": "number",
                        "description": "Dimension value in current document units (cm for distance/radius/diameter, degrees for angle)"
                    },
                    "point1_index": {
                        "type": "integer",
                        "description": "Index of first point for distance dimension (point-to-point only)"
                    },
                    "point2_index": {
                        "type": "integer",
                        "description": "Index of second point for distance dimension (required for distance type)"
                    },
                    "line_index": {
                        "type": "integer",
                        "description": "Index of line for linear dimension"
                    },
                    "circle_index": {
                        "type": "integer",
                        "description": "Index of circle for radius/diameter dimension"
                    },
                    "arc_index": {
                        "type": "integer",
                        "description": "Index of arc for radius/diameter dimension"
                    },
                    "line1_index": {
                        "type": "integer",
                        "description": "Index of first line for angle dimension"
                    },
                    "line2_index": {
                        "type": "integer",
                        "description": "Index of second line for angle dimension"
                    }
                },
                "required": ["sketch_path", "dimension_type", "value"]
            }
        ),
        types.Tool(
            name="fusion_get_features",
            description="Get all features from the timeline with their properties. Returns feature list with names, types, suppression states, and timeline positions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "component_path": {
                        "type": "string",
                        "description": "Path to component (default: 'root'). Format: 'root' or 'root/children/ComponentName'",
                        "default": "root"
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_suppress_feature",
            description="Suppress or unsuppress a feature in the timeline. Suppressed features are skipped during regeneration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "component_path": {
                        "type": "string",
                        "description": "Path to component (default: 'root')",
                        "default": "root"
                    },
                    "feature_index": {
                        "type": "integer",
                        "description": "Feature index from fusion_get_features. Use either feature_index or feature_name."
                    },
                    "feature_name": {
                        "type": "string",
                        "description": "Feature name from fusion_get_features. Use either feature_index or feature_name."
                    },
                    "suppress": {
                        "type": "boolean",
                        "description": "True to suppress, false to unsuppress (default: true)",
                        "default": True
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_edit_feature",
            description="Edit feature parameters (distance, angle, radius, etc). Supports Extrude, Revolve, Fillet, and Chamfer features. CAUTION: May affect downstream features.",
            inputSchema={
                "type": "object",
                "properties": {
                    "component_path": {
                        "type": "string",
                        "description": "Path to component (default: 'root')",
                        "default": "root"
                    },
                    "feature_index": {
                        "type": "integer",
                        "description": "Feature index from fusion_get_features"
                    },
                    "feature_name": {
                        "type": "string",
                        "description": "Feature name from fusion_get_features"
                    },
                    "edits": {
                        "type": "object",
                        "description": "Parameters to edit. Available parameters depend on feature type.",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "New feature name (works for all features)"
                            },
                            "distance": {
                                "type": "number",
                                "description": "Extrude distance or Chamfer distance in cm"
                            },
                            "taper_angle": {
                                "type": "number",
                                "description": "Extrude taper angle in radians"
                            },
                            "angle": {
                                "type": "number",
                                "description": "Revolve angle in radians"
                            },
                            "radius": {
                                "type": "number",
                                "description": "Fillet radius in cm"
                            }
                        }
                    }
                },
                "required": ["edits"]
            }
        ),
        types.Tool(
            name="fusion_highlight_geometry",
            description="Highlight specific geometry elements in the viewport by adding them to the selection. Useful for debugging and visualization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "description": "Array of element paths to highlight. Paths from fusion_get_tree, fusion_get_edge_info, etc. Can also be a single path string.",
                        "items": {
                            "type": "string"
                        }
                    },
                    "clear_selection": {
                        "type": "boolean",
                        "description": "Whether to clear existing selection before highlighting (default: true)",
                        "default": True
                    }
                },
                "required": ["paths"]
            }
        ),
        types.Tool(
            name="fusion_measure_all_angles",
            description="Measure all angles between edges or faces in a body. Returns array of angle measurements with optional filtering by angle range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "body_path": {
                        "type": "string",
                        "description": "Path to body. Format: 'root/bRepBodies/BodyName'"
                    },
                    "mode": {
                        "type": "string",
                        "description": "Measurement mode: 'edges' for angles between connected edges, 'faces' for angles between adjacent faces",
                        "enum": ["edges", "faces"],
                        "default": "edges"
                    },
                    "min_angle": {
                        "type": "number",
                        "description": "Minimum angle to include in results (degrees, default: 0)",
                        "default": 0
                    },
                    "max_angle": {
                        "type": "number",
                        "description": "Maximum angle to include in results (degrees, default: 180)",
                        "default": 180
                    }
                },
                "required": ["body_path"]
            }
        ),
        types.Tool(
            name="fusion_get_edge_relationships",
            description="Get topology relationships for a specific edge: connected edges at vertices, adjacent faces, curve type, and geometric properties.",
            inputSchema={
                "type": "object",
                "properties": {
                    "edge_path": {
                        "type": "string",
                        "description": "Path to edge. Format: 'root/bRepBodies/BodyName/edges/INDEX'"
                    }
                },
                "required": ["edge_path"]
            }
        ),
        # Server configuration tools
        types.Tool(
            name="fusion_set_server",
            description="Set the Fusion 360 server address to connect to. Use IP address for remote computers, or friendly names like 'this computer', 'local', 'my computer' for localhost.",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {
                        "type": "string",
                        "description": "Server address (IP like '192.168.1.50') or friendly name ('this computer', 'local', 'my computer', 'here')"
                    }
                },
                "required": ["server"]
            }
        ),
        types.Tool(
            name="fusion_get_server",
            description="Get the current Fusion 360 server address being used.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="fusion_set_design_type",
            description="Switch between Parametric and Direct design modes. Direct mode is faster for batch geometry creation. Parametric mode maintains feature history and supports parameters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["parametric", "direct"],
                        "description": "Design mode: 'parametric' (feature history, parameters) or 'direct' (no history, faster)"
                    }
                },
                "required": ["mode"]
            }
        ),
        types.Tool(
            name="fusion_create_joint",
            description="Create a joint between two components. Snaps geometry_one to geometry_two. Supports all 7 motion types: rigid, revolute, slider, cylindrical, ball, planar, pin_slot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "geometry_one": {
                        "type": "object",
                        "description": "First joint geometry (component that moves to snap)",
                        "properties": {
                            "entity_path": {
                                "type": "string",
                                "description": "Path to entity: 'root/bodies/Body1/faces/0', 'root/children/Comp:1/bodies/Body1/edges/3', 'root/bodies/Body1/vertices/0', or 'origin'"
                            },
                            "key_point": {
                                "type": "string",
                                "enum": ["center", "start", "middle", "end"],
                                "description": "Key point on entity (default: center). For faces: center of face. For edges: start/middle/end point. For cylinders: start/middle/end along axis.",
                                "default": "center"
                            }
                        },
                        "required": ["entity_path"]
                    },
                    "geometry_two": {
                        "type": "object",
                        "description": "Second joint geometry (stationary reference)",
                        "properties": {
                            "entity_path": {
                                "type": "string",
                                "description": "Path to entity (same format as geometry_one)"
                            },
                            "key_point": {
                                "type": "string",
                                "enum": ["center", "start", "middle", "end"],
                                "description": "Key point on entity",
                                "default": "center"
                            }
                        },
                        "required": ["entity_path"]
                    },
                    "motion_type": {
                        "type": "string",
                        "enum": ["rigid", "revolute", "slider", "cylindrical", "ball", "planar", "pin_slot"],
                        "description": "Joint motion type. rigid=0 DOF, revolute=1 rotation, slider=1 translation, cylindrical=rotation+translation same axis, ball=3 rotations, planar=2 translations+1 rotation, pin_slot=rotation+translation different axes",
                        "default": "rigid"
                    },
                    "axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Rotation axis for revolute/cylindrical/pin_slot (default: z)",
                        "default": "z"
                    },
                    "slide_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Slide direction for slider/pin_slot (default: x)",
                        "default": "x"
                    },
                    "normal_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Normal direction for planar joints (default: y)",
                        "default": "y"
                    },
                    "pitch_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Pitch axis for ball joints (default: z)",
                        "default": "z"
                    },
                    "yaw_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Yaw axis for ball joints (default: x)",
                        "default": "x"
                    },
                    "offset": {
                        "type": "number",
                        "description": "Offset distance between geometries in cm"
                    },
                    "angle": {
                        "type": "number",
                        "description": "Angle between geometries in degrees"
                    },
                    "is_flipped": {
                        "type": "boolean",
                        "description": "Flip joint direction",
                        "default": False
                    },
                    "name": {
                        "type": "string",
                        "description": "Joint display name"
                    }
                },
                "required": ["geometry_one", "geometry_two"]
            }
        ),
        types.Tool(
            name="fusion_create_as_built_joint",
            description="Create an as-built joint between two occurrences that are already positioned correctly. Unlike regular joints, as-built joints do NOT move components. Use 'root' as occurrence_two to ground a component to the root.",
            inputSchema={
                "type": "object",
                "properties": {
                    "occurrence_one": {
                        "type": "string",
                        "description": "Path to first occurrence: 'root/children/CompName:1' or 'root/occurrences/CompName:1'"
                    },
                    "occurrence_two": {
                        "type": "string",
                        "description": "Path to second occurrence, or 'root'/'null'/'ground' to ground the component to the root component"
                    },
                    "geometry": {
                        "type": "object",
                        "description": "Optional geometry reference for joint position",
                        "properties": {
                            "entity_path": {
                                "type": "string",
                                "description": "Path to face/edge/vertex for joint position"
                            },
                            "key_point": {
                                "type": "string",
                                "enum": ["center", "start", "middle", "end"],
                                "default": "center"
                            }
                        },
                        "required": ["entity_path"]
                    },
                    "motion_type": {
                        "type": "string",
                        "enum": ["rigid", "revolute", "slider", "cylindrical", "ball", "planar", "pin_slot"],
                        "description": "Joint motion type (default: rigid)",
                        "default": "rigid"
                    },
                    "axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Rotation axis (default: z)",
                        "default": "z"
                    },
                    "slide_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Slide direction (default: x)",
                        "default": "x"
                    },
                    "normal_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "default": "y"
                    },
                    "pitch_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "default": "z"
                    },
                    "yaw_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "default": "x"
                    },
                    "name": {
                        "type": "string",
                        "description": "Joint display name"
                    }
                },
                "required": ["occurrence_one", "occurrence_two"]
            }
        ),
        types.Tool(
            name="fusion_drive_joint",
            description="Drive a joint to specific position values. Set rotation (degrees), slide (cm), pitch/yaw/roll (degrees) depending on joint type. Optionally animate with steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_name": {
                        "type": "string",
                        "description": "Name of the joint to drive"
                    },
                    "rotation": {
                        "type": "number",
                        "description": "Target rotation in degrees (revolute, cylindrical, pin_slot, planar)"
                    },
                    "slide": {
                        "type": "number",
                        "description": "Target slide distance in cm (slider, cylindrical, pin_slot)"
                    },
                    "primary_slide": {
                        "type": "number",
                        "description": "Primary slide in cm (planar joints)"
                    },
                    "secondary_slide": {
                        "type": "number",
                        "description": "Secondary slide in cm (planar joints)"
                    },
                    "pitch": {
                        "type": "number",
                        "description": "Pitch angle in degrees (ball joints)"
                    },
                    "yaw": {
                        "type": "number",
                        "description": "Yaw angle in degrees (ball joints)"
                    },
                    "roll": {
                        "type": "number",
                        "description": "Roll angle in degrees (ball joints)"
                    },
                    "animate_steps": {
                        "type": "integer",
                        "description": "Number of animation steps (0 = instant, >0 = smooth animation with viewport updates)",
                        "default": 0
                    }
                },
                "required": ["joint_name"]
            }
        ),
        types.Tool(
            name="fusion_set_joint_limits",
            description="Set min/max/rest limits on a joint's degree of freedom. Rotation limits in degrees, slide limits in cm.",
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_name": {
                        "type": "string",
                        "description": "Name of the joint"
                    },
                    "dof": {
                        "type": "string",
                        "enum": ["rotation", "slide", "pitch", "yaw", "roll", "primary_slide", "secondary_slide"],
                        "description": "Which degree of freedom to set limits on. Depends on joint type: revolute=rotation, slider=slide, cylindrical=rotation|slide, ball=pitch|yaw|roll, planar=rotation|primary_slide|secondary_slide, pin_slot=rotation|slide"
                    },
                    "min_enabled": {
                        "type": "boolean",
                        "description": "Enable minimum limit"
                    },
                    "min_value": {
                        "type": "number",
                        "description": "Minimum value (degrees for rotation, cm for slide). Automatically enables min_enabled."
                    },
                    "max_enabled": {
                        "type": "boolean",
                        "description": "Enable maximum limit"
                    },
                    "max_value": {
                        "type": "number",
                        "description": "Maximum value (degrees for rotation, cm for slide). Automatically enables max_enabled."
                    },
                    "rest_enabled": {
                        "type": "boolean",
                        "description": "Enable rest/home position"
                    },
                    "rest_value": {
                        "type": "number",
                        "description": "Rest/home value (degrees or cm). Automatically enables rest_enabled."
                    }
                },
                "required": ["joint_name", "dof"]
            }
        ),
        types.Tool(
            name="fusion_modify_joint",
            description="Modify joint properties: lock/unlock, suppress/unsuppress, rename, flip, or change motion type. Works on both regular joints and as-built joints.",
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_name": {
                        "type": "string",
                        "description": "Name of the joint to modify"
                    },
                    "is_locked": {
                        "type": "boolean",
                        "description": "Lock (true) or unlock (false) the joint"
                    },
                    "is_suppressed": {
                        "type": "boolean",
                        "description": "Suppress (true) or unsuppress (false) the joint"
                    },
                    "new_name": {
                        "type": "string",
                        "description": "New display name for the joint"
                    },
                    "is_flipped": {
                        "type": "boolean",
                        "description": "Flip joint direction"
                    },
                    "motion_type": {
                        "type": "string",
                        "enum": ["rigid", "revolute", "slider", "cylindrical", "ball", "planar", "pin_slot"],
                        "description": "Change the motion type of the joint"
                    },
                    "axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Rotation axis when changing motion type",
                        "default": "z"
                    },
                    "slide_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Slide axis when changing motion type",
                        "default": "x"
                    },
                    "normal_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "default": "y"
                    },
                    "pitch_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "default": "z"
                    },
                    "yaw_axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "default": "x"
                    }
                },
                "required": ["joint_name"]
            }
        ),
        types.Tool(
            name="fusion_create_joint_origin",
            description="Create a reusable joint origin point on a component. Joint origins define persistent connection points with optional offsets and angle for use in joint creation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "geometry": {
                        "type": "object",
                        "description": "Geometry defining the joint origin location",
                        "properties": {
                            "entity_path": {
                                "type": "string",
                                "description": "Path to face/edge/vertex: 'root/bodies/Body1/faces/0'"
                            },
                            "key_point": {
                                "type": "string",
                                "enum": ["center", "start", "middle", "end"],
                                "default": "center"
                            }
                        },
                        "required": ["entity_path"]
                    },
                    "component_path": {
                        "type": "string",
                        "description": "Path to component (default: 'root'). Use 'root/children/CompName:1' for sub-components.",
                        "default": "root"
                    },
                    "offset_x": {
                        "type": "number",
                        "description": "X offset in cm"
                    },
                    "offset_y": {
                        "type": "number",
                        "description": "Y offset in cm"
                    },
                    "offset_z": {
                        "type": "number",
                        "description": "Z offset in cm"
                    },
                    "angle": {
                        "type": "number",
                        "description": "Angle offset in degrees"
                    },
                    "is_flipped": {
                        "type": "boolean",
                        "description": "Flip the joint origin direction",
                        "default": False
                    },
                    "name": {
                        "type": "string",
                        "description": "Display name for the joint origin"
                    }
                },
                "required": ["geometry"]
            }
        ),
        types.Tool(
            name="fusion_create_rigid_group",
            description="Create a rigid group that locks multiple occurrences together so they move as one unit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "occurrence_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of occurrence paths: ['root/children/Comp1:1', 'root/children/Comp2:1']"
                    },
                    "include_children": {
                        "type": "boolean",
                        "description": "Include child components in the rigid group",
                        "default": False
                    },
                    "name": {
                        "type": "string",
                        "description": "Display name for the rigid group"
                    }
                },
                "required": ["occurrence_paths"]
            }
        ),
        types.Tool(
            name="fusion_create_motion_link",
            description="Create a motion link to synchronize motion between two joints. Maps a value range on joint_one to a value range on joint_two (e.g., '360 deg' rotation = '10 cm' slide).",
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_one": {
                        "type": "string",
                        "description": "Name of the first joint"
                    },
                    "joint_two": {
                        "type": "string",
                        "description": "Name of the second joint. Omit to link two DOFs within joint_one (for multi-DOF joints like cylindrical, ball, planar, pin_slot)."
                    },
                    "value_one": {
                        "type": "string",
                        "description": "Motion range for joint_one as string with units, e.g. '360 deg', '10 cm'"
                    },
                    "value_two": {
                        "type": "string",
                        "description": "Motion range for joint_two as string with units, e.g. '360 deg', '10 cm'"
                    },
                    "is_reversed": {
                        "type": "boolean",
                        "description": "Reverse the motion direction",
                        "default": False
                    },
                    "name": {
                        "type": "string",
                        "description": "Display name for the motion link"
                    }
                },
                "required": ["joint_one"]
            }
        ),
        types.Tool(
            name="fusion_delete_joint",
            description="Delete a joint or as-built joint by name. Removes the joint and its motion relationship between components.",
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_name": {
                        "type": "string",
                        "description": "Name of the joint to delete"
                    }
                },
                "required": ["joint_name"]
            }
        ),
        types.Tool(
            name="fusion_delete_feature",
            description="Delete a feature, joint, rigid group, or other design element. Use for removing broken joints, unwanted features, or cleaning up the design.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the element to delete (for features, joints, rigid groups)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to element (e.g., 'root/bodies/Body1'). Alternative to name."
                    },
                    "type": {
                        "type": "string",
                        "enum": ["feature", "joint", "rigid_group"],
                        "description": "Type of element to delete (default: feature). Use 'joint' for joints/as-built joints, 'rigid_group' for rigid groups, 'feature' for timeline features.",
                        "default": "feature"
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_get_design_type",
            description="Get the current design type (Parametric or Direct). Returns whether timeline and parameters are available.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="fusion_get_joint_details",
            description="Get detailed information about a single joint: axis direction, geometry origins, key points, health state, error messages, angle/offset parameters, timeline index. More detailed than get_tree.",
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_name": {
                        "type": "string",
                        "description": "Name of the joint to inspect"
                    }
                },
                "required": ["joint_name"]
            }
        ),
        types.Tool(
            name="fusion_get_grounding_state",
            description="Query grounding state of occurrences without fetching the full design tree. Lightweight check for diagnostics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "occurrence_path": {
                        "type": "string",
                        "description": "Path to a specific occurrence (e.g., 'root/children/Comp:1'). Omit to query all top-level occurrences."
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_undo",
            description="Undo the last operation in Fusion 360. Useful as a safety net when a joint creation moves geometry unexpectedly or an operation produces unwanted results.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="fusion_delete_occurrence",
            description="Delete an occurrence (component instance) from the design. Removes the occurrence and all its geometry from the assembly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "occurrence_path": {
                        "type": "string",
                        "description": "Path to occurrence: 'root/children/CompName:1' or 'root/occurrences/CompName:1'"
                    }
                },
                "required": ["occurrence_path"]
            }
        ),
        types.Tool(
            name="fusion_move_occurrence",
            description="Move an occurrence by a relative vector or to an absolute position. Works directly on the occurrence transform — no feature created. Calls design.snapshots.add() to finalize in Direct mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "occurrence_path": {
                        "type": "string",
                        "description": "Path to occurrence"
                    },
                    "vector": {
                        "type": "object",
                        "description": "Relative translation vector in cm",
                        "properties": {
                            "x": {"type": "number", "default": 0},
                            "y": {"type": "number", "default": 0},
                            "z": {"type": "number", "default": 0}
                        }
                    },
                    "position": {
                        "type": "object",
                        "description": "Absolute position in cm (alternative to vector)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        },
                        "required": ["x", "y", "z"]
                    }
                },
                "required": ["occurrence_path"]
            }
        ),
        types.Tool(
            name="fusion_rotate_occurrence",
            description="Rotate an occurrence around an axis. Composes with existing transform.",
            inputSchema={
                "type": "object",
                "properties": {
                    "occurrence_path": {
                        "type": "string",
                        "description": "Path to occurrence"
                    },
                    "angle": {
                        "type": "number",
                        "description": "Rotation angle in degrees"
                    },
                    "axis": {
                        "type": "string",
                        "enum": ["x", "y", "z"],
                        "description": "Rotation axis (default: z). For custom axis, use 'direction' parameter instead.",
                        "default": "z"
                    },
                    "direction": {
                        "type": "object",
                        "description": "Custom rotation axis direction vector (overrides 'axis')",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        }
                    },
                    "origin": {
                        "type": "object",
                        "description": "Rotation center point in cm (default: 0,0,0)",
                        "properties": {
                            "x": {"type": "number", "default": 0},
                            "y": {"type": "number", "default": 0},
                            "z": {"type": "number", "default": 0}
                        }
                    }
                },
                "required": ["occurrence_path", "angle"]
            }
        ),
        types.Tool(
            name="fusion_set_occurrence_transform",
            description="Set the full transform matrix on an occurrence. Can set absolute position, full 4x4 matrix, or reset to identity (origin).",
            inputSchema={
                "type": "object",
                "properties": {
                    "occurrence_path": {
                        "type": "string",
                        "description": "Path to occurrence"
                    },
                    "translation": {
                        "type": "object",
                        "description": "Set position directly (resets rotation to identity)",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        },
                        "required": ["x", "y", "z"]
                    },
                    "matrix": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Full 4x4 transform matrix as 16 floats (row-major order)"
                    },
                    "reset": {
                        "type": "boolean",
                        "description": "Reset transform to identity (moves occurrence to origin)",
                        "default": false
                    }
                },
                "required": ["occurrence_path"]
            }
        ),
        types.Tool(
            name="fusion_create_component",
            description="Create a new empty component in the root assembly. Returns the occurrence path for use in other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the new component"
                    },
                    "position": {
                        "type": "object",
                        "description": "Initial position in cm (default: origin)",
                        "properties": {
                            "x": {"type": "number", "default": 0},
                            "y": {"type": "number", "default": 0},
                            "z": {"type": "number", "default": 0}
                        }
                    }
                }
            }
        ),
        types.Tool(
            name="fusion_copy_occurrence",
            description="Copy an occurrence — creates a new instance of the same component. Useful for creating patterns or duplicating parts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Path to the occurrence to copy"
                    },
                    "position": {
                        "type": "object",
                        "description": "Absolute position for the copy in cm",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                        },
                        "required": ["x", "y", "z"]
                    },
                    "offset": {
                        "type": "object",
                        "description": "Offset from original position (alternative to position)",
                        "properties": {
                            "x": {"type": "number", "default": 0},
                            "y": {"type": "number", "default": 0},
                            "z": {"type": "number", "default": 0}
                        }
                    }
                },
                "required": ["source_path"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution"""

    # Handle server configuration tools locally (no Fusion connection needed)
    if name == "fusion_set_server":
        server_input = arguments.get("server", "localhost")
        new_server = set_fusion_server(server_input)
        is_local = is_local_server()
        location = "this computer" if is_local else f"remote server at {new_server}"
        return [types.TextContent(
            type="text",
            text=f"Fusion 360 server set to: {new_server} ({location})\nFull URL: {get_fusion_url()}"
        )]

    if name == "fusion_get_server":
        is_local = is_local_server()
        location = "this computer" if is_local else "remote server"
        return [types.TextContent(
            type="text",
            text=f"Current Fusion 360 server: {_fusion_server} ({location})\nFull URL: {get_fusion_url()}"
        )]

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
        'fusion_mirror_body': 'mirror_body',
        'fusion_split_body': 'split_body',
        'fusion_boolean_operation': 'boolean_operation',
        'fusion_create_sketch': 'create_sketch',
        'fusion_sketch_add_line': 'sketch_add_line',
        'fusion_sketch_add_circle': 'sketch_add_circle',
        'fusion_sketch_add_arc': 'sketch_add_arc',
        'fusion_sketch_add_rectangle': 'sketch_add_rectangle',
        'fusion_sketch_add_point': 'sketch_add_point',
        'fusion_sketch_add_constraint': 'sketch_add_constraint',
        'fusion_sketch_add_dimension': 'sketch_add_dimension',
        'fusion_get_features': 'get_features',
        'fusion_suppress_feature': 'suppress_feature',
        'fusion_edit_feature': 'edit_feature',
        'fusion_highlight_geometry': 'highlight_geometry',
        'fusion_measure_all_angles': 'measure_all_angles',
        'fusion_get_edge_relationships': 'get_edge_relationships',
        'fusion_create_extrude': 'create_extrude',
        'fusion_set_design_type': 'set_design_type',
        'fusion_create_joint': 'create_joint',
        'fusion_create_as_built_joint': 'create_as_built_joint',
        'fusion_drive_joint': 'drive_joint',
        'fusion_set_joint_limits': 'set_joint_limits',
        'fusion_modify_joint': 'modify_joint',
        'fusion_create_joint_origin': 'create_joint_origin',
        'fusion_create_rigid_group': 'create_rigid_group',
        'fusion_create_motion_link': 'create_motion_link',
        'fusion_delete_joint': 'delete_joint',
        'fusion_delete_feature': 'delete_feature',
        'fusion_get_design_type': 'get_design_type',
        'fusion_get_joint_details': 'get_joint_details',
        'fusion_get_grounding_state': 'get_grounding_state',
        'fusion_undo': 'undo',
        'fusion_delete_occurrence': 'delete_occurrence',
        'fusion_move_occurrence': 'move_occurrence',
        'fusion_rotate_occurrence': 'rotate_occurrence',
        'fusion_set_occurrence_transform': 'set_occurrence_transform',
        'fusion_create_component': 'create_component',
        'fusion_copy_occurrence': 'copy_occurrence'
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
            get_fusion_url(),
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
            text=f"Error: Cannot connect to Fusion 360 at {get_fusion_url()}. Make sure the HTTP Add-In is running on that machine."
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
                server_version="0.12.4",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
