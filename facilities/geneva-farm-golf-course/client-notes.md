# Client notes

- Geneva Farm Golf Course is in Street, Maryland and uses facility-local
  Eastern Time (`America/New_York`).
- This is one bookable eighteen-hole course. Do not ask the caller to choose a
  course and do not pass a course filter to availability.
- Both nine-hole and eighteen-hole play are supported.
- The inclusive advance-booking window is 10 calendar days. When the local
  current date is July 27, August 6 is eligible and August 7 is not.
- No minimum-player, membership, pass, group, price-class, card-on-file,
  day-of-week, or time-of-day booking eligibility restriction was supplied.
- Preserve and pass the exact course value returned with the selected
  availability result when booking.
- Geneva Farm uses Club Prophet, not ForeUp. Booking references are numeric,
  such as `366135`. Do not prepend or expect `TTID_` during fallback booking
  lookup or cancellation. Keep booking references hidden from callers.
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
