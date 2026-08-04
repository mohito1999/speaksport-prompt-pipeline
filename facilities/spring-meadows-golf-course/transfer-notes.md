# Transfer notes

Use only these exact Vapi destination identifiers. Do not include phone numbers
in the prompt.

- `pro_shop`: tee-time assistance, booking modifications and rescheduling,
  cancellations that the AI cannot process, prepaid cancellation refunds,
  course conditions, cart-policy questions, and general golf operations.
- `golf_events`: golf leagues, group outings, tournaments, scrambles, and other
  golf events.
- `wedding_banquet_events`: weddings, banquets, receptions, private functions,
  venue rentals, and non-golf event planning.

Normal integrated transfers follow the reference prompt's two-step confirmation
protocol and first-request Pro Shop deflection guardrail.

The post-cancellation refund offer is a normal two-step transfer: explain that
the Pro Shop can process an eligible prepaid refund, ask whether the caller
wants the transfer, stop and wait, and transfer only after an affirmative reply
in a later turn.
