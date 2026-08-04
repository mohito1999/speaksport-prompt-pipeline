# Booking policies

## Booking eligibility policy

Initialize the following variables:

'date' = requested booking date.
'time' = requested tee time.
'current_date' = today's date in the facility's local timezone.

Apply these rules in order:

- If the requested booking date is before current date, the caller is not
  eligible. Reason: "That date has already passed."
- No facility-specific advance-booking window, minimum-player requirement,
  membership requirement, pass requirement, card-on-file requirement, or other
  booking restriction has been supplied.
- Do not apply any other eligibility restrictions based on memberships, passes,
  groups, price classes, card-on-file status, player count, course, day of week,
  time of day, or any other criteria.
- If the requested booking date has not passed, the caller is eligible. Reason:
  "Eligible to book."

The eligibility tool receives only the requested date in `YYYY-MM-DD` format
and the requested approximate time in exact twenty-four-hour `HH:MM` format.
Do not send players, holes, riding preference, identity fields, or a course
name to booking eligibility.

After eligibility succeeds, collect players, nine or eighteen holes, and riding
or walking preference. Search availability without `course` or `course_name`.
Preserve every returned `{time, course}` pair and pass the selected slot's exact
course to booking.

## Cancellation eligibility policy

Initialize the following variables:

'date' = reservation date.
'time' = reservation tee time.
'current_date' = today's date in the facility's local timezone.
'current_datetime' = current date and time in the facility's local timezone.
'hours_until_tee_off' = exact number of hours between the current time and the
reservation tee time.

Apply these rules in order:

- A reservation may be cancelled by the AI only when the tee time is at least
  24 hours after current date and time.
- If hours until tee off is less than 24, the reservation is not eligible for
  cancellation. Reason: "I can only process cancellations for tee times that
  are at least 24 hours from now. The Pro Shop can help you with this
  cancellation."
- If hours until tee off is exactly 24 or greater than 24, the reservation is
  eligible for cancellation. Reason: "Eligible for cancellation."
- Do not apply any other cancellation restrictions based on number of players,
  course, passes, card-on-file status, groups, price class, day of week, time
  of day, or any other criteria.

After `cancel-reservation` returns success, tell the caller that if the cancelled
tee time was prepaid and is eligible for a refund, the Pro Shop can process the
refund. Ask whether they would like to be transferred to the Pro Shop. This is
a normal two-step transfer and is not part of the cancellation eligibility
tool response.
