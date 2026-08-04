# Client notes

- Twin Oaks Golf Course is in San Marcos, California and uses facility-local
  Pacific Time (`America/Los_Angeles`).
- This is an integrated, single-course booking flow.
- The first-request Pro Shop transfer deflection is disabled. Never tell a
  caller the shop is busy or make them ask twice. Every normal transfer still
  requires the standard two-step offer, stop, and later affirmative consent.
- The JC Golf site contains pages for many unrelated courses. Only Twin Oaks
  facts are in scope. Do not use another JC Golf course's course details,
  rates, policies, staff, amenities, or booking rules.
- The separate official Weddings at Twin Oaks site is an approved source for
  wedding, celebration, banquet, and venue facts.
- Never ask whether the caller wants nine or eighteen holes. Twin Oaks supports
  eighteen-hole bookings only, so pass 18 to availability and booking.
- Always collect number of players before availability searches.
- Never ask riding or walking. Rates include a cart, so pass riding as true.
- SoCal and Senior discounts are applied at check-in and do not affect booking
  eligibility.
- Standard JC Players Card holders receive an inclusive eight-day window.
  Public guests, JC 20/30 Club participants, and JC Junior Player Card holders
  receive an inclusive seven-day window.
- Use semantic inference over caller price class only to recognize the standard
  JC Players Card. Do not let a loose match accidentally give the 20/30 or
  Junior programs an eighth day.
- Beyond the applicable phone-booking window, explain the prepaid,
  non-refundable online option up to 60 days and offer the booking link by SMS.
  Ask for consent and wait before calling `send_sms`.
- Twin Oaks uses Club Prophet numeric booking references. Never introduce
  `TTID_`.
- After successful cancellation, explain that eligible prepaid refunds are
  handled by the Pro Shop and offer a normal two-step transfer.
- Greeting, disclaimer, and announcement come from runtime variables; do not
  invent fixed values when they are empty.
