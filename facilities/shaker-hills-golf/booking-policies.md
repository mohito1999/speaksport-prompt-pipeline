# Booking policies

## Eligibility policy - current client rule

Evaluate the requested date in the facility timezone (`America/New_York`).

1. If the requested date is before the facility-local current date, return `eligible: false` with reason: "The requested date has already passed. Please choose a future date."
2. Determine caller membership tier using `price_class` via semantic inference:
   - **Junior Member**: `price_class` contains "junior" (case-insensitive).
   - **Platinum Member**: `price_class` contains "platinum" (case-insensitive).
   - **Gold Member**: `price_class` contains "gold" (case-insensitive).
   - **Silver Member**: `price_class` contains "silver" (case-insensitive).
   - **Weekday Hybrid Member**: `price_class` contains both "weekday" and "hybrid" (case-insensitive).
   - **Weekday Member**: `price_class` contains "weekday" (case-insensitive) without "hybrid".
   - **Twilight Hybrid Member**: `price_class` contains both "twilight" and "hybrid" (case-insensitive).
   - **Twilight Member**: `price_class` contains "twilight" (case-insensitive) without "hybrid".
   - **Public Player / Non-Member**: `price_class` is empty, null, or does not match any member category.

3. Evaluate booking window limits based on tier:
   - **Junior Member**: Maximum 24 hours (1 calendar day) in advance under Junior Member benefits. If date > 1 day in advance, return `eligible: false` with reason: "Junior members may only book under junior benefits up to 24 hours in advance. Booking more than 24 hours out will incur standard public rates."
   - **Platinum Member**: Maximum 14 calendar days in advance.
   - **Weekday Hybrid Member**: Maximum 14 calendar days in advance.
   - **Gold Member**: Maximum 12 calendar days in advance.
   - **Twilight Hybrid Member**: Maximum 12 calendar days in advance.
   - **Silver Member**: Maximum 10 calendar days in advance.
   - **Weekday Member**: Maximum 10 calendar days in advance.
   - **Twilight Member**: Maximum 10 calendar days in advance.
   - **Public Player / Non-Member**:
     - 1 to 7 calendar days in advance: `eligible: true` with `reason: "Eligibility confirmed."`
     - 8 to 90 calendar days in advance: `eligible: true` with `reason: "Eligible with a $30 non-refundable advance booking fee per player required for bookings 8 to 90 days in advance."`
     - More than 90 calendar days in advance: `eligible: false` with `reason: "Tee times cannot be booked more than 90 days in advance."`

4. For Member tiers, if the requested date exceeds the tier's max advance window, return `eligible: false` with the tier-specific booking window limit explanation. Otherwise, return `eligible: true` and `reason: "Eligibility confirmed."`

The eligibility tool receives `date` as `YYYY-MM-DD` and requested approximate `time` as 24-hour `HH:MM`. Do not send players, holes, riding preference, identity fields, or a course name to eligibility.

After eligibility succeeds:
- If booking 8 to 90 days in advance as a public player, inform the caller of the $30 non-refundable advance booking fee per player and obtain explicit confirmation before searching availability or booking.
- Collect players, nine or eighteen holes, and riding or walking preference. Search availability without `course` or `course_name`. Preserve every returned `{time, course}` pair and pass the selected slot's exact course to booking.
