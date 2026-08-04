# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/New_York`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Check caller residency and Recreation ID Card status using `customer_groups` and `customer_passes`:
   - Check if caller is a Resident: perform semantic inference on `customer_groups` and `customer_passes` (e.g. matching "Resident", "Town Resident", "Senior Resident", "25-26 Resident", or any resident designation).
   - Check if caller holds an active Recreation ID Card: perform semantic inference on `customer_passes` (e.g. matching "Rec Card", "Recreation ID", "ID Card", "Rec Pass", "Town Rec Card", or any Recreation ID card designation where `expired: false`).
   - Classify caller as "Resident with Rec ID Card" ONLY if both residency and an active Recreation ID Card are present.
   - Otherwise, classify caller as "Resident without Rec ID Card / Non-Resident".
3. If the caller is a Resident with a Recreation ID Card:
   - Calculate the latest allowed booking date as the facility-local current date plus 14 calendar days.
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Residents with a Recreation ID Card can only book up to 14 days in advance. Please choose a date on or before the latest available booking date."
4. If the caller is a Resident without a Recreation ID Card or a Non-Resident:
   - Calculate the latest allowed booking date as the facility-local current date plus 7 calendar days.
   - If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Non-cardholders and non-residents can only book up to 7 days in advance. Please choose a date on or before the latest available booking date."
5. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The seventh and fourteenth future calendar dates are included in booking windows. For example, when the local current date is July 20:
- For Non-Cardholders / Non-Residents, July 27 is eligible and July 28 is not.
- For Residents with a Rec ID Card, August 3 is eligible and August 4 is not.

The eligibility tool receives `date` as `YYYY-MM-DD` and requested approximate `time` as 24-hour `HH:MM`. Do not send players, holes, riding preference, identity fields, or a course name to eligibility.

After eligibility succeeds, collect players, nine or eighteen holes, and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.
