Initialize the following variables:
'date' = string; reservation date; YYYY-MM-DD, with MM-DD-YYYY also accepted; required
'time' = string; reservation tee time; 24-hour HH:MM, with 12-hour time also accepted; required
'current_date' = string; today's date in the facility local timezone; YYYY-MM-DD
'current_datetime' = string; current timestamp in the facility local timezone
'hours_until_tee_off' = number; exact server-computed hours from now until tee-off

Apply these rules in order:
- If hours until tee off is less than 24, return ineligible: "Cancellations must be made at least 24 hours before the tee time. The Pro Shop is currently closed, so please call back after eight o'clock A M tomorrow on this same number for assistance."
- If hours until tee off is exactly 24 or greater, return eligible: "Eligible for cancellation."
- Do not apply any other cancellation criterion.
