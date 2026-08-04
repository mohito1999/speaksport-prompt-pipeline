# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/New_York`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Calculate the latest allowed booking date as the facility-local current date plus seven calendar days.
3. If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Tee times can only be booked up to seven days in advance. Please choose a date on or before the latest available booking date."
4. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The seventh future calendar date is included. For example, when the facility-local current date is July 10, July 17 is eligible and July 18 is not.

The eligibility tool receives `date` as `YYYY-MM-DD` and requested approximate `time` as 24-hour `HH:MM`. Do not send players, holes, riding preference, identity fields, or a course name to eligibility.

After eligibility succeeds, collect players, nine or eighteen holes, and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.
