# Non-integrated generation instructions

Status: active. Owner-confirmed on 2026-07-10.

Generate facility-specific content using the selected reference for architecture and depth, never as an authoritative source of facility facts.

- Return named sections for the core shell, knowledge base, logic module, and any intentional closing core-shell blocks.
- Include this exact date-and-time sentence, substituting the facility's configured IANA timezone in both expressions: `Today is {{"now" | date: "%A, %B %d, %Y", "<facility timezone>"}}, and the current time is {{"now" | date: "%I:%M %p", "<facility timezone>"}}.` Preserve natural spoken-date rules and interpret “next Tuesday” as the nearest future Tuesday.
- Read `transfer_policy.first_shop_transfer_deflection` from the facility configuration. Include first-request Golf Shop or Pro Shop deflection only when it is `true`. When it is `false`, do not resist, delay, or gatekeep the first request; follow the normal configured transfer-confirmation protocol immediately.
- Keep facts in the knowledge base, global receptionist behavior in the core shell, and workflows in the logic module.
- Treat the approved fact inventory as a coverage checklist, not source material to summarize aggressively. Include every caller-useful informational fact supported by it. Preserve every distinct membership tier, price, spouse or junior price, benefit, booking window, discount, rate, hour, date range, season, age threshold, fee, tax, gratuity, capacity, amenity, staff role, course detail, policy, exception, restriction, penalty, event term, instruction detail, historical fact, and accolade. Never replace detailed supported options with phrases such as “various memberships,” “rates vary,” or a representative sample when the inventory contains the specifics.
- Organize and deduplicate the knowledge base for natural lookup, but do not merge facts when doing so loses conditions or distinctions. Rich facilities should produce a correspondingly rich knowledge base; 1,500 to 3,500 words or more is normal when the evidence supports it. Never pad or invent details merely to reach a length.
- Preserve membership, pass, golf-rate, booking-policy, facility-policy, staff, instruction, and operational details at high resolution. For long catering menus, repeated event calendars, hole-by-hole narratives, or other bulk reference material, retain useful package names, prices, fees, capacities, dates, and representative or defining inclusions without reproducing every dish, duplicate event occurrence, or source-table cell. This is loss-aware consolidation, not permission to reduce major facility offerings to generic summaries.
- Official-site facts are approved informational evidence unless contradicted by a higher-authority source or explicitly listed in `ignored_facts`. Retain changeable information and label it as “published,” “listed,” or with its supplied year or season when appropriate. Do not move supported facts into “open questions” merely because current confirmation could be useful.
- Omit phone numbers from the prompt under the current global convention even if they appear in the fact inventory. Omit source provenance and internal confidence labels from caller-facing knowledge.
- Before returning, audit the completed knowledge base against the fact inventory item by item. Use `generation_notes` to state the inventory fact count and enumerate every caller-useful fact intentionally omitted with the exact reason. Do not silently omit facts to shorten the prompt.
- Explain that standard tee times and live rates are handled through the configured online portal.
- Offer the booking link by SMS and wait for consent before invoking `send_sms`.
- Do not search inventory, book tee times, or generate an eligibility policy.
- Mention only logical tool names and runtime variables from active registries.
- Route special booking types only according to current client policy and the approved transfer protocol.
- Use `transfer_call-staging` with exact configured destination identifiers and no phone numbers.
- Do not copy names, prices, destinations, phone numbers, events, exceptions, or test behavior from the reference facility.
- Surface conflicts and missing inputs as open questions instead of inventing an answer.
