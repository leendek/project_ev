const DAY_HEIGHT = 60; // pixels per hour from CSS --hour-height
const REFRESH_MS = 5000;
const daysEl = document.getElementById("days");
const timeAxisEl = document.getElementById("timeAxis");
const weekRangeEl = document.getElementById("weekRange");
const statusBarEl = document.getElementById("statusBar");
const lastTripKmEl = document.getElementById("lastTripKm");
const homeCityInput = document.getElementById("homeCityInput");
const prevWeekBtn = document.getElementById("prevWeek");
const nextWeekBtn = document.getElementById("nextWeek");

const state = {
  agenda: [],
  weekOffset: 0,
  anchorDate: null,
  loadedAt: null,
  homeCity: localStorage.getItem("schedule_home_city") || "Ghent",
};

const weekdayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function pad(value) {
  return String(value).padStart(2, "0");
}

function parseDateOnly(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function parseTimeValue(value) {
  if (!value) return null;
  if (typeof value !== "string") return null;

  if (value.includes("T")) {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return { hours: parsed.getHours(), minutes: parsed.getMinutes(), seconds: parsed.getSeconds() };
    }
  }

  const match = value.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!match) return null;
  return {
    hours: Number(match[1]),
    minutes: Number(match[2]),
    seconds: Number(match[3] || 0),
  };
}

function toMinutes(timeValue) {
  const parsed = parseTimeValue(timeValue);
  if (!parsed) return null;
  return parsed.hours * 60 + parsed.minutes + parsed.seconds / 60;
}

function minutesToLabel(totalMinutes) {
  const rounded = Math.round(totalMinutes);
  if (rounded >= 1440) return "24:00";
  const normalized = ((rounded % 1440) + 1440) % 1440;
  const hours = Math.floor(normalized / 60);
  const minutes = normalized % 60;
  return `${pad(hours)}:${pad(minutes)}`;
}

function minutesToClockRange(start, end) {
  return `${minutesToLabel(start)} – ${minutesToLabel(end)}`;
}

function formatDayHeader(date) {
  return {
    dow: weekdayLabels[date.getDay()],
    label: `${date.getDate()} ${monthLabels[date.getMonth()]}`,
  };
}

function formatWeekRange(startDate) {
  const endDate = new Date(startDate);
  endDate.setDate(endDate.getDate() + 6);

  const sameMonth = startDate.getMonth() === endDate.getMonth();
  const sameYear = startDate.getFullYear() === endDate.getFullYear();
  const startLabel = `${startDate.getDate()} ${monthLabels[startDate.getMonth()]}`;
  const endLabel = `${endDate.getDate()} ${monthLabels[endDate.getMonth()]}`;

  if (sameYear) {
    return sameMonth
      ? `${startLabel} – ${endDate.getDate()} ${monthLabels[endDate.getMonth()]} ${endDate.getFullYear()}`
      : `${startLabel} – ${endLabel} ${endDate.getFullYear()}`;
  }

  return `${startLabel} ${startDate.getFullYear()} – ${endLabel} ${endDate.getFullYear()}`;
}

function weekStartOf(date) {
  const result = new Date(date);
  const day = result.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  result.setDate(result.getDate() + diff);
  result.setHours(0, 0, 0, 0);
  return result;
}

function addDays(date, amount) {
  const result = new Date(date);
  result.setDate(result.getDate() + amount);
  return result;
}

