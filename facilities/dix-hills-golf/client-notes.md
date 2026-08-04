# Client notes

- Facility-local time is Eastern Time (`America/New_York`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.
- Identify residency status dynamically from caller `customer_groups` and `customer_passes`. Perform semantic inference to match any resident permutations (e.g. "Senior Resident", "25-26 Resident", "Town Resident", etc.). Residents receive a 14-day booking window while Non-Residents receive a 7-day booking window.
- Do not invent additional card-on-file, membership, pass, group, price-class, day-of-week, or time-of-day eligibility restrictions.
