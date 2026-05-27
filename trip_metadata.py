"""Helpers for storing confirmed trip metadata."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping


def _extract_questions_from_assistant_turn(content: str) -> list[str]:
    if not content:
        return []
    try:
        parsed = json.loads(content)
    except Exception:
        return []
    questions = parsed.get("questions") if isinstance(parsed, dict) else None
    if not isinstance(questions, list):
        return []
    return [str(question).strip() for question in questions if str(question).strip()]


def extract_clarifications_from_session(session_turns: list[dict[str, str]] | None) -> str:
    """Build a concise clarification transcript from a session turn list."""
    if not session_turns:
        return ""

    clarifications: list[str] = []
    pending_questions: list[str] = []
    for turn in session_turns:
        role = str(turn.get("role") or "").lower()
        content = str(turn.get("content") or "").strip()
        if not content:
            continue

        if role == "assistant":
            pending_questions = _extract_questions_from_assistant_turn(content)
            continue

        if role != "user" or not pending_questions:
            continue

        answer = content
        if answer.lower().startswith("user confirmation:"):
            confirmation_value = answer.split(":", 1)[1].strip()
            if confirmation_value.lower() in {"c", "n"}:
                pending_questions = []
                continue

        question = pending_questions.pop(0)
        clarifications.append(f"Q: {question}")
        clarifications.append(f"A: {answer}")
        if not pending_questions:
            pending_questions = []

    return "\n".join(clarifications)


def build_trip_metadata(
    trip: Mapping[str, Any],
    session_id: str,
    original_prompt: str,
    clarifications: str,
    confirmed_trip_json: str,
) -> dict[str, Any]:
    """Build canonical trip metadata for ChromaDB storage."""
    trip_dict = dict(trip or {})
    trip_date = str(trip_dict.get("date") or "")
    trip_title = str(trip_dict.get("title") or trip_dict.get("trip_title") or "")
    origin = str(trip_dict.get("from") or trip_dict.get("origin") or "")
    destination = str(trip_dict.get("to") or trip_dict.get("destination") or "")
    time_leave = str(trip_dict.get("Time_leave") or trip_dict.get("time_leave") or "")
    time_arrival = str(trip_dict.get("Time_arrival") or trip_dict.get("time_arrival") or "")
    distance_km = trip_dict.get("distance_km")

    metadata = {
        "metadata_version": 1,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "original_prompt": original_prompt or "",
        "clarifications": clarifications or "",
        "confirmed_trip_json": confirmed_trip_json or "",
        "trip_title": trip_title,
        "trip_date": trip_date,
        "origin": origin,
        "destination": destination,
        "time_leave": time_leave,
        "time_arrival": time_arrival,
    }

    if distance_km not in (None, ""):
        try:
            metadata["distance_km"] = float(distance_km)
        except (TypeError, ValueError):
            metadata["distance_km"] = distance_km

    if time_leave and time_arrival:
        metadata["duration_minutes"] = _calculate_duration_minutes(time_leave, time_arrival)

    return metadata


def _calculate_duration_minutes(time_leave: str, time_arrival: str) -> int | None:
    try:
        leave_hour, leave_minute = map(int, time_leave.split(":"))
        arrival_hour, arrival_minute = map(int, time_arrival.split(":"))
    except (ValueError, AttributeError):
        return None

    leave_total = leave_hour * 60 + leave_minute
    arrival_total = arrival_hour * 60 + arrival_minute
    if arrival_total < leave_total:
        arrival_total += 24 * 60
    return arrival_total - leave_total
