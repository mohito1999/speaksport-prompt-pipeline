# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/Denver`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Calculate the latest allowed booking date as the facility-local current date plus 14 calendar days.
3. If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Tee times can only be booked up to 14 days in advance. Please choose a date on or before the latest available booking date."
4. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The fourteenth future calendar date is included in the booking window. For example, when the local current date is July 10, July 24 is eligible and July 25 is not.

The eligibility tool receives only `date` as `YYYY-MM-DD` and requested approximate `time` as 24-hour `HH:MM`. Do not send players, holes, riding preference, identity fields, or a course name to eligibility.

After eligibility succeeds, collect players, nine or eighteen holes, and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.
