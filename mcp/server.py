"""FastMCP server exposing OpenRouteService trip planning tools."""
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _bootstrap_imports() -> None:
    """Make the installed `mcp` package importable before local helpers."""
    removed_entries: list[str] = []
    for entry in list(sys.path):
        try:
            resolved = Path(entry or os.getcwd()).resolve()
        except Exception:
            continue
        if resolved in {PROJECT_ROOT, Path(__file__).resolve().parent}:
            sys.path.remove(entry)
            removed_entries.append(entry)

    from mcp.server import FastMCP  # type: ignore

    for entry in reversed(removed_entries):
        sys.path.insert(0, entry)

    globals()["FastMCP"] = FastMCP


_bootstrap_imports()

_ors_import_error: str | None = None
try:
    from openrouteservice_mcp import fill_arrival_times  # type: ignore
except Exception as exc:  # pragma: no cover - defensive
    fill_arrival_times = None  # type: ignore
    _ors_import_error = str(exc)


def _load_env_file(path: str) -> None:
    """Load simple KEY=VALUE lines from a file into os.environ if not already set."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and not os.getenv(key):
                os.environ[key] = value


if not os.getenv("ORS_API_KEY"):
    _load_env_file(str(PROJECT_ROOT / ".env"))
    _load_env_file(str(PROJECT_ROOT / "config.example.env"))


mcp = FastMCP("openrouteservice-server")


@mcp.tool(
    name="fill_trip_arrival_times",
    description="Estimate arrival times using OpenRouteService and fill Time_arrival for each trip.",
)
def fill_trip_arrival_times(proposals: dict[str, Any]) -> dict[str, Any]:
    """Attempt to enrich proposals; return a clear error if ORS helper is unavailable."""
    api_key = os.getenv("ORS_API_KEY")
    if not api_key:
        return {"error": "ORS_API_KEY not set", "proposals": proposals}

    if _ors_import_error or fill_arrival_times is None:
        return {"error": f"openrouteservice helper unavailable: {_ors_import_error}", "proposals": proposals}

    try:
        enriched = fill_arrival_times(proposals, api_key=api_key)
        return {"proposals": enriched}
    except Exception as exc:
        return {"error": str(exc), "proposals": proposals}


if __name__ == "__main__":
    print("MCP server starting", file=sys.stderr, flush=True)
    mcp.run(transport="stdio")
