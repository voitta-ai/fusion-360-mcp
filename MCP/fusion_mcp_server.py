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
        'fusion_edit_feature': 'edit_feature'
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
                server_version="0.11.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
