# Codex Context Handoff: SpeakSport Facility Prompt Pipeline

## 1. Assignment

Build a local, Python-based project that creates production-ready SpeakSport facility onboarding packages. Read `docs/PRD.md` completely before designing or implementing the application.

The system accepts a facility website, an integrated or non-integrated reference prompt, client policies, transfer configuration, tool configuration, and runtime-variable definitions. It crawls the website through Firecrawl, uses an LLM through OpenRouter, and produces a validated package.

The most important output is a single `unified-vapi-prompt.md` file. It must contain the facility's core shell, complete knowledge base, and logic module together so an operator can paste the entire file directly into Vapi.

For integrated facilities, also produce a separate `eligibility-backoffice-policy.md`.

Do not publish anything to Vapi or the SpeakSport backoffice in the first release.

## 2. Security warning

A Firecrawl key was pasted into the earlier planning conversation. Treat it as compromised. Do not copy it into source code, documentation, fixtures, shell history, or generated files. The product owner must rotate it before running the application.

All credentials must be supplied locally through environment variables:

```dotenv
FIRECRAWL_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_MAX_COST_USD=
```

Create `.env.example` with blank values and ensure `.env` is ignored by Git. Never ask the product owner to paste live credentials into a prompt when they can set them locally after the project scaffold exists.

## 3. Business context

SpeakSport provisions voice AI receptionists for golf facilities. Each facility requires a long, bespoke system prompt containing:

- Identity and voice persona.
- TTS-safe response conventions.
- Greeting and runtime-variable behavior.
- Facility knowledge.
- Booking or booking-link workflow.
- Transfers.
- Enabled tools and failure handling.
- Edge cases.

Two main workflow types exist.

### Integrated

The receptionist can check caller eligibility, search tee-time inventory, and complete a booking. Sugarmill Woods is the supplied reference example.

### Non-integrated

The receptionist cannot access the tee sheet. It directs standard bookings to the online portal, normally by SMS, and transfers special requests when required. Bobby Jones Golf Course is the supplied reference example.

The reference prompts demonstrate desired richness and architecture, but they are not automatically correct in every detail. They contain facility-specific data and some inconsistent or historical conventions. Treat them as versioned reference inputs and apply approved global rules and current tool contracts over stale examples.

## 4. Supplied source materials

The current planning workspace contains:

- Integrated reference prompt, Sugarmill Woods: `/Users/mohitmotwani/.codex/attachments/3ab137ce-6ab1-40d0-81eb-8b4e83cba16f/pasted-text.txt`
- Non-integrated reference prompt, Bobby Jones: `/Users/mohitmotwani/.codex/attachments/558047c2-c8af-435a-b759-fed5b52b0c7c/pasted-text.txt`
- Historical operations guide: `/Users/mohitmotwani/Downloads/SpeakSport AI Receptionist_ The Ultimate Customer Success & Prompting Guide (1).pdf`
- Product requirements: `docs/PRD.md`

Copy the two reference prompts into the new project's versioned `references/` tree before using them. Preserve the originals as read-only source fixtures. Do not rely indefinitely on attachment paths because they are not durable project storage.

The user also supplied this eligibility example for Sugarmill Woods:

- A caller is a Golf Member if at least one `customer_passes` record has `expired: false`.
- A caller with no passes, or only expired passes, is a Non-Golf Member.
- Golf Members can book up to 30 days ahead.
- Non-Golf Members can book up to 7 days ahead.
- Deny outside the appropriate window with the corresponding approved reason.
- Otherwise return `eligible: true` and `reason: "Eligibility confirmed."`

Store a cleaned version as an eligibility reference fixture. Improve its structure so each condition, return value, and reason forms one coherent rule block or line.

## 5. Non-negotiable product decisions

1. The primary output is one unified Vapi prompt with the knowledge base embedded.
2. Standalone knowledge files are supporting artifacts, not substitutes for the embedded knowledge base.
3. The prompt must not know or mention backend endpoint versioning.
4. Vapi logical tool names are configuration.
5. Reference prompts and pipeline instructions are replaceable, versioned inputs.
6. Do not hard-code one reference prompt into Python source.
7. Do not hard-code OpenRouter model selection into generation logic.
8. Eligibility business rules belong in the backoffice policy. The receptionist prompt only orchestrates the eligibility tool and handles its response.
9. Facts must have provenance and conflicts must be surfaced.
10. Human approval is required before deployment.
11. No automatic Vapi or backoffice publishing in the first release.

## 6. Current integrated tool behavior

The Vapi tools interface is configured to call current backend endpoints. Generated prompts should use the configured logical tool names only.

### Eligibility

