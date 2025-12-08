#!/usr/bin/env python3
"""
Test script to verify MCP server tool registration
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the server module
import fusion_mcp_server

async def test_tools():
    """Test what tools are registered"""
    print("=" * 60)
    print("MCP Server Tool Registration Test")
    print("=" * 60)

    # Get the tools list
    tools = await fusion_mcp_server.handle_list_tools()

    print(f"\nTotal tools registered: {len(tools)}")
    print("\nTool List:")
    print("-" * 60)

    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool.name}")
        print(f"   Description: {tool.description[:80]}...")
        print()

    print("=" * 60)
    print(f"\nExpected: 27 tools")
    print(f"Found: {len(tools)} tools")

    if len(tools) == 27:
        print("✅ SUCCESS: All 27 tools registered correctly")
    else:
        print(f"❌ ERROR: Expected 27 tools but found {len(tools)}")
        print("\nExpected tools:")
        expected = [
            "execute_fusion_script",
            "fusion_screenshot",
            "fusion_get_camera",
            "fusion_set_camera",
            "fusion_get_tree",
            "fusion_set_element_properties",
            "fusion_measure_distance",
            "fusion_measure_angle",
            "fusion_get_edge_info",
            "fusion_get_face_info",
            "fusion_find_edges_by_criteria",
            "fusion_find_faces_by_criteria",
            "fusion_create_plane",
            "fusion_create_axis",
            "fusion_move_body",
            "fusion_rotate_body",
            "fusion_mirror_body",
            "fusion_split_body",
            "fusion_boolean_operation",
            "fusion_create_sketch",
            "fusion_sketch_add_line",
            "fusion_sketch_add_circle",
            "fusion_sketch_add_arc",
            "fusion_sketch_add_rectangle",
            "fusion_sketch_add_point",
            "fusion_sketch_add_constraint",
            "fusion_sketch_add_dimension"
        ]
        actual = [t.name for t in tools]
        for exp in expected:
            if exp in actual:
                print(f"  ✅ {exp}")
            else:
                print(f"  ❌ {exp} (MISSING)")

    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_tools())
