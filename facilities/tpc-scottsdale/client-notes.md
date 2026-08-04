# Client notes

- TPC Scottsdale is in Scottsdale, Arizona and uses facility-local time
  (`America/Phoenix`).
- This is a non-integrated, SMS-only booking flow.
- The official booking portal is `https://tpcscottsdale.ezlinksgolf.com/`.
- TPC Scottsdale has two courses: Stadium Course and Champions Course.
- Do not apply booking-window or eligibility rules and do not generate booking
  or cancellation eligibility backoffice artifacts.
- Standard tee-time callers should be offered the official booking link by SMS.
  Explicit consent is required before calling `send_sms`.
- Do not invoke `send_sms` and ask for consent in the same response.
- The assistant may answer weather questions using
  `get-weather-forecast-staging`.
- Existing booking changes, cancellations, and other reservation assistance are
  transfer-only. Determine whether the caller needs the Stadium Shop or
  Champions Shop before offering the transfer.
- Preserve all configured person and department transfer destinations exactly.
  Do not infer phone numbers or substitute unconfigured identifiers.
- Greeting, disclaimer, and announcement are supplied by runtime variables. Do
  not invent fixed values when they are empty.