- Call as soon as requested date and approximate requested time are known.
- Call before asking for group size, holes, riding/walking, identity details, or inventory.
- Pass `date` as `YYYY-MM-DD`.
- Pass `time` as 24-hour `HH:MM`.
- Backend obtains caller context from the phone-linked customer profile.
- Response contains `eligible` and `reason`.
- Stop the booking flow on false and communicate the returned reason naturally.

### Availability

- `date` is required.
- `when`, `num_players`, `num_holes`, and course filtering are supported according to the tool contract.
- Course filtering is normally omitted for a single-course facility.
- For multi-course sites, pass the exact selected course value from the initialized course list.
- Results are course-tagged slots, for example `{ "time": "1:48 PM", "course": "Eagle" }`.
- Preserve the time/course association.

### Booking

- Use the exact selected availability slot.
- Convert the selected time to 24-hour `HH:MM` for the tool.
- Pass the exact returned course when the configured contract requires it.
- Required identity fields are first name, last name, and email.
- Required booking fields include date, exact time, players, and holes.
- Riding is passed when collected and supported.
- Do not claim success until the tool returns success.

Do not embed the label “v6” in generated prompts, UI copy, or validation rules. It may appear only in developer migration notes if ever needed, not as receptionist knowledge.

## 7. Firecrawl implementation baseline

Use the official Firecrawl Python SDK if it supports all needed v2 fields cleanly; otherwise isolate direct HTTP calls in the Firecrawl adapter.

Default crawl settings:

```python
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions

app = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])

scrape_options = ScrapeOptions(
    only_main_content=True,
    max_age=172800000,
    parsers=["pdf"],
    formats=["markdown"],
)

crawl_result = app.crawl(
    normalized_url,
    sitemap="include",
    crawl_entire_domain=False,
    limit=50,
    scrape_options=scrape_options,
)
```

The service must record the crawl job ID and support status checks through `GET https://api.firecrawl.dev/v2/crawl/{id}`. The status response can include `scraping`, `completed`, or `failed`, progress counts, data, and a `next` URL for more results. Implement polling, retry/backoff, pagination, resume, and local caching.

Do not assume the pasted example returns all data synchronously. Verify actual installed SDK behavior and write adapter tests around it.

## 8. OpenRouter implementation baseline

OpenRouter exposes OpenAI-like request/response schemas and an official Python SDK. Use an adapter so the rest of the application depends on a small internal interface rather than a vendor SDK.

Use strict structured outputs for intermediate stages whenever the configured model supports them. Examples include:

- Extracted fact inventory.
- Conflict report.
- Prompt section plan.
- Generated section bundle.
- Validation findings.

Use a deterministic assembler to create the final Markdown. Do not rely on regex to recover multiple long sections from an unconstrained response when a schema can return named fields.

Model selection must be configurable. Reproducible runs should pin the model slug. Record requested model, returned model, token usage, and cost when available.

## 9. Reference-prompt observations

### 9.1 Shared strengths to preserve

Both supplied prompts demonstrate:

- `<core-shell>`, `<knowledge-base>`, and `<logic-module>` architecture.
- Rich facility-specific knowledge.
- Strong voice/TTS instructions.
- Greeting, disclaimer, and announcement behavior.
- One-question-at-a-time guidance.
- Transfer routing.
- Explicit scope of capabilities.
- Tool failure and call ending behavior.

### 9.2 Integrated reference strengths

The Sugarmill prompt demonstrates:

- Eligibility before inventory.
- Player, hole, and cart collection after eligibility.
- Course-tagged availability.
- Caller name and email confirmation.
- Conversion of returned 12-hour time into the booking tool's 24-hour format.
- Weather, day-of-week, inventory warm-up, and transfer tools.
- A large embedded facility knowledge base.

### 9.3 Non-integrated reference strengths

The Bobby Jones prompt demonstrates:

- SMS booking-link behavior.
- Dynamic-rate deflection to the online portal.
- Special-case transfers such as Youth on Course.
- Extensive facility, dining, events, instruction, and history content.
- Factual-grounding instructions.

### 9.4 Issues not to copy blindly

The application must surface or normalize these issues through canonical configuration:

- Some sections require explicit verbal transfer confirmation, while later examples transfer immediately.
- The Bobby Jones reference includes phone numbers in the prompt even though another operating convention says the transfer tool should own them.
- Some prompt logic repeats raw curly-brace variables instead of referring to initialized semantic names.
- The Sugarmill eligibility example includes `course_name`, while the current eligibility brief says only date and time are needed.
- Availability examples use free-form phrases such as “after 2 PM,” while the current backend contract should explicitly define accepted `when` values.
- Tool-failure fallbacks sometimes attempt another transfer without confirmation, which may conflict with the mandatory transfer protocol.
- Bobby Jones contains duplicate “General Manager” headings and a special test behavior that should not leak to unrelated facilities.
- Dated events and seasonal rules can become stale and must be marked time-sensitive.

