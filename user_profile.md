# User Profile Template for RAG

Use this file as a single, clear narrative source of truth for one user. Fill in the placeholders with short factual statements. The goal is to give RAG a clean profile to retrieve when the model needs to add or modify trips.

Keep the content simple and non-duplicated. Do not repeat the same information in multiple sections unless there is a real difference in meaning.

---

## Identity and Location

Name: [Tom Dejaegher]

Short ID: [user_01]

Lives in (home): [Houtmarkt, Kortrijk, Belgium]

Timezone: [Europe/Brussels]

Home situation: [House with dedicated parking and home charger]

Optional location detail: []

---

## EV Profile

Vehicle: [Tesla model 3]

Model year: [2019]

Battery capacity: [45 kWh]

Typical efficiency: [16 kWh/100km]

Home charger power: [5 kW]

Maximum AC charge rate: [11 kW]

Home charging available: [yes]

Preferred target SOC: [80%]

Minimum SOC: [20%]

Charging preference: [home first, maximum by solar power, home battery available for night charging, public fast charger when needed]

---

## Daily Habits

Weekday commute: [Work from Mon-Fri and I drive from home to Arcelormittal Dunkerque, on Wednesday I only work half a day which is in the morning, single trip is 95km. On Tuesday evening I leave around 20:00 till 22:00 for hobby to Waregem in the sport hall De Treffer, single trip is 20km]

Weekend commute: [On Sundays in the morning from 9:00 till 11:00 to Lille in France which is 50km single trip]

Work or away hours: [Typically I leave at 06:30 and back home at 19:00 except for Wednesdays back at 13:00]

Car usually available at home: [e.g. 19:00–06:30 except on Tuesday evening only from 22:30 till 6:30]

Preferred charging window: []

Daily constraints: []

Example fill-in:
The user commutes 30 km from Monday to Friday. The car is usually at home from 18:00 to 08:00 and can charge overnight between 22:00 and 06:00.

---

## Monthly Habits

Typical long trip pattern: [The last Sunday of the month we go to Antwerpen AUWERSSTRAAT to meet my parents, we typically leave around 13:00 and are back at 19:00]

Monthly errands or special days: []

Monthly charging constraint: []

Example fill-in:
Once per month, the user has a long trip around the 15th of the month, usually around 200 km.

---

## Yearly Habits

Vacation months: [Typical summer vacation is last week of July and first 2 weeks of August and one week of holiday around Christmas and one week around New Year]

Seasonal changes: [Take in account in winter, it is colder and heater of the car is on increasing the consumption to 19kWh/100km]

Annual maintenance or service month: []

Other yearly notes: []

Example fill-in:
The user travels more during July and August and has an annual service in June.

---

## Charging and Availability Notes

Public charging preference: [prefer / neutral / avoid]

Times when the car must be available: [e.g. weekdays before 08:30]

Times when charging is allowed: [e.g. overnight only, off-peak only]

Special availability rules: [e.g. never charge during school drop-off hours]

---

## Constraints for Trip Planning

Use this section for any detail that matters when the model adds or modifies trips.

- The car must be available for work on weekday mornings.
- The user prefers charging at home rather than at public stations.
- Long trips should be planned with higher target SOC.

Write each constraint as one short sentence.

---

## Belgium Bank Holidays

Use these rules in a year-independent way.

Fixed-date holidays:

- 01-01 = New Year's Day
- 05-01 = Labour Day
- 07-21 = Belgian National Day
- 08-15 = Assumption of Mary
- 11-01 = All Saints' Day
- 11-11 = Armistice Day
- 12-25 = Christmas Day

Movable holidays relative to Easter Sunday:

- Easter Monday = Easter Sunday + 1 day
- Ascension Day = Easter Sunday + 39 days
- Pentecost Monday = Easter Sunday + 50 days

How to use:

1. Check the fixed month-day holidays first.
2. If the date is not fixed, calculate Easter Sunday for that year.
3. Then apply the movable holiday offsets above.
4. Keep in mind on these days we typical do not work and are home or plan a trip to unknown location

---

## Recommended Style for Filling This File

- Keep each line short and factual.
- Do not repeat the same fact in multiple sections.
- Use exact times, distances, and recurring patterns when known.
- Leave unknown fields blank instead of guessing.

