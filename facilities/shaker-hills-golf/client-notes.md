# Client notes

- Facility-local time is Eastern Time (`America/New_York`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.
- Membership tiers are identified dynamically via the `price_class` variable using semantic matching:
  - **Platinum Member**: 14-day advance booking window.
  - **Weekday Hybrid Member**: 14-day advance booking window.
  - **Gold Member**: 12-day advance booking window.
  - **Twilight Hybrid Member**: 12-day advance booking window.
  - **Silver Member**: 10-day advance booking window.
  - **Weekday Member**: 10-day advance booking window.
  - **Twilight Member**: 10-day advance booking window.
  - **Public Player**: Standard 7-day advance booking window (no fee).
  - **Public 8–90 Days Advance**: Public players can book 8 to 90 days in advance subject to a **$30 non-refundable upcharge per player**. The assistant MUST inform the caller of this $30/player fee and confirm they accept it before searching availability or executing a booking.

- **Junior Membership Policy**:
  - Junior Members may only book tee times under their junior member benefits up to 24 hours in advance (strict policy).
  - If a Junior Member (or parent booking for a junior) attempts to book more than 24 hours in advance, inform them that booking >24 hours out will incur standard public junior rates rather than junior member benefits.
  - Junior memberships are deeply discounted and intended for utilizing unused tee times within 24 hours of play.

- Do not invent additional card-on-file, membership, pass, group, price-class, day-of-week, or time-of-day eligibility restrictions.
