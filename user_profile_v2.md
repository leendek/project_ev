# User Profile v2 for RAG Trip Scheduling

This file is optimized for retrieval. Keep facts short, atomic, and easy to quote back into a trip-planning prompt.

## Retrieval Rules
- Treat each bullet as a standalone fact.
- Prefer concrete values over descriptions.
- Store aliases, schedule facts, and exceptions separately.
- Avoid long prose paragraphs.
- Update facts when the user gives a better source of truth.

## Core Anchors
- home_base: Gent
- home_aliases: home, at home, my place
- work_location: Office, Brussels
- family_location: Kortrijk
- hobby_location: Waregem
- weekend_city: Antwerp
- leisure_aliases: friends, city center, restaurant, cinema
- transport_aliases: station, train station, airport

## Alias Map
- "home" -> Gent
- "office" -> Office, Brussels
- "work" -> Office, Brussels
- "HQ" -> Office, Brussels
- "parents" -> Kortrijk
- "family" -> Kortrijk
- "hobby" -> Waregem
- "sport" -> gym or training location
- "city trip" -> Antwerp unless user says otherwise
- "shop" -> nearest supermarket or shopping center

## Daily Schedule Facts
- weekday_commute_days: Monday to Friday
- weekday_commute_departure: 06:45
- weekday_commute_return: 17:30
- weekday_morning_location: car at home before departure
- weekday_daytime_location: car away from home
- weekday_evening_location: car at home after return
- weekday_night_location: car at home overnight

## Weekly Availability Windows
- Monday 00:00-06:45: car at home
- Monday 06:45-17:30: car away at Office, Brussels
- Monday 17:30-24:00: car at home
- Tuesday 00:00-06:45: car at home
- Tuesday 06:45-17:30: car away at Office, Brussels
- Tuesday 17:30-24:00: car at home
- Wednesday 00:00-06:45: car at home
- Wednesday 06:45-17:30: car away at Office, Brussels
- Wednesday 17:30-24:00: car at home
- Thursday 00:00-06:45: car at home
- Thursday 06:45-17:30: car away at Office, Brussels
- Thursday 17:30-19:00: car at home
- Thursday 19:00-22:00: car at Waregem
- Thursday 22:00-24:00: car at home
- Friday 00:00-06:45: car at home
- Friday 06:45-17:30: car away at Office, Brussels
- Friday 17:30-20:00: car at home
- Friday 20:00-21:30: car at gym or sport location
- Friday 21:30-24:00: car at home
- Saturday: usually at home unless a trip is scheduled
- Sunday: usually at home unless a family visit or weekend trip is scheduled

## Special Trip Patterns
- Saturday trips are often same-day return
- Sunday family visits are often evening return
- weekend trips often start on Saturday morning
- normal workweek means Monday to Friday commute days
- whole workweek should not be duplicated day by day unless the user asks for each day
- if the user says "from 8AM till 6PM", treat it as a round-trip window
- if the user says "weekend trip", ask whether return is same day or next day when unclear

## Location During Common Windows
- 06:45-17:30 on weekdays: car is at Office, Brussels
- 19:00-22:00 on Thursday: car is at Waregem
- 20:00-21:30 on Friday: car is at gym or sport location
- Saturday daytime without a trip: car is at home
- Sunday daytime without a trip: car is at home
- overnight without a trip: car is at home

## Trip History Facts
- route_gent_brussels_minutes: 45-70
- route_gent_kortrijk_minutes: 25-40
- route_gent_antwerp_minutes: 45-75
- route_gent_waregem_minutes: 20-35
- route_gent_leuven_minutes: 60-90
- route_gent_koksijde_minutes: 90-150
- route_gent_brussels_distance_km: about 55
- route_gent_kortrijk_distance_km: about 45
- route_gent_antwerp_distance_km: about 60
- route_gent_waregem_distance_km: about 25
- route_gent_leuven_distance_km: about 90
- route_gent_koksijde_distance_km: about 120

## Planning Hints
- if departure is 06:45 and return is 17:30, the car is away all day
- if the user gives a vague place, resolve it using the alias map first
- if the request mentions a known route, use the route facts to estimate the car location window
- if the request conflicts with the weekly schedule, use the explicit request over the default pattern
- if a trip is not explicit, do not invent it

## Date Interpretation Rules
- planner_year: 2026
- tomorrow means the next calendar day after today
- next Friday means the next Friday after today, not the current Friday if today is Friday
- this weekend means the nearest Saturday and Sunday in the current week context
- last weekend of May means the last Saturday and Sunday in May
- first Monday in June means the first Monday in June of the planner year
- reference_dates should cover the next 7 days from today

## Exception Rules
- school_holidays: fewer weekday commute trips
- public_holidays: no work commute by default
- work_from_home_day: remove commute trip
- car_service_day: no trip assumption
- rescheduled_hobby: replace normal hobby slot for that day
- vacation_period: override the normal weekly pattern

## Output Preferences
- split round trips into outbound and return records
- keep linked round-trip titles identical
- use null instead of guessing missing facts
- prefer precise times over broad windows when both are available
- return structured JSON suitable for downstream scheduling
- keep feedback_LLM short and specific

## Suggested Atomic Records
- commute_monday: leave 06:45, return 17:30
- commute_tuesday: leave 06:45, return 17:30
- commute_wednesday: leave 06:45, return 17:30
- commute_thursday: leave 06:45, return 17:30
- commute_friday: leave 06:45, return 17:30
- hobby_thursday: 19:00-22:00, Waregem
- sport_friday: 20:00-21:30, gym or sport location
- family_visit_sunday: Kortrijk, usually evening return
- weekend_trip: Antwerp, often Saturday only

## Compact Fact Block
- home_base: Gent
- work_location: Office, Brussels
- family_location: Kortrijk
- hobby_location: Waregem
- weekday_commute_departure: 06:45
- weekday_commute_return: 17:30
- Thursday_hobby_start: 19:00
- Thursday_hobby_end: 22:00
- Friday_sport_start: 20:00
- Friday_sport_end: 21:30
- Saturday_default_location: home
- Sunday_default_location: home

## Example Short Sentences for RAG
- The user lives in Gent.
- The default office destination is Office, Brussels.
- Weekday commuting is usually Monday to Friday.
- The car is usually at home overnight.
- Thursday evening is usually reserved for a hobby in Waregem.
- Friday evening may include sport.
- Weekend trips often start on Saturday.
- Family visits are often to Kortrijk.
- Public holidays should not create a work commute by default.
