# EV Charging Calendar UI

A lightweight Python desktop app that displays a monthly calendar and marks recommended charging days for an electric vehicle.

## Features
- Monthly calendar view with charging days highlighted.
- Click any day to inspect charging window and energy estimate.
- In-app chat box to add manual trips in natural language.
- Voice-to-text input for trip chat using Whisper.
- Direct microphone capture (Start/Stop) for hands-free trip input.
- Home location input in the planner panel for trip context.
- Chat log shows raw LLM output for transparency/debugging.
- Adjustable planning inputs:
  - Home location
  - Battery capacity
  - Consumption
  - Charger power
  - Daily commute distance
  - Minimum, target, and starting SOC
- JSON export view for downstream optimization pipelines.

## LLM Trip Chat
The UI includes a chat panel that tries to load:

- `metallama/Llama-3.2-1B-Instruct`
- `openai/whisper-small` (for speech-to-text)

Example prompts:

- `trip to amsterdam this wednesday`
- `trip to rotterdam on 2026-04-02 160 km`
- `trip on 25/3 from gent to rotterdam and back`
- `add trip to utrecht on selected date 140 km`

Date handling notes:

- Supports `YYYY-MM-DD` and `DD/MM` (or `DD-MM`) formats.
- For `DD/MM` without a year, the app uses the currently selected planner year.

When a trip is added, the planner updates that day with extra driving distance and may add a pre-charge slot the previous day if needed.

Speech input flow:

- Click `Voice -> Text` in the chat panel.
- Select an audio file (`.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`).
- Whisper transcribes your speech and sends the transcript directly to Llama parsing.
- If FFmpeg is missing, `.wav` files can still work through an in-app fallback decoder.

Microphone flow:

- Click `Start Mic`, speak your trip request, then click `Stop Mic`.
- The app records temporary WAV audio, transcribes it with Whisper, and sends it to Llama parsing.

The chat flow is LLM-only. If the model is unavailable or returns unclear output, no trip is added.

The LLM prompt includes the selected date, planner year, and configured home location.

## Install (Optional but Recommended for LLM)

```bash
pip install transformers torch
```

For direct microphone recording:

```bash
pip install sounddevice
```

If your system cannot decode compressed audio files, install FFmpeg. Without FFmpeg, use `.wav` as input.

## Run
From the workspace root:

```bash
python charging_calendar_ui.py
```

If your terminal uses a Conda environment, run with that environment activated.

## Scheduling Logic (Prototype)
- Assumes weekday driving (Mon-Fri) with configurable daily commute distance.
- Schedules a charge when SOC drops below minimum threshold.
- Also allows a Sunday top-up to prepare for weekday driving.
- Adds manual trip distance from chat commands into day-level energy use.
- Adds pre-charge behavior when a planned trip would push next-day SOC below minimum.

## Notes
- This is a prototype planner with deterministic assumptions.
- You can later connect it to calendar APIs, trip estimators, and charging optimizers.
