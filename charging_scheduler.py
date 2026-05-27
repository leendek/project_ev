"""Deterministic charging scheduler for confirmed EV trips."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Mapping

from vehicle_config import (
    BATTERY_CAPACITY_KWH,
    CHARGER_POWER_KW,
    EFFICIENCY_KWH_100KM,
    HOME_LOCATION,
    MIN_SOC_PERCENT,
    START_SOC_PERCENT,
    TARGET_SOC_PERCENT,
)


DEFAULT_HOME_WINDOWS: list[tuple[str, str]] = [("22:00", "06:00")]


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _parse_clock_minutes(value: Any) -> int | None:
    if not value:
        return None
    try:
        hours_str, minutes_str = str(value).split(":", 1)
        return int(hours_str) * 60 + int(minutes_str)
    except (ValueError, TypeError):
        return None


def _minutes_to_clock(minutes: int) -> str:
    normalized = minutes % (24 * 60)
    return f"{normalized // 60:02d}:{normalized % 60:02d}"


def _window_bounds(start: str, end: str) -> tuple[int, int]:
    start_minutes = _parse_clock_minutes(start) or 0
    end_minutes = _parse_clock_minutes(end) or 0
    if end_minutes <= start_minutes:
        end_minutes += 24 * 60
    return start_minutes, end_minutes


def _trip_distance_km(trip: Mapping[str, Any]) -> float:
    for key in ("distance_km", "distance", "route_distance_km", "route_km"):
        value = trip.get(key)
        if value is None or value == "":
            continue
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return 0.0


def _trip_sort_key(trip: Mapping[str, Any]) -> tuple[str, str, str]:
    trip_date = str(trip.get("date") or "")
    leave_time = str(trip.get("Time_leave") or "99:99")
    title = str(trip.get("title") or trip.get("trip_title") or "")
    return trip_date, leave_time, title


def _group_trips_by_date(trips: list[Mapping[str, Any]]) -> dict[date, list[Mapping[str, Any]]]:
    grouped: dict[date, list[Mapping[str, Any]]] = defaultdict(list)
    for trip in trips:
        trip_date = _parse_date(trip.get("date"))
        if trip_date is None:
            continue
        grouped[trip_date].append(trip)
    for trip_list in grouped.values():
        trip_list.sort(key=_trip_sort_key)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def infer_home_windows_from_trips(trips_for_day: list[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """Infer when the car is at home on a given day from trip gaps."""
    if not trips_for_day:
        return [("00:00", "23:59")]

    ordered = sorted(trips_for_day, key=_trip_sort_key)
    windows: list[tuple[str, str]] = []

    first_leave = _parse_clock_minutes(ordered[0].get("Time_leave"))
    if first_leave is not None and first_leave > 0:
        windows.append(("00:00", _minutes_to_clock(first_leave)))

    for left_trip, right_trip in zip(ordered, ordered[1:]):
        left_arrival = _parse_clock_minutes(left_trip.get("Time_arrival"))
        right_leave = _parse_clock_minutes(right_trip.get("Time_leave"))
        if left_arrival is None or right_leave is None:
            continue
        if right_leave > left_arrival:
            windows.append((_minutes_to_clock(left_arrival), _minutes_to_clock(right_leave)))

    last_arrival = _parse_clock_minutes(ordered[-1].get("Time_arrival"))
    if last_arrival is not None and last_arrival < 24 * 60 - 1:
        windows.append((_minutes_to_clock(last_arrival), "23:59"))

    cleaned_windows = [(start, end) for start, end in windows if start != end]
    return cleaned_windows or list(DEFAULT_HOME_WINDOWS)


def _normalize_vehicle_profile(vehicle_profile: Mapping[str, Any] | None) -> dict[str, Any]:
    profile = dict(vehicle_profile or {})
    return {
        "battery_kwh": float(profile.get("battery_kwh", BATTERY_CAPACITY_KWH)),
        "efficiency_kwh_100km": float(profile.get("efficiency_kwh_100km", EFFICIENCY_KWH_100KM)),
        "charger_power_kw": float(profile.get("charger_power_kw", CHARGER_POWER_KW)),
        "min_soc_percent": int(profile.get("min_soc_percent", MIN_SOC_PERCENT)),
        "target_soc_percent": int(profile.get("target_soc_percent", TARGET_SOC_PERCENT)),
        "start_soc_percent": int(profile.get("start_soc_percent", START_SOC_PERCENT)),
        "home_location": str(profile.get("home_location", HOME_LOCATION)),
    }


def _allocate_charge_slots(
    required_kwh: float,
    available_windows: list[tuple[str, str]],
    charger_power_kw: float,
) -> list[dict[str, Any]]:
    remaining_kwh = max(0.0, required_kwh)
    if remaining_kwh <= 0.0 or charger_power_kw <= 0.0:
        return []

    ordered_windows = sorted(
        available_windows,
        key=lambda window: _window_bounds(window[0], window[1])[1],
        reverse=True,
    )

    slots: list[dict[str, Any]] = []
    for start, end in ordered_windows:
        window_start, window_end = _window_bounds(start, end)
        if window_end <= window_start:
            continue
        window_capacity_kwh = ((window_end - window_start) / 60.0) * charger_power_kw
        if window_capacity_kwh <= 0.0:
            continue

        allocated_kwh = min(remaining_kwh, window_capacity_kwh)
        allocated_minutes = max(1, int(round((allocated_kwh / charger_power_kw) * 60.0)))
        slot_end_abs = window_end
        slot_start_abs = max(window_start, slot_end_abs - allocated_minutes)

        slots.append(
            {
                "start": _minutes_to_clock(slot_start_abs),
                "end": _minutes_to_clock(slot_end_abs),
                "energy_kwh": round(allocated_kwh, 2),
                "charger_power_kw": round(charger_power_kw, 2),
                "location": "home",
            }
        )
        remaining_kwh -= allocated_kwh
        if remaining_kwh <= 0.01:
            break

    return slots


def compute_charging_plan(
    trips: list[dict[str, Any]],
    vehicle_profile: Mapping[str, Any] | None,
    charger_power_kw: float,
    home_availability: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic charging plan from confirmed trips.

    The first version keeps the policy simple:
    - infer daily home windows from the trip gaps unless explicit windows are provided
    - consume energy per trip using the configured efficiency
    - schedule the minimum overnight/home charge needed to stay above the minimum SOC
      before the next driving day, or to return to target SOC when feasible
    """

    resolved_profile = _normalize_vehicle_profile(vehicle_profile)
    resolved_profile["charger_power_kw"] = float(charger_power_kw or resolved_profile["charger_power_kw"])

    grouped_trips = _group_trips_by_date(trips)
    if not grouped_trips:
        return {
            "status": "empty",
            "vehicle_profile": resolved_profile,
            "daily_plans": [],
            "summary": {"trip_count": 0, "planned_charge_kwh": 0.0},
        }

    current_soc = float(resolved_profile["start_soc_percent"])
    daily_plans: list[dict[str, Any]] = []
    total_planned_charge_kwh = 0.0

    sorted_dates = list(grouped_trips.keys())
    for index, trip_day in enumerate(sorted_dates):
        trips_for_day = grouped_trips[trip_day]
        day_distance_km = sum(_trip_distance_km(trip) for trip in trips_for_day)
        day_energy_kwh = (day_distance_km * resolved_profile["efficiency_kwh_100km"]) / 100.0
        current_soc = max(0.0, current_soc - ((day_energy_kwh / resolved_profile["battery_kwh"]) * 100.0))

        next_day = sorted_dates[index + 1] if index + 1 < len(sorted_dates) else None
        next_day_trips = grouped_trips.get(next_day, []) if next_day else []
        next_day_energy_kwh = sum(_trip_distance_km(trip) for trip in next_day_trips) * resolved_profile["efficiency_kwh_100km"] / 100.0
        next_day_required_soc = resolved_profile["min_soc_percent"] + ((next_day_energy_kwh / resolved_profile["battery_kwh"]) * 100.0)

        target_soc = resolved_profile["target_soc_percent"]
        required_soc = current_soc
        charge_reason = "no charging needed"
        if next_day_trips:
            required_soc = min(100.0, max(target_soc, next_day_required_soc))
            if current_soc < required_soc:
                charge_reason = f"prepare for next trip day {next_day.isoformat()}"
        elif current_soc < target_soc:
            required_soc = target_soc
            charge_reason = "top up at home"

        charge_needed_kwh = max(0.0, ((required_soc - current_soc) / 100.0) * resolved_profile["battery_kwh"])
        available_windows = list(home_availability) if home_availability is not None else infer_home_windows_from_trips(trips_for_day)
        charge_slots = _allocate_charge_slots(charge_needed_kwh, available_windows, resolved_profile["charger_power_kw"])
        planned_charge_kwh = round(sum(slot["energy_kwh"] for slot in charge_slots), 2)
        total_planned_charge_kwh += planned_charge_kwh

        if planned_charge_kwh > 0.0:
            current_soc = min(100.0, current_soc + ((planned_charge_kwh / resolved_profile["battery_kwh"]) * 100.0))

        daily_plans.append(
            {
                "date": trip_day.isoformat(),
                "trip_count": len(trips_for_day),
                "trip_distance_km": round(day_distance_km, 2),
                "energy_used_kwh": round(day_energy_kwh, 2),
                "soc_after_trips_percent": round(max(0.0, current_soc - ((planned_charge_kwh / resolved_profile["battery_kwh"]) * 100.0)) if planned_charge_kwh > 0.0 else current_soc, 2),
                "required_soc_percent": round(required_soc, 2),
                "charge_needed_kwh": round(charge_needed_kwh, 2),
                "charging_slots": charge_slots,
                "home_windows": [
                    {"start": start, "end": end}
                    for start, end in available_windows
                ],
                "charge_reason": charge_reason,
                "trip_titles": [trip.get("title") or trip.get("trip_title") or "Trip" for trip in trips_for_day],
            }
        )

    return {
        "status": "ok",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "vehicle_profile": resolved_profile,
        "daily_plans": daily_plans,
        "summary": {
            "trip_count": sum(len(trips_for_day) for trips_for_day in grouped_trips.values()),
            "day_count": len(daily_plans),
            "planned_charge_kwh": round(total_planned_charge_kwh, 2),
        },
    }
