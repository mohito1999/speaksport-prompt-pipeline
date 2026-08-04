Initialize the following variables:
'date' = string; requested booking date; YYYY-MM-DD, with MM-DD-YYYY also accepted; required
'time' = string; requested tee time; 24-hour HH:MM, with 12-hour time also accepted; required
'current_date' = string; today's date in the facility local timezone; YYYY-MM-DD
'customer_passes' = list of strings; caller's active pass or membership labels; empty when none

Apply these rules in order:
- If the requested booking date is before the facility-local current date, return ineligible: "That date has already passed."
- Semantically inspect the customer’s passes for an active, unexpired Todd Creek Season Pass.
- If an active Todd Creek Season Pass holder requests a date more than 14 calendar days after the facility-local current date, return ineligible: "Active Todd Creek Season Pass holders may book up to 14 calendar days in advance, including the fourteenth future date."
- If a caller without an active Todd Creek Season Pass requests a date more than 10 calendar days after the facility-local current date, return ineligible: "Public guests may book up to 10 calendar days in advance, including the tenth future date."
- Otherwise, return eligible: "Eligible to book."
- Do not apply any other eligibility criterion based on groups, price class, card-on-file status, number of players, holes, course, time of day, pass-covered days, or any other factor.
