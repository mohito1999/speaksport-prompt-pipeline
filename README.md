# SpeakSport Facility Prompt Pipeline

This local Python application produces review-ready SpeakSport facility onboarding packages. It crawls a facility website through Firecrawl, extracts source-grounded facts through OpenRouter, generates integrated or non-integrated prompt sections, assembles one unified Vapi prompt, validates it, and creates a human-review package. It never publishes to Vapi or SpeakSport backoffice.

## Local setup

Python dependencies live in the project-local `.venv`:

```bash
uv sync --extra dev
source .venv/bin/activate
speaksport init
pytest
```

If `uv` is unavailable:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Do not paste credentials into chat, source files, fixtures, or commands. Copy `.env.example` to the ignored `.env`, rotate the previously exposed Firecrawl key, and set credentials locally.

## Local Control Room

The easiest way to use the pipeline is the local Control Room. On macOS,
double-click `start-control-room.command` in the project folder. It opens a
guided interface for new facilities, existing-prompt updates, configuration
editing, explicit external-processing approval, live run progress, and prior
run artifacts.

You can also start it from the project virtual environment:

```bash
source .venv/bin/activate
speaksport ui
```

Open `http://127.0.0.1:8765` and press Control-C when finished. The service is
local-only by default and does not expose `.env` credentials. See
[`docs/CONTROL_ROOM.md`](docs/CONTROL_ROOM.md) for the short operator guide.

## Current CLI

```text
speaksport init
speaksport facility create <slug> --name <name> --website <https-url> --mode <mode> --timezone <iana-zone> --tee-sheet <foreup|club_prophet|other>
speaksport facility show <slug>
speaksport manifest create <slug>
speaksport references list
speaksport references activate <mode> <version>
speaksport assemble <slug> --core-shell <file> --knowledge-base <file> --logic-module <file>
speaksport validate <slug> <unified-prompt.md>
speaksport crawl <slug>
speaksport crawl <slug> --resume [--run-id <run-id>]
speaksport extract <slug> [--run-id <run-id>]
speaksport generate <slug> [--run-id <run-id>]
speaksport run <slug>
speaksport diff <slug> [--against <run-id>]
speaksport package <slug> [--run-id <run-id>]
speaksport ui [--host 127.0.0.1] [--port 8765]
```

`speaksport run` is the fastest path: it starts a resumable Firecrawl job, stores immutable raw pages, normalizes and deduplicates them, extracts a provenance-bearing fact inventory, generates the prompt package, and runs deterministic validation. Successful LLM stage results are cached by input and instruction hash.

If extraction or generation fails after crawling, do not delete the run or start another crawl. Resume from the preserved raw pages with:

```bash
speaksport generate <slug> --run-id <run-id>
```

The pipeline reserves thirty-five percent of the configured OpenRouter run ceiling for final prompt generation. Facility configuration and client policy files are extracted once, while website pages are processed in balanced batches.

For a non-integrated facility, pass `--booking-url`. For a multi-course facility, pass `--course` once per exact runtime course value.

New integrated facility scaffolds require `--tee-sheet`. This records the GMS
explicitly instead of inferring it from booking-reference wording:

```yaml
tee_sheet: club_prophet # or foreup / other
```

When `club_prophet` is selected, the scaffold automatically enables
`get_customer_records` and `confirm_identity`. Generated prompts initialize
`{{identity_confirmed}}` and add the mandatory on-call identity flow. When that
value is false, profile-dependent booking, pricing, and membership handling
first looks up all phone-matched records and lets the caller choose; no match
continues as a new guest. One match still requires confirmation, multiple
matches are never ranked or auto-selected, only an email ending/domain may be
spoken, and identity-tool errors continue without a transfer. When the value is
true, the stored identity is reused without asking again. ForeUp and `other`
tee sheets never receive this flow.

Integrated facilities can enable existing-booking lookup and cancellation by adding these exact logical names to `enabled_tools` in `facility.yaml`:

```yaml
enabled_tools:
  - get-bookings
  - get-eligibility-for-cancellation
  - cancel-reservation
```

`get-bookings` may be enabled by itself for lookup-only service. Cancellation eligibility and cancellation must be enabled together with all three tools; booking modifications and rescheduling remain transfer-only.

Integrated generation writes booking eligibility to `eligibility-backoffice-policy.md`. When `get-eligibility-for-cancellation` is enabled, it also writes `cancellation-eligibility-backoffice-policy.md`. Both use the compact variable-initialization and ordered-rule format defined in `config/eligibility-conventions.yaml`; these backoffice decision prompts are separate from the caller-facing Vapi prompt.

## Configuration ownership

The tool contract, runtime-variable registry, transfer behavior, course handling, and no-phone-number rule were confirmed by the product owner beginning on 2026-07-10, with booking lookup and cancellation capabilities added on 2026-07-22. The configured OpenRouter model is `openai/gpt-5.6-terra` with a $1.50 per-run ceiling. The historical operations guide is retained as non-authoritative context; newer contracts and owner instructions override conflicts.

Reference prompts are immutable versioned inputs. Their metadata stores a SHA-256 content hash, and `speaksport references list` fails if an active reference was edited in place. Create a new version directory for every revision.

## Facility workflow

1. Create a facility directory with `speaksport facility create`.
2. Complete `facility.yaml` and the Markdown policy/note files.

