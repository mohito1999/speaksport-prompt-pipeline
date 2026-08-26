# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/Los_Angeles`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Check caller member status:
   - If at least one `customer_passes` record has `expired: false` or `customer_groups` contains "member" or "Member" (case-insensitive), classify the caller as a Member.
   - Otherwise, classify the caller as a Public Player (Non-Member).
3. If the caller is a Member:
   - Calculate the latest allowed booking date as the facility-local current date plus 13 calendar days (representing a 14-day booking window inclusive of the current date).
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Members can only book up to 14 days in advance (including today). Please choose a date on or before the latest available booking date."
4. If the caller is a Public Player (Non-Member):
   - Calculate the latest allowed booking date as the facility-local current date plus 6 calendar days (representing a 7-day booking window inclusive of the current date).
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Public players can only book up to 7 days in advance (including today). Please choose a date on or before the latest available booking date."
5. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

For example, when the local current date is July 10:
- For public players, July 16 is eligible and July 17 is not.
- For members, July 23 is eligible and July 24 is not.

The eligibility tool receives `date` as `YYYY-MM-DD` and requested approximate `time` as 24-hour `HH:MM`. Do not send players, holes, riding preference, identity fields, or a course name to eligibility.

## Availability and booking

- After eligibility succeeds, collect exact player count and nine or eighteen holes.
- Do not ask riding or walking before availability; riding is not an availability argument.
- Search availability without `course` or `course_name` because Gold Hills is a single-course facility.
- For one player, present only slots whose `spots_remaining` is below four so the caller joins an existing group.
- Preserve every returned slot as a single record containing `time`, `course`, `spots_remaining`, and all returned pricing fields.
- Gold Hills is not on the SpeakSport per-booking fee model. Quote `base_price_per_player` as the walking rate and `base_price_per_player_riding` as the riding rate. Do not add or describe a booking fee.
- After the caller selects an exact returned slot, ask whether they will ride or walk. Pass the corresponding `riding` boolean to booking.
- Pass the selected slot's exact returned `course` to booking.

## Date and weekday resolution

- Use the enhanced `get-day-of-week-staging` contract for every date-sensitive request.
- Date only: pass only `date` and use returned `readable` and `day_of_week`.
- Weekday only: pass only `day_of_week`, present the four returned upcoming dates, and ask the caller to choose one exact date.
- Date and weekday together: pass both. If `matches` is false, explain the conflict and stop before inventory warm-up, eligibility, availability, or booking.

## Cancellation eligibility

- Use exact facility-local hours until tee off.
- Less than 24 hours is ineligible: "I can only process cancellations for tee times that are at least 24 hours from now. The Pro Shop can help you with this cancellation."
- Exactly 24 hours or more is eligible: "Eligible for cancellation."
- Apply no other cancellation criteria.
- ForeUp references use `TTID_`; never speak a booking reference.
- After successful cancellation, explain that the Pro Shop processes any eligible prepaid refund and use the hours-aware transfer flow.
