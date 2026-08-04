# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/Detroit`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Calculate the latest allowed booking date as the facility-local current date plus 14 calendar days.
3. If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Tee times can only be booked up to 14 days in advance. Please choose a date on or before the latest available booking date."
4. Evaluate Card on File and Northville Card pass requirements:
   - Check if caller has an active Northville Card by semantically matching the labels in `customer_passes` against "Northville Card", "Northville Pass", "Northville Member Card", or an equivalent Northville designation. The runtime list already contains active passes only; do not look for an `expired` property.
   - If the caller holds a qualifying active Northville-designated pass, they are eligible to book even if `customer_has_card_on_file` is false.
   - If the caller does NOT hold an active Northville Card and `customer_has_card_on_file` is false, return `eligible: false` with reason: "Bookings require a credit card on file or an active Northville Card. Please contact the Golf Shop to update your card on file."
5. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The fourteenth future calendar date is included in the booking window. For example, when the local current date is July 22, August 5 is eligible and August 6 is not.

The eligibility tool receives `date` as `YYYY-MM-DD`, requested approximate `time` as 24-hour `HH:MM`, and `num_players` as the requested player count. Collect player count before eligibility for this facility because the minimum-player rule is part of eligibility. Do not send holes, riding preference, identity fields, or a course name to eligibility.

After eligibility succeeds:
- Collect nine or eighteen holes and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.

## Cancellation eligibility policy - current client rule

Initialize cancellation eligibility using the reservation date, reservation tee time, facility-local current date and time, and the server-computed exact hours until tee off.

- The AI may cancel a reservation only when the tee time is at least 24 hours after the facility-local current date and time.
- If hours until tee off is less than 24, return ineligible with reason: "Cancellations must be made at least 24 hours before the tee time. Cancellations within 24 hours may be subject to a no-show fee. Please contact the Golf Shop for assistance."
- If hours until tee off is exactly 24 or greater than 24, return eligible with reason: "Eligible for cancellation."
- Do not apply any other cancellation restrictions based on number of players, course, passes, card-on-file status, groups, price class, day of week, time of day, or any other criteria.
