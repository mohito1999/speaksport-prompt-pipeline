# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/New_York`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Check caller member status:
   - If at least one `customer_passes` record has `expired: false` or `customer_groups` contains "member" or "Member" (case-insensitive), classify the caller as a Member.
   - Otherwise, classify the caller as a Public Player (Non-Member).
3. If the caller is a Member:
   - Calculate the latest allowed booking date as the facility-local current date plus 14 calendar days.
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Members can only book up to 14 days in advance. Please choose a date on or before the latest available booking date."
4. If the caller is a Public Player (Non-Member):
   - Calculate the latest allowed booking date as the facility-local current date plus 7 calendar days.
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Public players can only book up to 7 days in advance. Please choose a date on or before the latest available booking date."
5. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The eligibility tool receives `date` as `YYYY-MM-DD` and requested approximate `time` as 24-hour `HH:MM`. Do not send players, holes, riding preference, identity fields, or a course name to eligibility.

After eligibility succeeds, collect players, nine or eighteen holes, and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.
