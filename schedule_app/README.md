# Schedule App

A small local web app that displays the agenda from `../agenda.json` in a weekly calendar layout.

## Run

```bash
python schedule_app/app.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Behavior

- Reads `agenda.json` from the project root.
- Refreshes automatically every 5 seconds.
- Infers when the car is home from the gaps between trips.
- Shows home windows and trip cards in a weekly timeline view.

## Notes

- The app expects `agenda.json` to be a JSON list of trips.
- If the file is missing, the UI shows an empty state until data appears.
