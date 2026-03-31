import calendar
import json
import re
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import date, timedelta
from tkinter import messagebox, ttk

try:
    from transformers import pipeline
except Exception:
    pipeline = None


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class ChargeSlot:
    day: date
    start: str
    end: str
    energy_kwh: float
    target_soc: int
    reason: str


@dataclass
class TripEvent:
    day: date
    title: str
    distance_km: float


class ChargingPlanner:
    def __init__(
        self,
        battery_kwh: float,
        efficiency_kwh_100km: float,
        charger_power_kw: float,
        daily_km: float,
        min_soc: int,
        target_soc: int,
        start_soc: int,
        planned_trip_km: dict[date, float] | None = None,
    ) -> None:
        self.battery_kwh = battery_kwh
        self.efficiency_kwh_100km = efficiency_kwh_100km
        self.charger_power_kw = charger_power_kw
        self.daily_km = daily_km
        self.min_soc = min_soc
        self.target_soc = target_soc
        self.start_soc = start_soc
        self.planned_trip_km = planned_trip_km or {}

    def simulate_month(self, year: int, month: int) -> dict[date, ChargeSlot]:
        slots: dict[date, ChargeSlot] = {}
        current_soc = float(self.start_soc)

        _, last_day = calendar.monthrange(year, month)
        for day_num in range(1, last_day + 1):
            current_day = date(year, month, day_num)
            weekday = current_day.weekday()
            trip_km = float(self.planned_trip_km.get(current_day, 0.0))

            drive_km = trip_km
            if weekday < 5:
                # Weekday commute assumption: use energy Monday to Friday.
                drive_km += self.daily_km

            if drive_km > 0:
                used_kwh = (drive_km * self.efficiency_kwh_100km) / 100.0
                used_percent = (used_kwh / self.battery_kwh) * 100.0
                current_soc = max(0.0, current_soc - used_percent)

            should_charge = current_soc <= self.min_soc
            reason = "SOC below minimum threshold"

            next_day = current_day + timedelta(days=1)
            next_trip_km = float(self.planned_trip_km.get(next_day, 0.0))
            if next_trip_km > 0:
                projected_km = next_trip_km + (self.daily_km if next_day.weekday() < 5 else 0.0)
                projected_used_kwh = (projected_km * self.efficiency_kwh_100km) / 100.0
                projected_used_percent = (projected_used_kwh / self.battery_kwh) * 100.0
                projected_soc_after_next_day = current_soc - projected_used_percent
                if projected_soc_after_next_day < self.min_soc:
                    should_charge = True
                    reason = f"Prepare for planned trip on {next_day.isoformat()}"

            # Top up before Monday when weekend ends.
            if weekday == 6 and current_soc < self.target_soc:
                should_charge = True
                reason = "Prepare for weekday driving"

            if should_charge:
                needed_percent = max(0.0, float(self.target_soc) - current_soc)
                needed_kwh = (needed_percent / 100.0) * self.battery_kwh

                max_end_hour = 6.0
                hours_needed = needed_kwh / self.charger_power_kw if self.charger_power_kw else 0.0

                # Slot is placed overnight: from previous evening to early morning.
                end_clock = max_end_hour
                start_clock = max(0.0, end_clock - hours_needed)
                if start_clock < 0.0:
                    start_clock = 0.0

                start_time = f"{int(start_clock):02d}:{int((start_clock % 1) * 60):02d}"
                end_time = f"{int(end_clock):02d}:{int((end_clock % 1) * 60):02d}"

                slots[current_day] = ChargeSlot(
                    day=current_day,
                    start=start_time,
                    end=end_time,
                    energy_kwh=round(needed_kwh, 2),
                    target_soc=self.target_soc,
                    reason=reason,
                )
                current_soc = float(self.target_soc)

        return slots


class ChargingCalendarUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("EV Charging Calendar Planner")
        self.root.geometry("1050x700")
        self.root.minsize(920, 620)

        self.charge_slots: dict[date, ChargeSlot] = {}
        self.trip_events: dict[date, TripEvent] = {}
        self.selected_day: date | None = None
        self.chat_busy = False
        self.llm_generator = None

        today = date.today()
        self.year_var = tk.IntVar(value=today.year)
        self.month_var = tk.IntVar(value=today.month)

        self.battery_var = tk.DoubleVar(value=60.0)
        self.efficiency_var = tk.DoubleVar(value=17.0)
        self.charger_var = tk.DoubleVar(value=7.4)
        self.daily_km_var = tk.DoubleVar(value=35.0)
        self.min_soc_var = tk.IntVar(value=30)
        self.target_soc_var = tk.IntVar(value=80)
        self.start_soc_var = tk.IntVar(value=65)

        self.day_cells: dict[date, tk.Button] = {}

        self._build_ui()
        self.recompute()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)

        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=2)
        container.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(container)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self._build_controls(left_frame)

        self.calendar_frame = ttk.Frame(left_frame)
        self.calendar_frame.pack(fill="both", expand=True, pady=(8, 0))

        right_frame = ttk.LabelFrame(container, text="Charging Details", padding=10)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.rowconfigure(1, weight=1)

        self.details_label = ttk.Label(
            right_frame,
            text="Select a day from the calendar",
            justify="left",
            anchor="nw",
        )
        self.details_label.pack(fill="x", pady=(0, 10))

        self.json_box = tk.Text(right_frame, height=20, wrap="word")
        self.json_box.pack(fill="both", expand=True)

        export_btn = ttk.Button(right_frame, text="Export Monthly JSON", command=self.export_monthly_json)
        export_btn.pack(fill="x", pady=(10, 0))

        self._build_chat_panel(right_frame)

    def _build_chat_panel(self, parent: ttk.Frame) -> None:
        chat_frame = ttk.LabelFrame(parent, text="Trip Chat (TinyLlama)", padding=8)
        chat_frame.pack(fill="both", expand=False, pady=(10, 0))

        self.chat_status_var = tk.StringVar(value="LLM not loaded. Messages will use fallback parser if needed.")
        status_label = ttk.Label(chat_frame, textvariable=self.chat_status_var, wraplength=320, justify="left")
        status_label.pack(fill="x", pady=(0, 6))

        self.chat_log = tk.Text(chat_frame, height=9, wrap="word", state="disabled")
        self.chat_log.pack(fill="both", expand=True)

        entry_row = ttk.Frame(chat_frame)
        entry_row.pack(fill="x", pady=(6, 0))

        self.chat_input = ttk.Entry(entry_row)
        self.chat_input.pack(side="left", fill="x", expand=True)
        self.chat_input.bind("<Return>", lambda _event: self.send_chat_message())

        send_btn = ttk.Button(entry_row, text="Send", command=self.send_chat_message)
        send_btn.pack(side="left", padx=(6, 0))

        hint = "Example: trip to amsterdam this wednesday 240 km"
        ttk.Label(chat_frame, text=hint).pack(anchor="w", pady=(6, 0))

    def _build_controls(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Planner Inputs", padding=10)
        controls.pack(fill="x")

        fields = [
            ("Year", self.year_var),
            ("Month", self.month_var),
            ("Battery (kWh)", self.battery_var),
            ("Efficiency (kWh/100km)", self.efficiency_var),
            ("Charger Power (kW)", self.charger_var),
            ("Daily Commute (km)", self.daily_km_var),
            ("Min SOC (%)", self.min_soc_var),
            ("Target SOC (%)", self.target_soc_var),
            ("Start SOC (%)", self.start_soc_var),
        ]

        for row, (label, var) in enumerate(fields):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(controls, textvariable=var, width=12).grid(row=row, column=1, sticky="ew", pady=4)

        controls.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(controls)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ttk.Button(btn_frame, text="Generate Calendar", command=self.recompute).pack(side="left")
        ttk.Button(btn_frame, text="Today", command=self.go_to_today).pack(side="left", padx=(8, 0))

    def recompute(self) -> None:
        try:
            planner = ChargingPlanner(
                battery_kwh=float(self.battery_var.get()),
                efficiency_kwh_100km=float(self.efficiency_var.get()),
                charger_power_kw=float(self.charger_var.get()),
                daily_km=float(self.daily_km_var.get()),
                min_soc=int(self.min_soc_var.get()),
                target_soc=int(self.target_soc_var.get()),
                start_soc=int(self.start_soc_var.get()),
                planned_trip_km={d: e.distance_km for d, e in self.trip_events.items()},
            )
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            if month < 1 or month > 12:
                raise ValueError("Month must be between 1 and 12")

            self.charge_slots = planner.simulate_month(year, month)
            self.selected_day = None
            self._render_calendar(year, month)
            self._set_details_text("Select a day from the calendar")
            self._set_json_text("")
        except ValueError as exc:
            messagebox.showerror("Invalid Input", str(exc))

    def _render_calendar(self, year: int, month: int) -> None:
        for child in self.calendar_frame.winfo_children():
            child.destroy()
        self.day_cells.clear()

        header = ttk.Label(
            self.calendar_frame,
            text=f"{calendar.month_name[month]} {year}",
            font=("Segoe UI", 14, "bold"),
        )
        header.grid(row=0, column=0, columnspan=7, pady=(0, 8))

        for idx, day_name in enumerate(DAYS):
            ttk.Label(self.calendar_frame, text=day_name, anchor="center").grid(
                row=1, column=idx, sticky="ew", padx=2, pady=2
            )

        month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)

        for week_idx, week in enumerate(month_matrix, start=2):
            for day_idx, day_obj in enumerate(week):
                in_month = day_obj.month == month
                charge_slot = self.charge_slots.get(day_obj)
                trip_event = self.trip_events.get(day_obj)

                if not in_month:
                    label = ""
                    state = "disabled"
                    bg = "#efefef"
                else:
                    label = str(day_obj.day)
                    if charge_slot:
                        label += "\nCHG"
                    if trip_event:
                        label += "\nTRIP"
                    state = "normal"
                    if charge_slot and trip_event:
                        bg = "#cfe3ff"
                    elif charge_slot:
                        bg = "#d7f2d7"
                    elif trip_event:
                        bg = "#fff0bf"
                    else:
                        bg = "#ffffff"

                btn = tk.Button(
                    self.calendar_frame,
                    text=label,
                    width=11,
                    height=4,
                    relief="ridge",
                    bg=bg,
                    state=state,
                    command=lambda d=day_obj: self.show_day(d),
                )
                btn.grid(row=week_idx, column=day_idx, sticky="nsew", padx=2, pady=2)

                if in_month:
                    self.day_cells[day_obj] = btn

        for col in range(7):
            self.calendar_frame.columnconfigure(col, weight=1)

    def show_day(self, selected: date) -> None:
        self.selected_day = selected
        slot = self.charge_slots.get(selected)
        trip_event = self.trip_events.get(selected)

        if slot:
            details = (
                f"Date: {slot.day.isoformat()}\n"
                f"Charge Window: {slot.start} - {slot.end}\n"
                f"Energy Needed: {slot.energy_kwh} kWh\n"
                f"Target SOC: {slot.target_soc}%\n"
                f"Reason: {slot.reason}"
            )
            payload = {
                "date": slot.day.isoformat(),
                "car_availability": [
                    {"start": "00:00", "end": slot.start},
                    {"start": slot.end, "end": "23:59"},
                ],
                "charging_slot": {
                    "start": slot.start,
                    "end": slot.end,
                    "energy_kwh": slot.energy_kwh,
                    "target_soc": slot.target_soc,
                    "reason": slot.reason,
                },
            }
            self._set_json_text(json.dumps(payload, indent=2))
        else:
            details = (
                f"Date: {selected.isoformat()}\n"
                "No charging scheduled for this day.\n"
                "Vehicle can remain available all day."
            )
            payload = {
                "date": selected.isoformat(),
                "car_availability": [{"start": "00:00", "end": "23:59"}],
                "charging_slot": None,
            }
            self._set_json_text(json.dumps(payload, indent=2))

        if trip_event:
            details += (
                "\n\nPlanned Trip:\n"
                f"Title: {trip_event.title}\n"
                f"Extra Distance: {trip_event.distance_km} km"
            )
            payload["planned_trip"] = {
                "title": trip_event.title,
                "distance_km": trip_event.distance_km,
            }
            self._set_json_text(json.dumps(payload, indent=2))

        self._set_details_text(details)
        self._highlight_selected_day()

    def _highlight_selected_day(self) -> None:
        for day_obj, btn in self.day_cells.items():
            slot = self.charge_slots.get(day_obj)
            trip_event = self.trip_events.get(day_obj)
            if slot and trip_event:
                default_bg = "#cfe3ff"
            elif slot:
                default_bg = "#d7f2d7"
            elif trip_event:
                default_bg = "#fff0bf"
            else:
                default_bg = "#ffffff"
            btn.configure(bg=default_bg, highlightthickness=0)

        if self.selected_day in self.day_cells:
            self.day_cells[self.selected_day].configure(highlightthickness=2, highlightbackground="#2f5cff")

    def _set_details_text(self, text: str) -> None:
        self.details_label.configure(text=text)

    def _set_json_text(self, text: str) -> None:
        self.json_box.delete("1.0", tk.END)
        self.json_box.insert("1.0", text)

    def go_to_today(self) -> None:
        today = date.today()
        self.year_var.set(today.year)
        self.month_var.set(today.month)
        self.recompute()

    def export_monthly_json(self) -> None:
        year = int(self.year_var.get())
        month = int(self.month_var.get())
        _, last_day = calendar.monthrange(year, month)

        entries = []
        for day_num in range(1, last_day + 1):
            day_obj = date(year, month, day_num)
            slot = self.charge_slots.get(day_obj)
            trip_event = self.trip_events.get(day_obj)
            if slot:
                availability = [
                    {"start": "00:00", "end": slot.start},
                    {"start": slot.end, "end": "23:59"},
                ]
            else:
                availability = [{"start": "00:00", "end": "23:59"}]

            entries.append(
                {
                    "date": day_obj.isoformat(),
                    "car_availability": availability,
                    "planned_trip": (
                        {
                            "title": trip_event.title,
                            "distance_km": trip_event.distance_km,
                        }
                        if trip_event
                        else None
                    ),
                }
            )

        self._set_json_text(json.dumps(entries, indent=2))

    def send_chat_message(self) -> None:
        text = self.chat_input.get().strip()
        if not text or self.chat_busy:
            return

        self.chat_input.delete(0, tk.END)
        self._append_chat("You", text)
        self.chat_busy = True
        self.chat_status_var.set("Processing message...")

        worker = threading.Thread(target=self._process_chat_message, args=(text,), daemon=True)
        worker.start()

    def _process_chat_message(self, text: str) -> None:
        action, source = self._interpret_message(text)
        self.root.after(0, lambda: self._apply_chat_action(action, source, text))

    def _apply_chat_action(self, action: dict | None, source: str, original_text: str) -> None:
        self.chat_busy = False
        self.chat_status_var.set(source)

        if not action:
            self._append_chat(
                "Assistant",
                "I could not parse that request. Try: 'trip to amsterdam this wednesday 240 km'.",
            )
            return

        if action.get("action") != "add_trip":
            self._append_chat("Assistant", "Only add_trip is supported right now.")
            return

        trip_date = self._parse_iso_date(action.get("date", ""))
        if not trip_date:
            self._append_chat("Assistant", "I could not resolve the trip date.")
            return

        title = str(action.get("title") or "Trip")
        try:
            distance_km = float(action.get("distance_km") or 120.0)
        except ValueError:
            distance_km = 120.0

        self.trip_events[trip_date] = TripEvent(day=trip_date, title=title, distance_km=round(distance_km, 1))
        self.recompute()

        year = int(self.year_var.get())
        month = int(self.month_var.get())
        if trip_date.year == year and trip_date.month == month:
            self.show_day(trip_date)

        self._append_chat(
            "Assistant",
            (
                f"Added trip on {trip_date.isoformat()}: {title} ({round(distance_km, 1)} km). "
                "Calendar and charging plan updated."
            ),
        )

    def _append_chat(self, role: str, text: str) -> None:
        self.chat_log.configure(state="normal")
        self.chat_log.insert(tk.END, f"{role}: {text}\n")
        self.chat_log.see(tk.END)
        self.chat_log.configure(state="disabled")

    def _interpret_message(self, message: str) -> tuple[dict | None, str]:
        llm_result = self._interpret_with_llm(message)
        if llm_result:
            return llm_result, "Parsed with TinyLlama"

        fallback = self._fallback_trip_parser(message)
        if fallback:
            return fallback, "TinyLlama unavailable or unclear output; used fallback parser"

        return None, "Could not parse request"

    def _interpret_with_llm(self, message: str) -> dict | None:
        if pipeline is None:
            return None

        if self.llm_generator is None:
            try:
                self.chat_status_var.set("Loading TinyLlama model (first run may take a while)...")
                self.llm_generator = pipeline(
                    "text-generation",
                    model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                )
            except Exception:
                self.llm_generator = None
                return None

        today_iso = date.today().isoformat()
        system_prompt = (
            "You are a parser that converts trip requests into strict JSON. "
            "Return only one JSON object with keys: action, title, date, distance_km. "
            "Use action='add_trip'. Date must be ISO YYYY-MM-DD. "
            f"Assume today's date is {today_iso}."
        )
        prompt = f"{system_prompt}\nUser: {message}\nJSON:"

        try:
            output = self.llm_generator(
                prompt,
                max_new_tokens=120,
                do_sample=False,
                temperature=0.1,
                return_full_text=False,
            )
        except Exception:
            return None

        if not output:
            return None

        generated = output[0].get("generated_text", "").strip()
        json_match = re.search(r"\{[\s\S]*\}", generated)
        candidate = json_match.group(0) if json_match else generated

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None
        if parsed.get("action") != "add_trip":
            parsed["action"] = "add_trip"
        return parsed

    def _fallback_trip_parser(self, message: str) -> dict | None:
        text = message.strip().lower()
        if "trip" not in text and "drive" not in text and "go to" not in text:
            return None

        explicit_date = self._extract_explicit_date(text)
        if explicit_date:
            trip_date = explicit_date
        else:
            weekday_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            trip_date = None
            use_next = "next " in text
            base = date.today()
            for name, idx in weekday_map.items():
                if name in text:
                    trip_date = self._resolve_weekday(base, idx, force_next=use_next)
                    break

        if not trip_date:
            return None

        distance_match = re.search(r"(\d+(?:\.\d+)?)\s*(km|kilometer|kilometers)", text)
        distance_km = float(distance_match.group(1)) if distance_match else 120.0

        to_match = re.search(r"trip to\s+([a-z0-9\s\-]+?)(?:\s+(?:this|next)\s+|\s+on\s+|\s+\d+\s*km|$)", text)
        if to_match:
            location = to_match.group(1).strip(" .,")
            title = f"Trip to {location.title()}"
        else:
            title = "Trip"

        return {
            "action": "add_trip",
            "title": title,
            "date": trip_date.isoformat(),
            "distance_km": distance_km,
        }

    def _extract_explicit_date(self, text: str) -> date | None:
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if not match:
            return None

        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    def _resolve_weekday(self, base: date, weekday: int, force_next: bool = False) -> date:
        days_ahead = (weekday - base.weekday()) % 7
        if force_next:
            days_ahead = days_ahead + 7 if days_ahead != 0 else 7
        return base + timedelta(days=days_ahead)

    def _parse_iso_date(self, value: str) -> date | None:
        try:
            year, month, day = value.split("-")
            return date(int(year), int(month), int(day))
        except Exception:
            return None


def main() -> None:
    root = tk.Tk()
    app = ChargingCalendarUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
