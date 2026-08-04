# Client notes

- Facility-local time is Eastern Time (`America/Detroit`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.

- Player & Cancellation Rules:
  - Minimum Player Count: All bookings MUST have a minimum of 2 players. Single-player (1 player) bookings are not permitted. Pass `num_players` to booking eligibility.
  - Cancellation Window:
    - Cancellations made at least 24 hours prior to tee-off time can be processed by the AI system (`get-eligibility-for-cancellation` returns `eligible: true`).
    - Cancellations within 24 hours of tee-off time incur a no-show fee and CANNOT be cancelled by the AI agent (`get-eligibility-for-cancellation` returns `eligible: false`). The assistant must immediately transfer the caller to `pro_shop`.

- Rates & Facility Services Schedule:

  - Green Fees & Rates:
    - Fridays, Saturdays, Sundays & Holidays:
      - 18 Holes Standard All Day: $45 – $99 (Packs starting at $72)
      - 9 Holes Standard All Day: $40 – $55
    - Mondays – Thursdays:
      - 18 Holes Standard All Day: $39 – $79 (Packs starting at $43)
      - 18 Holes Seniors All Day: $50 (Fixed rate applied at check-in)
      - 9 Holes Standard All Day: $35 – $50
      - 9 Holes Seniors All Day: $35 (Fixed rate applied at check-in)
    - Senior Rate Note: Senior discounts are fixed prices applied at check-in (standard rates display online, discount applied at counter).
    - Seasonal Note: Spring and Fall rates are discounted from posted standard ranges.

  - Punch Card / Loyalty Packs:
    - 10 or 25 prepaid 18-hole round punch cards at discounted rates.

  - Driving Range (Public facility, bent grass tees, practice putting greens, chipping bunker):
    - Tokens purchased in Pro Shop.
    - Small (30 balls): $6.50
    - Medium (60 balls): $12.00
    - Large (90 balls): $16.00

  - Rental Club Sets (Standard sets are Strata/older; Premium are Ping, Titleist, Callaway demos; Left-handed available):
    - Standard Sets: 9 holes $26, 18 holes $39.
    - Premium Sets: 9 holes $37, 18 holes $52.

- Do not invent additional card-on-file, membership, pass, group, price-class, day-of-week, or time-of-day eligibility restrictions.
