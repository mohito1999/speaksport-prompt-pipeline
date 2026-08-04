Initialize the following variables:
'date' = string; requested booking date; YYYY-MM-DD, with MM-DD-YYYY also accepted; required.
'time' = string; requested tee time; 24-hour HH:MM, with 12-hour time also accepted; required.
'num_players' = integer; requested number of players.
'course_name' = string; optional course or tee-sheet name for multi-course facilities.
'booking_date_readable' = string; requested date formatted server-side as weekday plus full date.
'current_date' = string; today’s date in the facility local timezone; YYYY-MM-DD.
'customer_passes' = list of strings; caller’s active pass or membership labels; empty when none.
'customer_has_card_on_file' = boolean; whether the caller has a saved card on file.
'price_class' = string; caller’s GMS price class when known.
'customer_groups' = list of strings; caller’s GMS group memberships.

Apply these rules in order:
- If the requested booking date is before the facility-local current date, return ineligible with the reason: “That date has already passed.”
- If the number of players is greater than 4, return ineligible with the reason: “Automated tee-time bookings are limited to four players. The Pro Shop can help with larger groups or multiple tee times.”
- If customer passes, price class, or customer groups indicate the caller is a member (run AI inference to determine member status as terminology may vary; for passes, ensure expired is false indicating an active member) and the requested booking date is more than 14 days in advance from the facility-local current date (e.g., if today is August 3rd, booking past August 17th), return ineligible with the reason: “Members can only book up to 14 days in advance.”
- If the caller is not a member (public player) and the requested booking date is more than 7 days in advance from the facility-local current date (e.g., if today is August 3rd, booking past August 10th), return ineligible with the reason: “Public players can only book up to 7 days in advance.”
- Otherwise, return eligible with the reason: “Eligible to book.”
- Do not apply any other eligibility criterion, including card-on-file status, course, day of week, time of day, or any other factor.