Do not silently decide these global-policy questions from one reference. Expose them in configuration and require owner confirmation.

## 10. Recommended implementation sequence

### Phase 1: Scaffold and contracts

1. Create the Python project with a `src/` layout.
2. Add typed configuration and intermediate models.
3. Add CLI commands and run manifests.
4. Add secret handling, redaction, and `.gitignore`.
5. Create versioned reference, runtime-variable, and tool-contract registries.
6. Implement deterministic prompt assembly and structural validation first.

### Phase 2: Firecrawl

1. Implement Firecrawl adapter.
2. Add URL normalization.
3. Add start, poll, pagination, resume, and caching.
4. Preserve raw immutable page records.
5. Normalize and deduplicate Markdown.
6. Test entirely with mocked API responses before using live credits.

### Phase 3: LLM extraction

1. Implement OpenRouter adapter.
2. Add structured-output capability validation.
3. Extract facts with provenance.
4. Detect conflicts and create open questions.
5. Cache by content and instruction hash.

### Phase 4: Generation

1. Generate integrated and non-integrated section bundles.
2. Assemble the unified Vapi prompt.
3. Generate eligibility policy for integrated mode.
4. Create transfer and source artifacts.

### Phase 5: QA

1. Add deterministic validators.
2. Add independent LLM critique.
3. Add bounded repair passes.
4. Add diffs, approval checklist, and package command.
5. Run sanitized Sugarmill and Bobby Jones golden fixtures.

Do not begin with a GUI. Build and stabilize the CLI and artifact model first. A small local UI can be added after the workflow is reliable.

## 11. Minimum acceptance demonstration

The first end-to-end demonstration should show:

1. A fresh facility directory is initialized.
2. A mocked or low-cost crawl returns multiple Markdown pages and a PDF-derived page.
3. Facts are extracted with source identifiers.
4. A conflict between a client note and website fact is reported.
5. Integrated mode produces a unified prompt plus eligibility policy.
6. Non-integrated mode produces a unified prompt without integrated booking tools.
7. The final unified prompt includes its knowledge base.
8. Tool and runtime-variable validators run.
9. No secret appears anywhere in the run directory.
10. A second unchanged run reuses cached stages.
11. Changing a reference prompt version produces a clear diff and new manifest.

## 12. Inputs still required from the product owner

Before live pilot completion, obtain the following. The owner should place secrets locally rather than pasting them into Codex messages.

### Required for building

- The two reference prompt files copied into durable project paths.
- The historical operations guide, if it should remain a reference.
- A canonical runtime-variable registry with exact placeholder names.
- A canonical logical tool registry with exact Vapi tool names.
- Current tool schemas, accepted argument values, and result shapes.
- The one approved transfer protocol and its allowed exceptions.
- Decision on whether phone numbers belong in prompts or only in Vapi destination configuration.
- The default OpenRouter model slug and budget limit.

### Required for the first live facility

- Facility name and website URL.
- Integrated or non-integrated mode.
- Single-course or multi-course configuration.
- Exact course values from the facility configuration when applicable.
- Booking and eligibility rules.
- Cancellation/modification rules.
- Walking, riding, cart, guest, and card-on-file rules.
- Greeting, disclaimer, and announcement.
- Enabled tools.
- Transfer destination identifiers and responsibilities.
- Booking URL for non-integrated mode.
- Client notes, documents, and known exclusions.
- A human approver for the final prompt and eligibility policy.

### Local environment setup by the owner

- A newly rotated Firecrawl key in `.env`.
- An OpenRouter key in `.env` with an appropriate credit limit.
- Permission to spend Firecrawl credits and OpenRouter inference costs during live tests.

## 13. Suggested first instruction to Codex

Use the following as the kickoff request after creating or opening the new project:

> Read `docs/PRD.md` and `docs/CODEX_HANDOFF.md` completely. Inspect the integrated and non-integrated reference prompts that I have placed under `references/`. Build Milestone 1 only: scaffold the typed Python project, implement configuration models, reference and tool-contract versioning, CLI skeleton, run manifests, secret redaction, deterministic unified-prompt assembly, and initial validators. Do not call Firecrawl or OpenRouter yet. Add tests and show me the proposed configuration schemas and CLI behavior before proceeding to Milestone 2.

This staged instruction keeps the initial build reviewable and prevents live API spending before the foundations and contracts are agreed.

## 14. Definition of handoff completeness

Codex has enough context to begin when it has:

- This handoff document.
- The PRD.
- Durable copies of both reference prompts.
- A clear answer to the global decisions listed in the PRD.
- Blank `.env.example` values and locally configured real credentials only when live API work begins.

