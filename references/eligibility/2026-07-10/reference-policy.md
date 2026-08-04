# Sugarmill Woods eligibility reference fixture

This is a historical, facility-specific reference and is not a global rule.

Evaluate rules in order and stop at the first failed booking-window rule.

1. If at least one `customer_passes` record has `expired: false`, classify the caller as a Golf Member.
2. If `customer_passes` is empty, missing, or contains only records with `expired: true`, classify the caller as a Non-Golf Member.
3. If the caller is a Golf Member and the requested date is more than 30 calendar days after the facility-local current date, return `eligible: false` with the approved Golf Member booking-window reason.
4. If the caller is a Non-Golf Member and the requested date is more than 7 calendar days after the facility-local current date, return `eligible: false` with the approved Non-Golf Member booking-window reason.
5. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The evaluator returns only `eligible` and `reason`.

