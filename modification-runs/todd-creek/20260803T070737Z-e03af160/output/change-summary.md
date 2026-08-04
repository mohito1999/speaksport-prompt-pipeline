# Change summary

- Preserved the original knowledge base exactly through the required restoration sentinel.
- Migrated legacy booking workflow to the enabled integrated tools, including facility-local date and time, day-of-week lookup, inventory warm-up, eligibility-before-availability sequencing, exact-time availability re-query, rich availability result handling, and returned-course booking preservation.
- Replaced the legacy single-player Pro Shop handoff with the configured partially-filled-slot presentation rule.
- Added existing-booking lookup and eligible-cancellation workflows, including hidden booking references and ForeUp TTID_ fallback normalization.
- Added separate booking and cancellation eligibility policies with the configured inclusive booking windows and 24-hour cancellation cutoff.
- Applied the after-hours Pro Shop override throughout: no Pro Shop transfer, including tool-failure and profile-update cases; callers are directed to call the same number after eight o'clock A M tomorrow.
- Added weather-tool handling and retained two-step confirmation for the four non-Pro-Shop transfer destinations.
- Removed obsolete legacy booking tool names, legacy payload formats, obsolete cancellation-transfer-only behavior, automatic Pro Shop transfer behavior, and the obsolete returns-500 special behavior.
