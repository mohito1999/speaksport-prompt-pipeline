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
- If the number of players is fewer than 2, return ineligible with the reason: “Sugar Tree does not allow single-player tee-time bookings through the automated system. The Pro Shop may be able to pair you with an existing group.”
- If the number of players is greater than 4, return ineligible with the reason: “Automated tee-time bookings are limited to four players. The Pro Shop can help with larger groups or multiple tee times.”
- Otherwise, return eligible with the reason: “Eligible to book.”
- Do not apply any other eligibility criterion, including advance-booking windows, memberships, passes, groups, price classes, card-on-file status, course, day of week, time of day, or any other factor.
