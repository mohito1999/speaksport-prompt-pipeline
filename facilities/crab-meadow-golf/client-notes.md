# Client notes

- Facility-local time is Eastern Time (`America/New_York`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.
- Residency and Recreation ID Card eligibility:
  - Residents with an active Recreation ID Card (inferred from `customer_passes` indicating a Rec ID Card where `expired: false` and `customer_groups`/`customer_passes` indicating resident status) receive a 14-day booking window.
  - Residents without a Recreation ID Card and Non-Residents receive a 7-day booking window.

- General Facility Policies:
  - All bookings include an additional $4 reservation fee per person.
  - An additional 3% fee applies when paying with a credit card.
  - Callers are requested to arrive for check-in at least 30 minutes prior to their tee time.
  - Single riders will be paired together prior to teeing off.
  - Early Bird Special & Super Twilight times require golf carts.
  - Cancellations are required 24 hours in advance of a tee time to avoid a Cancellation Fee.
  - Arriving at the course with fewer players than booked incurs a No Show Fee per person.
  - No Show and Cancellation Fees are not charged during inclement weather.

- Green Fees & Rates Breakdown:

  - June – August:
    - Weekdays (Mon–Thu):
      - Morning (Open–11:00): Cardholder $35, Resident $51, Non-Resident $51, Senior $27, Early Bird $24 (available first 90 mins).
      - Afternoon (11:00–15:00): Resident $35, Non-Resident $35, Senior $27.
      - Twilight (15:00–18:00): Resident $29, Non-Resident $29, Junior $17, Senior $19.
      - Super Twilight (18:00–close): Special $26 (includes cart).
    - Weekends (Fri–Sun):
      - Morning (Open–11:00): Cardholder $39, Resident $56, Non-Resident $56, Early Bird $29.
      - Afternoon (11:00–15:00): Resident $37, Non-Resident $37.
      - Twilight (15:00–18:00): Resident $29, Non-Resident $29.
      - Super Twilight (18:00–close): Special $26 (includes cart).

  - May & September:
    - Weekdays (Mon–Fri):
      - Morning (Open–11:00): Cardholder $35, Resident $51, Non-Resident $51, Senior $27, Early Bird $24.
      - Afternoon (11:00–15:00): Resident $35, Non-Resident $35, Senior $27.
      - Twilight (15:00–17:00): Resident $29, Non-Resident $29, Junior $17, Senior $19.
      - Super Twilight (17:00–close): Special $26 (includes cart).
    - Weekends (Sat–Sun):
      - Morning (Open–11:00): Cardholder $39, Resident $56, Non-Resident $56, Early Bird $29.
      - Afternoon (11:00–15:00): Resident $37, Non-Resident $37.
      - Twilight (15:00–17:00): Resident $29, Non-Resident $29.
      - Super Twilight (17:00–close): Special $26 (includes cart).

  - April & October:
    - Weekdays (Mon–Fri):
      - Morning (Open–11:00): Cardholder $35, Resident $51, Non-Resident $51, Senior $27, Early Bird $24.
      - Afternoon (11:00–15:00): Resident $35, Non-Resident $35, Senior $27.
      - Twilight (15:00–16:00): Resident $29, Non-Resident $29, Junior $17, Senior $19.
      - Super Twilight (16:00–close): Special $26 (includes cart).
    - Weekends (Sat–Sun):
      - Morning (Open–11:00): Cardholder $39, Resident $56, Non-Resident $56, Early Bird $29.
      - Afternoon (11:00–15:00): Resident $37, Non-Resident $37.
      - Twilight (15:00–16:00): Resident $29, Non-Resident $29.
      - Super Twilight (16:00–close): Special $26 (includes cart).

  - November – March:
    - Weekdays (Mon–Fri):
      - Morning (Open–11:00): Cardholder $35, Resident $51, Non-Resident $51, Senior $27, Early Bird $24.
      - Afternoon (11:00–13:00): Resident $35, Non-Resident $35, Senior $27.
      - Twilight (13:00–15:00): Resident $29, Non-Resident $29, Junior $17, Senior $19.
      - Super Twilight (15:00–close): Special $26 (includes cart).
    - Weekends (Sat–Sun):
      - Morning (Open–11:00): Cardholder $39, Resident $56, Non-Resident $56, Early Bird $29.
      - Afternoon (11:00–13:00): Resident $37, Non-Resident $37.
      - Twilight (13:00–15:00): Resident $29, Non-Resident $29.
      - Super Twilight (15:00–close): Special $26 (includes cart).

  - Cart Fees & Extra Fees:
    - Morning & Afternoon cart fee: $22.
    - Twilight cart fee: $18.
    - Super Twilight specials include cart.
    - Reservation fee: $4 per person.
    - Credit Card Surcharge: 3%.
    - Early Bird Special: Available during the first 90 minutes of play.