function dateKeyLocal(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function getHomeCity() {
  return (state.homeCity || "Ghent").trim() || "Ghent";
}

function syncHomeCityInput() {
  if (homeCityInput && homeCityInput.value !== state.homeCity) {
    homeCityInput.value = state.homeCity;
  }
}

function parseTripDateTime(dateValue, timeValue, fallbackMinutes) {
  const baseDate = parseDateOnly(dateValue);
  if (!baseDate) return null;

  const parsedTime = parseTimeValue(timeValue);
  if (parsedTime) {
    baseDate.setHours(parsedTime.hours, parsedTime.minutes, parsedTime.seconds, 0);
    return baseDate;
  }

  if (typeof fallbackMinutes === "number" && Number.isFinite(fallbackMinutes)) {
    baseDate.setHours(0, 0, 0, 0);
    baseDate.setMinutes(fallbackMinutes);
    return baseDate;
  }

  return null;
}

function deriveTripStartDateTime(trip) {
  const leave = parseTripDateTime(trip.date, trip.Time_leave);
  if (leave) return leave;

  const arrival = parseTripDateTime(trip.date, trip.Time_arrival);
  if (arrival && typeof trip.travel_duration_s === "number") {
    return new Date(arrival.getTime() - trip.travel_duration_s * 1000);
  }

  return null;
}

function deriveTripEndDateTime(trip) {
  const arrival = parseTripDateTime(trip.date, trip.Time_arrival);
  if (arrival) return arrival;

  const leave = parseTripDateTime(trip.date, trip.Time_leave);
  if (leave && typeof trip.travel_duration_s === "number") {
    return new Date(leave.getTime() + trip.travel_duration_s * 1000);
  }

  return null;
}

function buildTripTimeline(agenda) {
  return agenda
    .map((trip, index) => {
      const start = deriveTripStartDateTime(trip);
      const end = deriveTripEndDateTime(trip);
      return {
        ...trip,
        _index: index,
        _start: start,
        _end: end,
        _fromNorm: normalizeText(trip.from),
        _toNorm: normalizeText(trip.to),
        _fromDisplay: trip.from || "",
        _toDisplay: trip.to || "",
      };
    })
    .filter((trip) => trip._start && trip._end)
    .sort((a, b) => a._start - b._start || a._end - b._end || a._index - b._index);
}

function inferInitialLocation(trips, homeCity) {
  if (!trips.length) return homeCity;
  const home = normalizeText(homeCity);
  const first = trips[0];
  if (first._fromNorm === home) return homeCity;
  if (first._toNorm === home) return "away";
  return "away";
}

function buildWeekSegments(agenda, homeCity, rangeStart, rangeEnd) {
  const trips = buildTripTimeline(agenda);
  const home = normalizeText(homeCity);
  const segments = [];
  let location = inferInitialLocation(trips, homeCity);
  let cursor = new Date(rangeStart);

  for (const trip of trips) {
    if (trip._end <= rangeStart) {
      location = trip._toDisplay || location;
      continue;
    }

    if (trip._start >= rangeEnd) {
      break;
    }

    const tripStart = trip._start < rangeStart ? new Date(rangeStart) : trip._start;
    const tripEnd = trip._end > rangeEnd ? new Date(rangeEnd) : trip._end;

    if (cursor < tripStart) {
      segments.push({
        type: normalizeText(location) === home ? "home" : "away",
        start: new Date(cursor),
        end: new Date(tripStart),
        location: normalizeText(location) === home ? homeCity : location,
      });
    }

    if (tripEnd > cursor) {
      segments.push({
        type: "trip",
        start: new Date(tripStart),
        end: new Date(tripEnd),
        trip,
      });
    }

    cursor = tripEnd > cursor ? new Date(tripEnd) : new Date(cursor);
    location = trip._toDisplay || location;
  }

  if (cursor < rangeEnd) {
    segments.push({
      type: normalizeText(location) === home ? "home" : "away",
      start: new Date(cursor),
      end: new Date(rangeEnd),
      location: normalizeText(location) === home ? homeCity : location,
    });
  }

  if (!segments.length) {
    segments.push({
      type: "home",
      start: new Date(rangeStart),
      end: new Date(rangeEnd),
      location: homeCity,
    });
  }

  return segments;
}

function minutesFromDate(date) {
  return date.getHours() * 60 + date.getMinutes() + date.getSeconds() / 60;
}

function sliceSegmentToDay(segment, dayStart, dayEnd) {
  const start = segment.start < dayStart ? dayStart : segment.start;
  const end = segment.end > dayEnd ? dayEnd : segment.end;
  if (end <= start) return null;
  return { ...segment, start, end };
}

function groupAgendaByDate(agenda) {
  const grouped = new Map();
  for (const trip of agenda) {
    const dateKey = trip.date || "unknown";
    if (!grouped.has(dateKey)) grouped.set(dateKey, []);
    grouped.get(dateKey).push(trip);
  }
  for (const [dateKey, trips] of grouped.entries()) {
    trips.sort((a, b) => (getTripStartMinutes(a) ?? 0) - (getTripStartMinutes(b) ?? 0));
  }
  return grouped;
}

function getTripStartMinutes(trip) {
  const fromLeave = toMinutes(trip.Time_leave);
  if (fromLeave !== null) return fromLeave;
  const arrival = toMinutes(trip.Time_arrival);
  if (arrival !== null && trip.travel_duration_s) {
    return Math.max(0, arrival - trip.travel_duration_s / 60);
  }
  return null;
}

function getTripEndMinutes(trip) {
  const arrival = toMinutes(trip.Time_arrival);
  if (arrival !== null) return arrival;
  const departure = toMinutes(trip.Time_leave);
  if (departure !== null && trip.travel_duration_s) {
    return departure + trip.travel_duration_s / 60;
  }
  return departure;
}

function getTripDurationMinutes(trip) {
  if (typeof trip.travel_duration_s === "number") return trip.travel_duration_s / 60;
  const start = getTripStartMinutes(trip);
  const end = getTripEndMinutes(trip);
  if (start !== null && end !== null) return Math.max(0, end - start);
  return 0;
}

function buildDaySegments(trips) {
  const segments = [];
  const sortedTrips = [...trips].sort((a, b) => (getTripStartMinutes(a) ?? 0) - (getTripStartMinutes(b) ?? 0));
  let cursor = 0;
  let lastTrip = null;

  for (const trip of sortedTrips) {
    const start = getTripStartMinutes(trip);
    const end = getTripEndMinutes(trip);

    if (start === null && end === null) continue;

    const safeStart = Math.max(0, Math.min(1440, start ?? end ?? 0));
    const safeEnd = Math.max(safeStart, Math.min(1440, end ?? safeStart));

    if (safeStart > cursor) {
      segments.push({
        type: "home",
        start: cursor,
        end: safeStart,
        priorTrip: lastTrip,
      });
    }

    segments.push({
      type: "trip",
      start: safeStart,
      end: Math.max(safeStart + 1, safeEnd),
      trip,
    });

    cursor = Math.max(cursor, Math.max(safeStart + 1, safeEnd));
    lastTrip = trip;
  }

  if (cursor < 1440) {
    segments.push({
      type: "home",
      start: cursor,
      end: 1440,
      priorTrip: lastTrip,
    });
  }

  if (!segments.length) {
    segments.push({ type: "home", start: 0, end: 1440, priorTrip: null });
  }

  return segments;
}

function svgCar(color = "currentColor") {
  return `
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M5 14.5V12.7c0-.62.18-1.23.52-1.76l1.21-1.86A3 3 0 0 1 9.24 8h5.52a3 3 0 0 1 2.51 1.34l1.21 1.86c.34.53.52 1.14.52 1.76v1.54" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M6 14h12" stroke="${color}" stroke-width="1.8" stroke-linecap="round"/>
      <circle cx="8" cy="16.8" r="1.2" stroke="${color}" stroke-width="1.6"/>
      <circle cx="16" cy="16.8" r="1.2" stroke="${color}" stroke-width="1.6"/>
      <path d="M11.4 3.8 9.7 8.1h2.2l-.9 4.3 4-5.3h-2.5l.9-3.3h-2Z" fill="${color}"/>
    </svg>
  `;
}

function svgHome(color = "currentColor") {
  return `
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M4 11.5 12 5l8 6.5" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M6.8 10.7V19h10.4v-8.3" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M10.2 19v-4h3.6v4" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  `;
}

function renderTimeAxis(headerOffset = 0) {
  timeAxisEl.innerHTML = "";
  for (let hour = 0; hour < 24; hour += 1) {
    const label = document.createElement("div");
    label.className = "time-label";
    label.style.top = `${headerOffset + hour * DAY_HEIGHT}px`;
    label.textContent = `${pad(hour)}:00`;
    timeAxisEl.appendChild(label);
  }
}

function renderAgenda(agenda) {
  const anchor = state.anchorDate || weekStartOf(new Date());
  const weekStart = addDays(anchor, state.weekOffset * 7);
  const weekEnd = addDays(weekStart, 7);
  const homeCity = getHomeCity();
  const segments = buildWeekSegments(agenda, homeCity, weekStart, weekEnd);

  weekRangeEl.textContent = formatWeekRange(weekStart);
  daysEl.innerHTML = "";

  let latestTripDistance = null;
  let latestTripEnd = -1;
  for (const trip of agenda) {
    const end = getTripEndMinutes(trip);
    if (typeof trip.distance_km === "number" && end !== null && end >= latestTripEnd) {
      latestTripDistance = trip.distance_km;
      latestTripEnd = end;
    }
  }
  lastTripKmEl.textContent = latestTripDistance !== null ? latestTripDistance.toFixed(0) : "--";

  for (let dayOffset = 0; dayOffset < 7; dayOffset += 1) {
    const dayDate = addDays(weekStart, dayOffset);
    const header = formatDayHeader(dayDate);
    const dayStart = new Date(dayDate);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(dayDate);
    dayEnd.setHours(23, 59, 59, 999);
    const daySegments = segments
      .map((segment) => sliceSegmentToDay(segment, dayStart, dayEnd))
      .filter(Boolean)
      .filter((segment) => segment.start < segment.end);

    const col = document.createElement("section");
    col.className = "day-column";
    col.innerHTML = `
      <div class="day-header">
        <span class="day-header__dow">${header.dow}</span>
        <span class="day-header__date">${header.label}</span>
      </div>
      <div class="day-body"></div>
    `;

    const body = col.querySelector(".day-body");

    if (!daySegments.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No agenda items";
      body.appendChild(empty);
    } else {
      const pxPerMinute = DAY_HEIGHT / 60;
      for (const segment of daySegments) {
        const el = document.createElement("article");
        el.className = `segment segment--${segment.type}`;
        const startMinutes = minutesFromDate(segment.start);
        const endMinutes = minutesFromDate(segment.end);
        el.style.top = `${startMinutes * pxPerMinute}px`;
        el.style.height = `${Math.max(42, (endMinutes - startMinutes) * pxPerMinute)}px`;

        if (segment.type === "home") {
          el.innerHTML = `
            <div class="segment__content">
              <div class="segment__time">${minutesToLabel(startMinutes)} – ${minutesToLabel(endMinutes)}</div>
              <div class="segment__label">Car is home</div>
              <div class="home-window">
                <div class="home-window__top">
                  <div class="home-card__icon">${svgHome("#4f9158")}</div>
                  <div class="home-meta">
                    <div class="home-meta__stats">
                      <span>${homeCity}</span>
                    </div>
                    <div class="home-window__sub">Available for charging</div>
                    <div class="home-meta__stats">
                      <span class="home-window__km">At home</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          `;
        } else if (segment.type === "away") {
          const locationLabel = segment.location ? segment.location : "unknown location";
          el.innerHTML = `
            <div class="segment__content">
              <div class="segment__time">${minutesToLabel(startMinutes)} – ${minutesToLabel(endMinutes)}</div>
              <div class="segment__label">Car is not home</div>
              <div class="away-window">
                <div class="home-window__top">
                  <div class="home-card__icon">${svgCar("#c15f4a")}</div>
                  <div class="home-meta">
                    <div class="home-meta__stats">
                      <span>${locationLabel}</span>
                    </div>
                    <div class="away-window__sub">No charging window at home during this interval</div>
                  </div>
                </div>
              </div>
            </div>
          `;
        } else {
          const trip = segment.trip;
          const durationMinutes = getTripDurationMinutes(trip);
          const departure = minutesToLabel(startMinutes);
          const arrival = minutesToLabel(endMinutes);
          const route = `${trip.from || "Unknown"} → ${trip.to || "Unknown"}`;
          const stats = [];
          if (typeof trip.distance_km === "number") stats.push(`${trip.distance_km.toFixed(2)} km`);
          if (durationMinutes) stats.push(`${Math.round(durationMinutes)} min`);
          el.innerHTML = `
            <div class="segment__content">
              <div class="trip-card">
                <div class="trip-card__icon">${svgCar("#4478c0")}</div>
                <div class="trip-meta">
                  <div class="trip-meta__title">${trip.title || trip.action || "Trip"}</div>
                  <div class="trip-meta__route">${route}</div>
                  <div class="trip-meta__stats">
                    <span>${departure} – ${arrival}</span>
                    ${stats.map((item) => `<span>${item}</span>`).join("")}
                  </div>
                </div>
              </div>
            </div>
          `;
        }

        body.appendChild(el);
      }
    }

    daysEl.appendChild(col);
  }

  }

  // Determine header offset (height of the sticky day header) so the time axis aligns
  const headerEl = document.querySelector('.day-header');
  const headerHeight = headerEl ? Math.ceil(headerEl.getBoundingClientRect().height) : 82;
  renderTimeAxis(headerHeight + 4); // small extra padding to clear the border
function pickAnchorDate(agenda) {
  const dates = agenda
    .map((trip) => parseDateOnly(trip.date))
    .filter(Boolean)
    .sort((a, b) => a.getTime() - b.getTime());

  const base = dates[0] || new Date();
  return weekStartOf(base);
}

async function loadAgenda() {
  try {
    const response = await fetch(`/api/agenda?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    state.agenda = Array.isArray(data.agenda) ? data.agenda : [];
    state.anchorDate = pickAnchorDate(state.agenda);
    state.loadedAt = new Date();
    renderAgenda(state.agenda);

    const timestamp = state.loadedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    statusBarEl.textContent = `Loaded ${state.agenda.length} trips from agenda.json at ${timestamp}. Home city: ${getHomeCity()}. Refreshes every 5 seconds.`;
  } catch (error) {
    statusBarEl.textContent = `Could not load agenda.json: ${error.message}`;
  }
}

function saveHomeCity(value) {
  const nextHomeCity = value.trim() || "Ghent";
  state.homeCity = nextHomeCity;
  localStorage.setItem("schedule_home_city", nextHomeCity);
  syncHomeCityInput();
  renderAgenda(state.agenda);
}

prevWeekBtn.addEventListener("click", () => {
  state.weekOffset -= 1;
  renderAgenda(state.agenda);
});

nextWeekBtn.addEventListener("click", () => {
  state.weekOffset += 1;
  renderAgenda(state.agenda);
});

homeCityInput.addEventListener("change", () => saveHomeCity(homeCityInput.value));
homeCityInput.addEventListener("blur", () => saveHomeCity(homeCityInput.value));

syncHomeCityInput();

// Initial render will call renderTimeAxis from renderAgenda after measuring header
loadAgenda();
setInterval(loadAgenda, REFRESH_MS);
