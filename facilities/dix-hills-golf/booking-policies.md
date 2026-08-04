# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/New_York`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Check caller residency status using `customer_groups` and `customer_passes`:
   - Perform semantic inference on caller group and pass names (e.g. "Resident", "Senior Resident", "Town Resident", "25-26 Resident", or any permutation containing "resident").
   - If any active `customer_passes` record or `customer_groups` entry indicates resident status, classify the caller as a Resident.
   - Otherwise, classify the caller as a Non-Resident.
3. If the caller is a Resident:
   - Calculate the latest allowed booking date as the facility-local current date plus 14 calendar days.
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Residents can only book up to 14 days in advance. Please choose a date on or before the latest available booking date."
4. If the caller is a Non-Resident:
   - Calculate the latest allowed booking date as the facility-local current date plus 7 calendar days.
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Non-residents can only book up to 7 days in advance. Please choose a date on or before the latest available booking date."
5. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The seventh and fourteenth future calendar dates are included in booking windows. For example, when the local current date is July 20:
- For Non-Residents, July 27 is eligible and July 28 is not.
- For Residents, August 3 is eligible and August 4 is not.

The eligibility tool receives `date` as `YYYY-MM-DD` and requested approximate `time` as 24-hour `HH:MM`. Do not send players, holes, riding preference, identity fields, or a course name to eligibility.

After eligibility succeeds, collect players, nine or eighteen holes, and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.
