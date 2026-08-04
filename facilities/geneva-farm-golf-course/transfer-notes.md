# Transfer notes

Use only these exact Vapi destination identifiers. Do not include phone numbers
in the prompt.

- `pro_shop`: tee-time assistance, booking modifications and rescheduling,
  cancellations that the AI cannot process, prepaid cancellation refunds,
  course conditions, and general golf operations.
- `events`: golf outings, tournaments, weddings, private events, and event
  planning.
- `restaurant`: restaurant hours, dining questions, reservations, and food and
  beverage inquiries.
- `business_office`: billing, administrative, account, and business-office
  inquiries.

Normal integrated transfers follow the reference prompt's two-step confirmation
protocol and first-request Pro Shop deflection guardrail.

The post-cancellation refund offer is a normal two-step transfer: explain that
the Pro Shop can process an eligible prepaid refund, ask whether the caller
wants the transfer, stop and wait, and transfer only after an affirmative reply
in a later turn.
