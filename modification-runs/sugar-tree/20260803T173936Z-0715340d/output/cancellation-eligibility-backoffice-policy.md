Initialize the following variables:
'date' = string; reservation date; YYYY-MM-DD, with MM-DD-YYYY also accepted; required.
'time' = string; reservation tee time; 24-hour HH:MM, with 12-hour time also accepted; required.
'num_players' = integer; number of players on the reservation.
'course_name' = string; optional course or tee-sheet name for multi-course facilities.
'booking_reference' = string; optional booking reference for authoritative GMS lookup.
'booking_date_readable' = string; reservation date formatted server-side as weekday plus full date.
'current_date' = string; today’s date in the facility local timezone; YYYY-MM-DD.
'current_datetime' = string; current timestamp in the facility local timezone.
'hours_until_tee_off' = number; exact server-computed hours from now until tee-off.
'customer_passes' = list of strings; caller’s active pass or membership labels; empty when none.
'customer_has_card_on_file' = boolean; whether the caller has a saved card on file.
'price_class' = string; caller’s GMS price class when known.
'customer_groups' = list of strings; caller’s GMS group memberships.

Apply these rules in order:
- Return ineligible with the reason: “The Pro Shop must process tee-time cancellations for Sugar Tree Golf Club.”
- Do not apply any other cancellation criterion, including reservation timing, hours until tee off, memberships, passes, groups, price classes, card-on-file status, course, player count, or any other factor.
