"""FastMCP server exposing OpenRouteService trip planning tools."""
import os
import sys
from copy import deepcopy
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FastMCP: Any = None


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
FastMCP = globals()["FastMCP"]

_ors_import_error: str | None = None
try:
    from openrouteservice_mcp import fill_arrival_times  # type: ignore
except Exception as exc:  # pragma: no cover - defensive
    fill_arrival_times = None  # type: ignore
    _ors_import_error = str(exc)


def fill_arrival_times_fallback(proposals: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Simple fallback implementation that queries OpenRouteService directly
    to estimate travel duration and fills `time_arrival` for each trip.

    This supports basic `HH:MM` or ISO-like time strings for `time_leave`.
    """
    if not api_key:
        raise RuntimeError("ORS API key required for fallback")

    enriched = deepcopy(proposals)
    records = _iter_trip_records(enriched)
    if not records:
        return enriched

    def _parse_time(t: str) -> datetime | None:
        if not isinstance(t, str):
            return None
        candidates = ["%H:%M", "%H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"]
        for fmt in candidates:
            try:
                return datetime.strptime(t, fmt)
            except Exception:
                continue
        # try splitting off date if combined
        if "T" in t or " " in t:
            tail = t.split("T")[-1].split(" ")[-1]
            for fmt in ["%H:%M", "%H:%M:%S"]:
                try:
                    dt = datetime.strptime(tail, fmt)
                    # attach today's date
                    now = datetime.now()
                    return datetime(now.year, now.month, now.day, dt.hour, dt.minute, dt.second)
                except Exception:
                    continue
        return None

    for key, trip in records:
        origin = trip.get("from") or trip.get("origin")
        destination = trip.get("to") or trip.get("destination")
        if not origin or not destination:
            continue

        origin_match = _geocode_location(str(origin), api_key)
        destination_match = _geocode_location(str(destination), api_key)
        if not origin_match or not destination_match:
            continue

        try:
            response = requests.post(
                "https://api.openrouteservice.org/v2/directions/driving-car",
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                json={"coordinates": [[origin_match["lon"], origin_match["lat"]], [destination_match["lon"], destination_match["lat"]]]},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            routes = payload.get("routes") or []
            duration_s = None
            if routes:
                summary = routes[0].get("summary", {})
                duration_s = summary.get("duration")
            if duration_s is None:
                # fallback to great-circle estimate (very rough)
                distance_km = _haversine_distance_km((origin_match["lat"], origin_match["lon"]), (destination_match["lat"], destination_match["lon"]))
                # assume average speed 60 km/h
                duration_s = (distance_km / 60.0) * 3600.0

            # compute arrival time if time_leave present
            time_leave = trip.get("time_leave") or trip.get("time_start") or trip.get("Time_leave")
            leave_dt = _parse_time(time_leave) if time_leave else None
            if leave_dt is not None:
                arrival_dt = leave_dt + timedelta(seconds=int(duration_s))
                # preserve date if present, otherwise return HH:MM
                if any(c in str(time_leave) for c in ("T", "-")):
                    trip["time_arrival"] = arrival_dt.isoformat(sep="T", timespec="seconds")
                else:
                    trip["time_arrival"] = arrival_dt.strftime("%H:%M")
            else:
                # store duration if cannot compute arrival
                trip["travel_duration_s"] = int(duration_s)
        except Exception:
            # don't raise; leave trip as-is
            continue

    return enriched


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


mcp = FastMCP("openrouteservice-server")
print("FastMCP instance created", file=sys.stderr, flush=True)


def _iter_trip_records(proposals: Any) -> list[tuple[Any, dict[str, Any]]]:
    """Return proposal keys and their trip dictionaries."""
    if isinstance(proposals, dict):
        if isinstance(proposals.get("proposal"), dict):
            proposals = proposals["proposal"]
        if all(isinstance(value, dict) for value in proposals.values()):
            ordered_keys = sorted(proposals.keys(), key=lambda key: int(key) if str(key).isdigit() else str(key))
            return [(key, proposals[key]) for key in ordered_keys]
    if isinstance(proposals, list):
        return list(enumerate(proposals))
    return []


def _haversine_distance_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius_km = 6371.0
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    a = sin(delta_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lon / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))


def _geocode_location(query: str, api_key: str) -> dict[str, Any] | None:
    response = requests.get(
        "https://api.openrouteservice.org/geocode/search",
        params={"api_key": api_key, "text": query, "size": 1},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features") or []
    if not features:
        return None
    feature = features[0]
    coordinates = feature.get("geometry", {}).get("coordinates") or []
    if len(coordinates) < 2:
        return None
    return {
        "lon": float(coordinates[0]),
        "lat": float(coordinates[1]),
        "label": feature.get("properties", {}).get("label", query),
    }


def _route_distance_km(origin: str, destination: str, api_key: str) -> tuple[float | None, str, dict[str, Any]]:
    origin_match = _geocode_location(origin, api_key)
    destination_match = _geocode_location(destination, api_key)
    if not origin_match or not destination_match:
        return None, "geocode_failed", {"origin": origin_match, "destination": destination_match}

    try:
        response = requests.post(
            "https://api.openrouteservice.org/v2/directions/driving-car",
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json={"coordinates": [[origin_match["lon"], origin_match["lat"]], [destination_match["lon"], destination_match["lat"]]]},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes") or []
        if routes:
            summary = routes[0].get("summary", {})
            distance_m = summary.get("distance")
            if distance_m is not None:
                return float(distance_m) / 1000.0, "ors_route", {"origin": origin_match, "destination": destination_match}
    except Exception:
        pass

    return (
        _haversine_distance_km((origin_match["lat"], origin_match["lon"]), (destination_match["lat"], destination_match["lon"])),
        "haversine",
        {"origin": origin_match, "destination": destination_match},
    )


@mcp.tool(
    name="fill_trip_arrival_times",
    description="Estimate arrival times using OpenRouteService and fill Time_arrival for each trip.",
)
def fill_trip_arrival_times(proposals: dict[str, Any]) -> dict[str, Any]:
    """Attempt to enrich proposals; return a clear error if ORS helper is unavailable."""
    api_key = os.getenv("ORS_API_KEY")
    if not api_key:
        return {"error": "ORS_API_KEY not set", "proposals": proposals}

    # Prefer the optional helper package when available; otherwise use
    # the built-in ORS-based fallback implemented above.
    if _ors_import_error or fill_arrival_times is None:
        try:
            enriched = fill_arrival_times_fallback(proposals, api_key=api_key)
            return {"proposals": enriched}
        except Exception as exc:
            return {"error": f"openrouteservice helper unavailable: {_ors_import_error}; fallback failed: {exc}", "proposals": proposals}

    try:
        enriched = fill_arrival_times(proposals, api_key=api_key)
        return {"proposals": enriched}
    except Exception as exc:
        # If the helper raises, attempt the fallback before failing
        try:
            enriched = fill_arrival_times_fallback(proposals, api_key=api_key)
            return {"proposals": enriched}
        except Exception:
            return {"error": str(exc), "proposals": proposals}


@mcp.tool(
    name="fill_trip_distances",
    description="Estimate trip distances using OpenRouteService and fill distance_km for each trip.",
)
def fill_trip_distances(proposals: dict[str, Any]) -> dict[str, Any]:
    """Estimate trip distances for each proposal entry."""
    api_key = os.getenv("ORS_API_KEY")
    if not api_key:
        return {"error": "ORS_API_KEY not set", "proposals": proposals}

    enriched = deepcopy(proposals)
    records = _iter_trip_records(enriched)
    if not records:
        return {"error": "No trip records found", "proposals": proposals}

    distance_errors: list[str] = []
    for key, trip in records:
        origin = trip.get("from") or trip.get("origin")
        destination = trip.get("to") or trip.get("destination")
        if not origin or not destination:
            distance_errors.append(f"{key}: missing origin or destination")
            continue

        try:
            distance_km, method, route_info = _route_distance_km(str(origin), str(destination), api_key)
        except Exception as exc:
            distance_errors.append(f"{key}: {exc}")
            continue

        if distance_km is None:
            distance_errors.append(f"{key}: unable to calculate distance")
            continue

        trip["distance_km"] = round(distance_km, 2)

    return {
        "proposals": enriched,
        "distance_errors": distance_errors,
    }


if __name__ == "__main__":
    try:
        import asyncio
        print("MCP server starting (SSE transport)", file=sys.stderr, flush=True)
        sys.stderr.flush()
        print(f"MCP object: {mcp}", file=sys.stderr, flush=True)
        print(f"About to call mcp.run_sse_async()...", file=sys.stderr, flush=True)
        sys.stderr.flush()
        # Run the MCP server with SSE (Server-Sent Events) transport
        # This is a request-response transport that should work better in subprocess context
        asyncio.run(mcp.run_sse_async())
        print(f"mcp.run_sse_async() completed", file=sys.stderr, flush=True)
        print("MCP server exited normally", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        print("MCP server interrupted", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Error running MCP server: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
