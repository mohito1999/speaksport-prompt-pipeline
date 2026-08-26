# Client notes

- Facility-local time is Pacific Time (`America/Los_Angeles`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.
- Distinguish booking window eligibility between members (14 days inclusive) and public players (7 days inclusive) based on caller membership status.
- Do not invent additional card-on-file, membership, pass, group, price-class, day-of-week, or time-of-day eligibility restrictions.
- Use the full ForeUp integrated tool suite: booking eligibility, availability,
  booking, booking lookup, cancellation eligibility, cancellation, enhanced
  date/day resolution, inventory warm-up, weather, and transfer.
- Initialize `{{current_status}}`, `{{opening_time}}`, and `{{closing_time}}`.
  When current status is `after_hours`, never invoke a transfer. Explain that
  the requested team is closed, offer to help, and say the caller may call back
  at Opening Time.
- A caller's direct transfer request is already consent. Do not ask them to
  confirm the same transfer again. When the assistant offers a transfer without
  a direct request, ask once and wait for the caller to accept.
- Gold Hills enables the first Pro Shop assistance check. On the first
  open-hours Pro Shop or general transfer request, ask: "Is there something I
  can assist you with first?" Never say that the shop is busy. If the caller
  says no or repeats the transfer request, transfer immediately without another
  confirmation question.
- Single callers may only be offered partially filled slots with
  `spots_remaining` below four.
- Gold Hills does not charge callers a SpeakSport booking fee. Use only returned
  base walking and riding prices, ask riding after slot selection, and never
  invent missing pricing.
