"""OpenRouteService MCP: fill arrival times for trip proposals.

This module geocodes text locations using ORS Search API and calls ORS
Directions API to estimate travel duration (no live traffic). It fills
`Time_arrival` for proposals that have `date` and `Time_leave`.

Usage: call `fill_arrival_times(proposals, api_key=os.getenv('ORS_API_KEY'))`
"""
from typing import Any, Dict, Optional, Tuple
import requests
import datetime
import time


def _geocode(text: str, api_key: str) -> Optional[Tuple[float, float]]:
    """Return (lng, lat) for a free-form address using ORS Search API."""
    if not api_key:
        raise ValueError("ORS API key is required")

    url = "https://api.openrouteservice.org/geocode/search"
    params = {"api_key": api_key, "text": text, "size": 1}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    features = data.get("features") or []
    if not features:
        return None

    geom = features[0].get("geometry") or {}
    coords = geom.get("coordinates")
    if not coords or len(coords) < 2:
        return None

    # ORS returns [lon, lat]
    return float(coords[0]), float(coords[1])


def _call_directions(start: Tuple[float, float], end: Tuple[float, float], api_key: str, profile: str = "driving-car") -> Optional[int]:
    """Call ORS Directions API and return duration in seconds (no traffic)."""
    if not api_key:
        raise ValueError("ORS API key is required")

    url = f"https://api.openrouteservice.org/v2/directions/{profile}"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    body = {"coordinates": [[start[0], start[1]], [end[0], end[1]]], "units": "m"}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    routes = data.get("routes")
    if not routes:
        return None

    summary = routes[0].get("summary") or {}
    duration = summary.get("duration")
    if duration is None:
        return None

    return int(duration)


def _local_timestamp(date_str: str, time_str: str) -> int:
    dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return int(time.mktime(dt.timetuple()))


def fill_arrival_times(proposals: Dict[str, Any], api_key: str, profile: str = "driving-car") -> Dict[str, Any]:
    """Fill `Time_arrival` for each trip in `proposals` using ORS.

    The function will attempt to geocode `from` and `to` text fields. If
    geocoding or routing fails for a trip, `Time_arrival` remains None.
    """
    for k, trip in proposals.items():
        if not trip.get("Time_leave") or trip.get("Time_arrival"):
            continue

        date = trip.get("date")
        origin = trip.get("from")
        destination = trip.get("to")
        leave = trip.get("Time_leave")

        if not (date and origin and destination and leave):
            continue

        try:
            dep_ts = _local_timestamp(date, leave)
        except Exception:
            trip["Time_arrival"] = None
            continue

        # Geocode origin/destination
        start = _geocode(origin, api_key)
        end = _geocode(destination, api_key)
        if not start or not end:
            trip["Time_arrival"] = None
            continue

        dur = _call_directions(start, end, api_key, profile=profile)
        if dur is None:
            trip["Time_arrival"] = None
            continue

        arr_ts = dep_ts + dur
        arr_dt = datetime.datetime.fromtimestamp(arr_ts)
        trip["Time_arrival"] = arr_dt.strftime("%H:%M")

    return proposals
