# Client notes

- Facility-local time is Mountain Time (`America/Denver`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.
- Apply the same 14-day booking window to all callers. No distinction is made between members and public players.
- Group Booking Policies:
  - For groups larger than 8 players (9 or more), transfer the caller immediately to the Club House using the `transfer_call-staging` tool. Do not attempt to book these groups.
  - For groups of 5 to 8 players, book consecutive tee times. For example, a group of 6 is booked as a foursome and a twosome; a group of 8 is booked as two foursomes. Retrieve availability, present the consecutive times to the caller, ask them to confirm/pick, and then proceed to book each tee time separately.
- Do not invent additional card-on-file, membership, pass, group, price-class, day-of-week, or time-of-day eligibility restrictions.