First-request Golf Shop or Pro Shop deflection is opt-in per facility:

```yaml
transfer_policy:
  first_shop_transfer_deflection: false
  allow_after_hours_transfers: false
```

Use `true` only when the assistant should respond to the caller's first general
or shop-transfer request with: “Is there something I can assist you with
first?” It must never claim that the shop is busy. If the caller declines or
repeats the request, the assistant transfers without asking for confirmation
again. With `false` (the default), a caller's direct transfer request is already
consent and transfers immediately when the destination is open. A transfer the
assistant merely offers still requires the caller to accept before it executes.

After-hours voicemail transfers are opt-in. Keep
`allow_after_hours_transfers: false` when a closed facility must not receive
transfers. Set it to `true` when callers may still be transferred after hours
to leave a voicemail. In that mode, the assistant explains that the requested
team is closed and the call may reach voicemail before following the normal
transfer consent rules. The Control Room exposes the same setting as
**After-hours voicemail transfers**, and both scaffold commands support
`--allow-after-hours-transfers`.

Every generated prompt initializes `{{current_status}}`, `{{opening_time}}`,
and `{{closing_time}}`. Current status changes transfer behavior according to
the facility setting above; it never restricts the assistant itself. Booking,
availability, identity resolution, eligibility, booking lookup, cancellation,
weather, SMS, and every other enabled non-transfer flow continue normally 24/7.

Single-player availability filtering is also configured per facility:

```yaml
availability_policy:
  single_player_requires_partially_filled_slot: false
```

Use `true` when a solo caller may be offered only returned slots where
`spots_remaining` is less than four. With `false` (the default), a solo caller
may be offered any otherwise valid returned slot, including one with all four
spots remaining. The setup command supports the matching
`--single-player-requires-partially-filled-slot` option.

Availability pricing is configured independently per facility:

```yaml
availability_pricing:
  speaksport_per_booking_model: false
  booking_fee_application: none # none, all_callers, or conditional
  disclose_booking_fee_when_applied: false
  booking_fee_rules: [] # required only for conditional
```

For facilities outside the SpeakSport per-booking model, returned base fields
are quoted: `base_price_per_player` for walking and
`base_price_per_player_riding` for riding. Per-booking facilities may also
return `price_per_player` and `price_per_player_riding`, which include the
booking fee. Conditional fee rules may use price class, active passes, or
customer groups. Prompts quote only returned fields and follow the configured
fee application and disclosure policy.

Integrated prompts treat every availability slot as a single record containing
`time`, `course`, `spots_remaining`, and its returned pricing fields. They do
not ask riding or walking before availability because riding is not an
availability argument; they ask after exact slot selection and before booking,
unless facility policy fixes `riding`. An empty availability list means no tee times are
available for the full requested date under the selected holes and course
criteria, not merely that no times are close to the requested clock time.
3. Add the rotated Firecrawl and OpenRouter keys to the local `.env`.
4. Run `speaksport run <slug>` or execute `crawl`, `extract`, and `generate` separately.
5. Review `runs/<slug>/<run-id>/output/`, especially the prompt, QA report, open questions, and approval checklist.

Human approval remains mandatory. `VALIDATED` never means `APPROVED_FOR_VAPI`.

## Existing prompt modification workflow

Existing live prompts use a separate workflow. It does not crawl a website and
does not invoke or alter the new-facility `speaksport run` path.

```bash
speaksport modify create legacy-club \
  --name "Legacy Club" \
  --source-prompt /path/to/current-vapi-prompt.md \
  --website https://example.com/ \
  --timezone America/New_York \
  --tee-sheet foreup \
  --single-player-requires-partially-filled-slot
```

This creates `modifications/<slug>/` with:

- `original-prompt.md`: immutable input copy of the current production prompt;
- `facility.yaml`: desired current tools, destinations, and facility policies;
- `modification.yaml`: preservation settings and optional context files;
- `update-notes.md`: free-form customer-requested logic, routing, knowledge, or
  workflow changes.

By default, the original `<knowledge-base>` block is restored byte-for-byte:

```yaml
preservation:
  knowledge_base: exact
  identity_and_voice: preserve
  transfer_destinations: preserve
  unmentioned_behavior: preserve_when_compatible
```

Set `knowledge_base: revise` only when the update explicitly changes facility
facts. Add any approved supplemental files to `additional_context_files` in
`modification.yaml`. Then run:

```bash
speaksport modify check legacy-club
speaksport modify run legacy-club
speaksport modify diff legacy-club
```

`modify check` is local-only and verifies the source prompt, preservation block,
tool compatibility, references, and input files without calling Firecrawl or
OpenRouter.

Each run is written under `modification-runs/<slug>/<run-id>/`, separate from
new-facility runs. Its review package contains the updated prompt, both booking
and cancellation eligibility policies when enabled, a knowledge-base
preservation hash report, a unified Markdown diff, a side-by-side HTML diff, a
change summary, QA findings, and an approval checklist.

## Provider references

- [Firecrawl crawl request](https://docs.firecrawl.dev/api-reference/endpoint/crawl-post)
- [Firecrawl crawl status and pagination](https://docs.firecrawl.dev/api-reference/endpoint/crawl-get)
- [OpenRouter API schema](https://openrouter.ai/docs/api/reference/overview)
- [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
