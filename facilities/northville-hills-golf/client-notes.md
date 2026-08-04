# Client notes

- Facility-local time is Eastern Time (`America/Detroit`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.

- Player & Card Requirements:
  - Minimum player count: All bookings MUST have a minimum of 2 players. Single-player (1 player) bookings are not permitted.
  - Card on File Rule: Bookings require the caller to have a card on file (`customer_has_card_on_file: true`).
  - Card Exception: If `customer_passes` contains a label semantically matching an active Northville Card, Northville Pass, Northville Member Card, or equivalent Northville-designated pass, the caller IS eligible to book even if `customer_has_card_on_file` is false. The runtime list contains active pass and membership labels only; do not look for an `expired` property.

- Green Fees & Rates Schedule:

  - Standard Peak Season Rates:
    - Fridays, Saturdays, Sundays & Holidays:
      - 18 Holes Standard All Day: $65 – $115 (As low as $65)
      - 9 Holes Standard All Day: $35 – $70
    - Monday – Thursday:
      - 18 Holes Standard All Day: $55 – $85 (As low as $50 online)
      - 18 Holes Seniors (Mon–Thu All Day): $55 (Fixed rate; lock at $50 online)
      - 9 Holes Standard All Day: $55

  - Opening Rates (Through April 30th):
    - Fridays, Saturdays, Sundays & Holidays:
      - 18 Holes Standard All Day: $65 – $85 (As low as $65)
      - 9 Holes Standard All Day: $35 – $60
    - Monday – Thursday:
      - 18 Holes Standard All Day: $50 – $70 (As low as $50)
      - 18 Holes Seniors (Mon–Thu All Day): $55 (Fixed rate; lock at $50 online)
      - 9 Holes Standard All Day: $35 – $55

  - Fall Rates (Starting October 12th):
    - Fridays, Saturdays, Sundays & Holidays:
      - 18 Holes Standard All Day: $65 – $85 (As low as $65)
      - 9 Holes Standard All Day: $35 – $60
    - Monday – Thursday:
      - 18 Holes Standard All Day: $50 – $70 (As low as $50)
      - 18 Holes Seniors (Mon–Thu All Day): $55 (Fixed rate; lock at $50 online)
      - 9 Holes Standard All Day: $35 – $55

  - Senior Rate Note: Senior rates are fixed at $55 for Mon–Thu 18 holes all day.

- Do not invent additional card-on-file, membership, pass, group, price-class, day-of-week, or time-of-day eligibility restrictions.
