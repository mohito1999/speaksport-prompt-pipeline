# SpeakSport customer update generator

This folder turns one dashboard screenshot and one recent call export into a
consistent, branded two-page customer update.

## For each facility

1. Create `inputs/<facility-slug>/`.
2. Add `dashboard.png` and `calls.csv`.
3. Copy `inputs/radrick_farms/update.json` and replace the facility name,
   dashboard metrics, selected call excerpts and report date.
   Set `operating_model` to either `integrated` or `non_integrated`.
4. Run the call analyzer to surface candidate proof calls:

   ```text
   python analyze_calls.py inputs/<facility-slug>/calls.csv --output inputs/<facility-slug>/call_analysis.json
   ```

5. Generate the document:

   ```text
   python generate_customer_update.py inputs/<facility-slug>/update.json outputs/<facility-slug>/performance-update.docx
   ```

6. Render and visually review both pages before sending.

Use official dashboard values as shown. Do not add together headline and
after-hours figures unless the dashboard definition explicitly confirms they
are separate populations. Remove personal phone numbers and email addresses
from every customer-facing excerpt.

## Model-specific reporting

- **Integrated:** lead with completed bookings, booking revenue and booking
  eligibility. For reports prepared from 31 July 2026 onward, the headline KPI
  grid contains only Calls handled, Bookings completed, Booking revenue and
  Time saved. The after-hours strip contains only Calls, Bookings and Booking
  revenue. Proof calls may show availability search and booking confirmation.
- **Non-integrated:** never imply SpeakSport books the tee time. Lead with
  booking intent captured, booking-link delivery, appropriate transfers and
  questions resolved.
- **Booking Opportunities Captured:** describe this as a recently introduced
  measurement until it has a full historical period. It counts calls where the
  caller expressed an intent to book, play or reserve and SpeakSport took the
  correct next action by sending the booking link or transferring to staff.

Unless instructed otherwise, use 31 July 2026 as the prepared date for the
remaining reports in this customer-update run.
