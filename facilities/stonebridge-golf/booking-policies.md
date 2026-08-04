# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/Detroit`).

### Booking Eligibility Rules:
1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Calculate the latest allowed booking date as the facility-local current date plus 14 calendar days.
3. If the requested date is after the latest allowed booking date, return `eligible: false` with reason: "Tee times can only be booked up to 14 days in advance. Please choose a date on or before the latest available booking date."
4. If player count (`num_players`) is provided and is less than 2, return `eligible: false` with reason: "Bookings require a minimum of 2 players. Single-player bookings are not permitted."
5. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The fourteenth future calendar date is included in the booking window. For example, when the local current date is July 22, August 5 is eligible and August 6 is not.

### Cancellation Eligibility Rules:
1. When evaluating `get-eligibility-for-cancellation`, check the reservation date and time against the current facility date and time.
2. If the cancellation request is made at least 24 hours prior to the scheduled tee-off time, return `eligible: true` and `reason: "Cancellation eligibility confirmed."`
3. If the cancellation request is within 24 hours of the scheduled tee-off time, return `eligible: false` with reason: "Cancellations within 24 hours of tee-off incur a no-show fee and must be handled directly by the Pro Shop. Transferring to the Pro Shop now."

After booking eligibility succeeds:
- Enforce player count rules: Bookings require a minimum of 2 players (1-player single bookings are not permitted).
- Collect players (minimum 2), nine or eighteen holes, and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.
