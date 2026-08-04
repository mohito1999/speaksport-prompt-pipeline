# Client notes

- Cascade Golf Course is in Cascade, Idaho and uses facility-local Mountain
  Time (`America/Boise`).
- This is one bookable course. Do not ask the caller to choose a course and do
  not pass a course filter to availability.
- The facility is a nine-hole course that also supports eighteen-hole play.
  Collect whether the caller wants nine or eighteen holes after eligibility.
- The client supplied no facility-specific booking restrictions. Do not invent
  an advance-booking window, minimum-player rule, membership or pass rule,
  card-on-file requirement, price-class rule, or other booking restriction.
- Preserve and pass the exact course value returned with the selected
  availability result when booking.
- The AI may process a cancellation when the tee time is at least 24 hours from
  the current facility-local date and time.
- If the tee time is less than 24 hours away, cancellation eligibility must
  return false with the exact supplied reason and the caller must be offered a
  normal two-step transfer to `pro_shop`.
- After a successful cancellation, explain that the Pro Shop can process a
  refund if the tee time was prepaid and eligible for one, then ask whether the
  caller would like a transfer. Do not imply that cancellation automatically
  issues a refund.
- Booking modifications and rescheduling remain transfer-only requests for the
  Pro Shop.
- Greeting, disclaimer, and announcement are supplied by Vapi runtime
  variables. Do not invent fixed values when they are empty.
