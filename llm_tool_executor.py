"""Tool executor for LLM-based MCP tool invocation."""
from __future__ import annotations

import json
from typing import Any, Callable

from mcp.client.session import ClientSession  # type: ignore


AVAILABLE_TOOLS = {
    "fill_trip_distances": {
        "name": "fill_trip_distances",
        "description": "Estimate trip distances in kilometers from origin to destination using OpenRouteService. Required for charging calculations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposals": {
                    "type": "object",
                    "description": "Dictionary mapping trip IDs (e.g., '1', '2') to trip objects with 'from' and 'to' fields"
                }
            },
            "required": ["proposals"]
        }
    },
    "fill_trip_times": {
        "name": "fill_trip_times",
        "description": "Estimate trip travel time using OpenRouteService and fill whichever of Time_arrival or Time_leave is missing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposals": {
                    "type": "object",
                    "description": "Dictionary mapping trip IDs (e.g., '1', '2') to trip objects with 'from', 'to', and either 'Time_leave' or 'Time_arrival' fields"
                }
            },
            "required": ["proposals"]
        }
    }
}


def get_tools_prompt_section() -> str:
    """Return a prompt section describing available tools for the LLM."""
    tools_desc = []
    for tool_name, tool_spec in AVAILABLE_TOOLS.items():
        tools_desc.append(f"- {tool_name}: {tool_spec['description']}")
    
    return f"""
Available tools for enriching trips (optional):
You can call these tools to enrich the trip data with distances and arrival times:
{chr(10).join(tools_desc)}

If you want to call a tool, include it in your response JSON as a "tool_calls" array:
{{
  "status": "proposal",
  "proposal": {{ ... your trips ... }},
  "tool_calls": [
    {{
            "tool_name": "fill_trip_times",
            "arguments": {{"proposals": {{ "1": {{ "from": "Gent", "to": "Antwerp", "Time_leave": "08:00" }} }}}}
    }}
  ]
}}

The user will execute these tools and provide the enriched data back to you.
"""


def extract_tool_calls(llm_response: str) -> list[dict[str, Any]]:
    """Extract tool calls from LLM response JSON."""
    try:
        start = llm_response.find("{")
        end = llm_response.rfind("}") + 1
        if start == -1 or end <= start:
            return []
        
        parsed = json.loads(llm_response[start:end])
        tool_calls = parsed.get("tool_calls") or []
        if not isinstance(tool_calls, list):
            return []
        return [call for call in tool_calls if isinstance(call, dict) and "tool_name" in call and "arguments" in call]
    except Exception:
        return []


async def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    mcp_session: ClientSession | None,
) -> dict[str, Any]:
    """Execute tool calls via MCP and return results."""
    if not mcp_session:
        return {"status": "no_mcp_session", "tool_results": []}
    
    results: list[dict[str, Any]] = []
    for call in tool_calls:
        tool_name = call.get("tool_name")
        arguments = call.get("arguments") or {}
        
        if tool_name not in AVAILABLE_TOOLS:
            results.append({
                "tool_name": tool_name,
                "error": f"Unknown tool: {tool_name}"
            })
            continue
        
        try:
            tool_result = await _call_mcp_tool(mcp_session, tool_name, arguments)
            results.append({
                "tool_name": tool_name,
                "result": tool_result,
                "success": "error" not in str(tool_result).lower()
            })
        except Exception as exc:
            results.append({
                "tool_name": tool_name,
                "error": str(exc)
            })
    
    return {
        "status": "ok",
        "tool_results": results
    }


async def _call_mcp_tool(session: ClientSession, tool_name: str, arguments: dict) -> dict | None:
    """Call an MCP tool and return the result as a dict."""
    try:
        result = await session.call_tool(tool_name, arguments=arguments)
        if result.content:
            text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
            try:
                return json.loads(text)
            except Exception:
                return {"raw_result": text}
        return {}
    except Exception as exc:
        return {"error": str(exc)}


def format_tool_results_for_llm(tool_results: dict[str, Any]) -> str:
    """Format tool execution results into a prompt section for the LLM."""
    raw = tool_results.get("tool_results")
    if not raw:
        return ""

    # Normalize to a list of result dicts. Guard against callers passing a dict
    # (already a bundle) or accidentally passing the inner list/dict directly.
    if isinstance(raw, dict):
        results_list = [raw]
    elif isinstance(raw, list):
        results_list = raw
    else:
        # If it's a string or unexpected type, return a simple textual summary.
        return "Tool execution results:\n" + str(raw)

    lines = ["Tool execution results:"]
    for result in results_list:
        if not isinstance(result, dict):
            lines.append(f"- Unexpected tool result type: {type(result).__name__}")
            continue

        tool_name = result.get("tool_name")
        if result.get("error"):
            lines.append(f"- {tool_name}: ERROR - {result['error']}")
        else:
            lines.append(f"- {tool_name}: SUCCESS")
            if "proposals" in result.get("result", {}):
                proposals = result["result"]["proposals"]
                lines.append(f"  Enriched {len(proposals)} trips with the following fields:")
                for trip_id, trip in list(proposals.items())[:1]:
                    fields = [k for k in trip.keys() if k in ("distance_km", "Time_arrival", "Time_leave", "time_arrival", "time_leave", "distance_method", "travel_duration_s")]
                    if fields:
                        lines.append(f"    {', '.join(fields)}")

    return "\n".join(lines)
