# Client notes

- Facility-local time is Eastern Time (`America/New_York`).
- Greeting, disclaimer, and announcement are owned by the Vapi runtime variables. Do not invent fixed values when they are empty.
- This is one bookable course. Do not ask the caller to choose a course and do not pass a course filter to availability.
- The facility supports both nine-hole and eighteen-hole tee times; collect `num_holes` after eligibility succeeds.
- Identify member status specifically using the `price_class` variable rather than `customer_passes` or `customer_groups`. Any price class other than standard daily fee / public indicates member booking eligibility (21 days out).
- Do not invent additional card-on-file, membership, pass, group, price-class, day-of-week, or time-of-day eligibility restrictions.
