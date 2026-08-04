# SpeakSport Facility Prompt Pipeline

## Product Requirements Document

**Status:** Build-ready draft  
**Last updated:** 2026-07-10  
**Product owner:** SpeakSport  
**Intended implementation:** Local Python application operated through Codex  

## 1. Executive summary

SpeakSport needs a repeatable, auditable way to onboard a new golf facility and generate the production prompt artifacts used by its Vapi voice receptionist. The current process combines website crawling, manually supplied client policies, reference prompts, prompt engineering, and manual quality checks. It works, but it is time-consuming and vulnerable to inconsistency, stale tool instructions, omitted knowledge, invented facts, and accidental regressions when reference prompts evolve.

The product described here is a local Python application that accepts a facility website and structured onboarding inputs, crawls up to 50 pages through Firecrawl, creates a source-grounded facility knowledge base, and uses an LLM through OpenRouter to produce review-ready outputs.

The primary production output is one unified Vapi system prompt. It must contain the facility-specific `<core-shell>`, `<knowledge-base>`, and `<logic-module>` content in a single Markdown file that can be pasted directly into Vapi. For integrated facilities, the pipeline must also produce a separate backoffice eligibility policy for the booking eligibility evaluator. Supporting files preserve source material, transfer configuration, generation metadata, validation results, and unresolved questions.

Reference prompts are versioned inputs to the pipeline, not behavior hard-coded into Python. SpeakSport must be able to replace or revise an integrated or non-integrated reference prompt and update its generation instructions without redesigning the application.

## 2. Problem statement

The existing workflow has several sources of operational risk:

- Website information is crawled and interpreted manually.
- Client-supplied rules can conflict with website content or be omitted.
- Integrated and non-integrated facilities require substantially different booking logic.
- Reference prompts contain both desirable conventions and facility-specific exceptions.
- Tool behavior can change behind stable Vapi tool names.
- A valid prompt must preserve extensive facility knowledge while remaining usable in a live voice call.
- Transfer logic, runtime variables, tool arguments, and caller-detail collection are easy to make inconsistent.
- A single generation pass can hallucinate facts, omit policies, duplicate sections, or create contradictions.
- Existing outputs are not always reproducible from a known set of source files and versions.

The new pipeline must reduce these risks without preventing a human operator from reviewing and editing the final prompt.

## 3. Product goals

### 3.1 Primary goals

1. Generate a complete, facility-specific unified Vapi prompt from a website, client notes, facility configuration, and a selected reference prompt.
2. Support both integrated and non-integrated facility workflows.
3. For integrated facilities, generate a separate eligibility backoffice policy containing direct, operational rules.
4. Preserve source provenance so factual claims can be traced to a website URL or client-provided input.
5. Keep tool contracts, runtime variables, generation instructions, and reference prompts versioned and independently updateable.
6. Detect contradictions, unsupported claims, missing required inputs, and structural violations before the output is marked ready.
7. Keep all secrets out of source control and generated artifacts.
8. Make each run reproducible and comparable with previous runs.

### 3.2 Secondary goals

- Make prompt updates easier to review through Markdown diffs.
- Support rerunning only the stages affected by changed inputs.
- Track model usage, cost information when returned, prompt versions, and crawl metadata.
- Allow future validators and output types without restructuring the core pipeline.
- Establish Sugarmill Woods and Bobby Jones as initial golden-reference fixtures.

## 4. Non-goals for the first release

- Automatically publishing prompts to Vapi.
- Automatically editing Vapi tool configurations.
- Automatically publishing eligibility policies to SpeakSport backoffice.
- Calling or changing production phone agents.
- Managing Twilio sender pools.
- Replacing human review before production deployment.
- Building a full multi-user cloud application.
- Automatically updating existing production prompts through the Slack prompt-edit workflow.
- Crawling authenticated private portals in the first release.

These may be considered later, but the first release ends with a locally generated, validated, human-reviewable package.

## 5. Users and core use cases

### 5.1 Primary user

A SpeakSport operator onboarding a new golf facility or regenerating a facility prompt after reference conventions change.

### 5.2 Primary use cases

1. Create a new integrated facility package.
2. Create a new non-integrated facility package.
3. Recrawl a facility website and identify knowledge changes.
4. Regenerate using a newer reference prompt or pipeline instruction version.
5. Compare a new prompt with the last approved prompt.
6. Update facility inputs without recrawling unchanged web content.
7. Validate an edited unified prompt before it is pasted into Vapi.

## 6. Core product principles

### 6.1 The unified prompt is the main artifact

The final Vapi prompt must be one self-contained Markdown document. Supporting knowledge-base files exist for source management and review, but the final `<knowledge-base>` must be embedded in `unified-vapi-prompt.md`.

### 6.2 Endpoint versions are implementation details

The generated prompt must use the logical tool names configured for the Vapi assistant. It must not mention endpoint versions such as “v6.” Endpoint selection is handled in the Vapi tools interface.

### 6.3 Reference prompts are influential but not infallible

Reference prompts establish style, depth, architecture, and known-good conventions. They may also contain historical behavior, facility-specific exceptions, or contradictions. Canonical tool contracts and approved pipeline rules take precedence over stale examples. Conflicts must be reported rather than silently copied.

### 6.4 Facts and behavior are separate

- Facility facts belong in the knowledge base.
- Global receptionist conventions belong in the core shell.
- Operational workflows and facility-specific action logic belong in the logic module.
- Eligibility decision rules belong in the separate backoffice policy, not duplicated in receptionist reasoning.

### 6.5 Human approval remains mandatory

The application can label an output `VALIDATED`, but only a human can label it `APPROVED_FOR_VAPI`.

## 7. Workflow variants

### 7.1 Integrated facility

An integrated receptionist can check booking eligibility, search tee-sheet availability, and book a selected tee time.

Required production artifacts:

- Unified Vapi prompt with embedded knowledge base.
- Eligibility backoffice policy.
- Transfer destination specification.
- QA report and source manifest.

Required integrated booking sequence:

1. Understand the tee-time request.
2. Collect requested date and approximate requested time.
3. Resolve relative dates and format date/time for the tool.
4. Invoke the configured eligibility tool immediately.
5. Do not ask for players, holes, riding/walking, email, or search inventory before eligibility succeeds.
6. If ineligible, stop the booking flow, communicate the tool-provided reason naturally, and offer an allowed alternative or confirmed transfer.
7. If eligible, collect players, holes, and riding/walking preference as required by the facility.
8. Search availability with the configured availability tool.
9. Treat every result as a paired `{time, course}` slot.
10. Present only tool-returned options.
11. After the caller selects a slot, collect or confirm first name, last name, and email according to the approved caller-detail convention.
12. Book using the exact selected time and its associated returned course.
13. Do not state that booking succeeded until the booking tool confirms success.
14. Communicate confirmation details and any returned amount due or booking reference when policy requires it.

### 7.2 Non-integrated facility

A non-integrated receptionist cannot search or book tee-sheet inventory. It directs standard tee-time requests to the online booking experience, normally by offering to send an SMS link.

Required production artifacts:

- Unified Vapi prompt with embedded knowledge base.
- Transfer destination specification.
- QA report and source manifest.

Required non-integrated booking sequence:

1. Explain that standard tee times and live rates are handled through the online booking portal.
2. Offer to send the configured booking link by SMS.
3. Wait for caller consent before invoking SMS if that is the approved convention.
4. Use only configured runtime variables and the configured SMS tool.
5. Handle SMS failure with an approved spoken fallback.
6. Route special booking types, such as Youth on Course or events, according to client rules and transfer protocol.

The non-integrated pipeline does not generate an eligibility policy unless explicitly enabled for a future hybrid workflow.

## 8. Inputs

### 8.1 Global configuration

Global configuration must be stored in version-controlled files and include:

- Approved prompt architecture.
- Integrated generation instructions.
- Non-integrated generation instructions.
- Runtime-variable registry.
- Logical tool registry and argument contracts.
- Transfer-protocol convention.
- Voice/TTS conventions.
- Factual-grounding rules.
- Validator configuration.
- Default model configuration.

### 8.2 Versioned reference assets

At minimum:

- `references/integrated/<version>/reference-prompt.md`
- `references/non-integrated/<version>/reference-prompt.md`
- `references/eligibility/<version>/reference-policy.md`
- `references/integrated/<version>/generation-instructions.md`
- `references/non-integrated/<version>/generation-instructions.md`

Each reference version must have metadata containing:

- Version identifier.
- Created date.
- Status: draft, active, deprecated.
- Summary of changes.
- Compatible tool-contract version.
- Content hash.

### 8.3 Facility intake

Each facility must have a human-editable YAML configuration. Required fields:

- Facility slug and display name.
- Primary website URL including scheme.
- Facility timezone.
- Integration type: `integrated` or `non_integrated`.
- Course configuration: `single_course` or `multi_course`.
- Exact runtime course values if known.
- Selected reference versions.
- Enabled logical tool names.
- Greeting, disclaimer, and announcement values or ownership notes.
- Booking URL for non-integrated facilities when applicable.
- Transfer destination identifiers and responsibilities.
- Client-provided booking and operating rules.
- Cancellation/modification policy.
- Walking, riding, and cart policies.
- Caller-detail requirements.
- Allowed source URLs or paths to exclude.
- Any facts that must be ignored even if found online.

The intake validator must stop before crawling if the website URL is invalid, the integration type is missing, or a selected reference does not exist.

### 8.4 Client notes and policies

The application must accept Markdown files in addition to YAML fields. This prevents complex policies from being forced into short configuration values.

Recommended files:

- `client-notes.md`
- `booking-policies.md`
- `transfer-notes.md`
- `known-exclusions.md`

### 8.5 Secrets and runtime environment

Secrets must be provided through environment variables or an untracked `.env` file:

- `FIRECRAWL_API_KEY`
- `OPENROUTER_API_KEY`

Optional configuration:

- `OPENROUTER_MODEL`
- `OPENROUTER_FALLBACK_MODELS`
- `OPENROUTER_MAX_COST_USD`
- `OPENROUTER_TIMEOUT_SECONDS`

No API key may appear in Python source, committed configuration, logs, prompt outputs, fixtures, or QA reports.

## 9. Firecrawl integration requirements

### 9.1 Default crawl configuration

The default must match the approved SpeakSport approach:

```python
ScrapeOptions(
    only_main_content=True,
    max_age=172800000,
    parsers=["pdf"],
    formats=["markdown"],
)
```

The crawl request must use:

- `sitemap="include"`
- `crawl_entire_domain=False`
- `limit=50`
- External links disabled.
- Subdomains disabled unless facility configuration explicitly enables them.
- Robots.txt respected.

The URL must be normalized to include `https://` when the user omits the scheme.

### 9.2 Asynchronous crawl lifecycle

The crawl service must:

1. Start a crawl and record its job ID immediately.
2. Persist the job ID and request configuration locally.
3. Poll `GET /v2/crawl/{id}` with bounded exponential backoff.
4. Handle `scraping`, `completed`, and `failed` statuses.
5. Display completed-page progress to the user.
6. Follow the response `next` URL until all result pages are retrieved when result size exceeds the response limit.
7. Preserve partial status and allow a later resume after interruption.
8. Handle 429 responses with retry guidance and a maximum wait policy.
9. Never print the authorization header or key.

### 9.3 Crawl storage

Every crawled page must be stored as an immutable raw record containing:

- Source URL.
- Canonical URL if available.
- Page title.
- HTTP status metadata.
- Crawl timestamp.
- Markdown content.
- Content hash.
- Crawl job ID.
- Firecrawl request options hash.

The raw layer must not be modified. Normalized and synthesized files must be written separately.

### 9.4 Crawl filtering and cleaning

The normalizer must:

- Remove repeated navigation, cookie, footer, and boilerplate content where Firecrawl leaves it behind.
- Deduplicate identical and near-identical pages.
- Preserve headings, tables, lists, dates, prices, names, policies, and relevant links.
- Flag pages with errors or suspiciously little content.
- Mark dated events and seasonal information as time-sensitive.
- Preserve PDF-derived page content and source attribution.
- Exclude irrelevant careers, privacy, legal boilerplate, generic blog archives, and unrelated domains by configurable rules.

## 10. Knowledge extraction and provenance

### 10.1 Structured fact model

Before prompt generation, the LLM must extract facts into a schema rather than generating the final prompt directly from a large undifferentiated crawl.

Each fact should contain:

- Category.
- Subject.
- Fact text.
- Normalized value where useful.
- Source type: website, PDF, client note, facility configuration, or reference rule.
- Source identifier and URL/file.
- Source excerpt kept short for review.
- Time sensitivity.
- Confidence.
- Conflict group identifier when applicable.

Core categories include:

- Facility identity and location.
- Hours.
- Staff and departments.
- Course layouts and starting courses.
- Practice facilities.
- Rates and memberships.
- Booking rules.
- Cancellation and modification rules.
- Cart and walking rules.
- Dress code and etiquette.
- Dining.
- Events and outings.
- Instruction.
- Rentals.
- Accessibility.
- Weather and frost rules.
- Transfer responsibilities.
- Other frequently asked questions.

### 10.2 Source precedence and conflicts

The pipeline must not silently choose between contradictory sources.

Default authority order:

1. Explicit client-provided policy marked current.
2. Approved facility intake configuration.
3. Current client-provided documents.
4. Current official facility website content.
5. Reference prompt examples, which are never authoritative for another facility's facts.

When two sources at the same authority level conflict, generation must pause or omit the disputed fact and place it in `open-questions.md`.

### 10.3 Knowledge-base generation

The generated knowledge base must:

- Be complete enough to answer expected facility calls.
- Retain relevant nuance without copying irrelevant website prose.
- Avoid promotional padding that reduces retrieval clarity.
- Use TTS-safe formatting for values likely to be spoken.
- Avoid unsupported implications.
- Contain no tool behavior or internal pipeline instructions except facility facts that affect caller answers.
- Be embedded in the final unified prompt.

## 11. LLM integration through OpenRouter

### 11.1 Provider abstraction

Implement an `LLMClient` interface so OpenRouter is the first provider but not inseparable from the pipeline. The implementation may use the official OpenRouter Python SDK, direct HTTP, or the OpenAI SDK configured with OpenRouter's base URL. Provider-specific details must remain inside the adapter.

### 11.2 Model configuration

- The model slug must be configuration, never hard-coded into generation logic.
- A run manifest must record the requested model and the actual returned model identifier when available.
- The user must be able to change the model without code changes.
- Model capability checks must verify support for required parameters such as structured outputs.
- Optional fallback models must be explicit and recorded.
- Automatic model aliases may be supported, but reproducibility mode must require a pinned model slug.

### 11.3 Structured outputs

Use strict JSON Schema outputs for intermediate stages such as fact extraction, conflict detection, prompt section planning, and QA findings. OpenRouter supports `response_format` with `json_schema` for compatible models. The application must verify model support and fail clearly if a required feature is unavailable.

The final Markdown may be returned as fields inside a structured object:

- `core_shell`
- `knowledge_base`
- `logic_module`
- `eligibility_policy`
- `transfer_destinations`
- `open_questions`
- `generation_notes`

A deterministic assembler must create the unified prompt from validated section fields.

### 11.4 Reliability and cost controls

- Use request timeouts.
- Retry transient 429 and 5xx failures with bounded exponential backoff and jitter.
- Do not retry schema or authentication failures blindly.
- Record token usage and cost data when provided.
- Support a per-run spending ceiling.
- Cache successful stage results by input hash.
- Use low-variance generation settings for extraction and validation.
- Never log hidden model reasoning.
- Store the exact prompts sent to the LLM with secrets removed.

## 12. Tool-contract registry

Tool behavior must be stored in a versioned configuration file. Tool names are logical names exposed in Vapi; endpoint versions must not appear in generated prompts.

### 12.1 Eligibility contract

Current intended behavior:

- Invoke as soon as requested booking date and approximate time are known.
- Invoke before collecting players, holes, riding/walking, identity details, or searching inventory.
- Required arguments: `date` in `YYYY-MM-DD` and `time` in 24-hour `HH:MM`.
- Backend obtains customer context such as passes, groups, price class, and card-on-file status.
- Result contains `eligible` and a human-readable `reason`.
- If false, stop the booking flow.
- If true, continue.

The logical tool name is facility/configuration dependent.

### 12.2 Availability contract

Current intended behavior:

- Required: `date`.
- Optional: `when`, `num_players`, `num_holes`, and `course`/`course_name` according to the configured tool schema.
- Prefer a supported daypart value or exact `HH:MM` for `when`; do not invent unsupported free-form expressions.
- For single-course facilities, normally omit course filtering.
- For multi-course facilities, pass the exact course value from the initialized course list when the caller chose a course.
- Never invent or normalize a course name beyond the exact configured value.
- Each returned slot is a `{time, course}` pair.

### 12.3 Booking contract

Current intended behavior:

- Required: date, exact selected time in 24-hour `HH:MM`, number of players, number of holes, first name, last name, and email.
- Course should be the exact `course` paired with the selected availability slot; it may be omitted only when the configured contract explicitly permits omission for a single-course site.
- Riding is passed when collected and supported.
- Never claim success before a successful tool result.
- Preserve booking reference and amount-due values when returned and when the approved prompt convention requires them to be spoken.

### 12.4 Other tools

The registry must support:

- Day-of-week lookup.
- Inventory warm-up when applicable.
- Weather forecast.
- SMS sending.
- Call transfer.
- Facility-specific tools.

Each contract must define the logical name, required/optional arguments, formats, result shape, invocation preconditions, failure handling, and compatible facility modes.

## 13. Prompt generation and assembly

### 13.1 Generation inputs

The generator must receive:

- Selected reference prompt and generation instructions.
- Canonical global conventions.
- Facility configuration.
- Approved structured facts.
- Client policies.
- Tool-contract version.
- Runtime-variable registry.
- Transfer destinations.
- Previous approved prompt when doing an update.

### 13.2 Unified prompt structure

The assembler must produce one file with balanced tags and a consistent order:

```markdown
<core-shell>
...
</core-shell>

<knowledge-base>
...
</knowledge-base>

<logic-module>
...
</logic-module>

<core-shell>
...
</core-shell>
```

Multiple core-shell blocks are allowed because the supplied references use them, but the validator must ensure they are intentional, balanced, non-contradictory, and ordered. A future canonical reference may consolidate them without requiring code changes.

### 13.3 Prompt length

Target approximately 4,000 to 5,000 words when the facility has enough relevant content. Completeness and operational clarity take precedence over padding. The system must report word count but must not invent or duplicate content merely to hit the target.

### 13.4 Facility-specific adaptation

The model must adapt, not mechanically replace names:

- Choose relevant transfer destinations.
- Include only enabled tools.
- Include eligibility logic only through tool orchestration in the receptionist prompt.
- Include only facility-supported capabilities.
- Preserve distinctive voice and facility identity.
- Avoid copying facts, names, rates, destinations, or exceptions from reference facilities.

## 14. Eligibility policy generation

Generate this artifact only for integrated facilities unless explicitly configured otherwise.

The policy must:

- Read like a brief to a new front-desk employee.
- Be specific, direct, and operational.
- Use one decision rule per line wherever possible.
- Refer only to backend properties available to the evaluator.
- Define membership/pass interpretation explicitly.
- Define date-window calculations explicitly.
- Define time, day, card-on-file, group, price-class, course, or player restrictions only when supplied by client policy.
- Specify the denial reason associated with each failed rule.
- Stop at the first failed rule when the business policy requires ordered evaluation.
- Return only `eligible` and `reason` behavior expected by the backend.
- Exclude receptionist persona, greetings, transfer behavior, and facility marketing information.

The validator must detect orphan lines such as a standalone `Return eligible: false` that are detached from their condition and reason.

## 15. Validation requirements

### 15.1 Deterministic validation

The application must run deterministic checks before LLM critique:

- Required files and metadata exist.
- Tags are balanced and ordered.
- Unified prompt contains a non-empty knowledge base.
- Required runtime variables are initialized.
- Unknown curly-brace variables are rejected.
- Raw endpoint version labels are absent.
- Only enabled tool names appear.
- Tool argument names and formats match the selected contract.
- Integrated booking order is correct.
- Non-integrated prompts do not search or book tee-sheet inventory.
- Availability results preserve time/course pairing.
- Booking uses the returned course rather than an invented course.
- Eligibility policy is not duplicated into receptionist decision logic.
- Transfer destinations match the facility configuration exactly.
- No secret-like strings appear.
- No reference-facility names or phone numbers leak into a new facility output.
- Word count and section sizes are reported.
- Duplicate or contradictory directives are flagged.
- Every high-risk facility fact has provenance.

### 15.2 TTS validation

Check caller-facing examples and scripts for:

- Numeric time formats that should be spoken as words.
- Currency symbols and digit-heavy prices.
- Raw JSON, arrays, or tables presented as speech.
- Unpronounceable URLs or email addresses without approved speech formatting.
- Overly long monologues.
- Multiple questions in one turn where the convention requires one question at a time.

Tool arguments may retain machine-readable numeric formats; the validator must distinguish tool payload instructions from spoken dialogue.

### 15.3 LLM critique and repair

After deterministic checks pass, run an independent critique stage using the fact inventory, contracts, and generated artifacts. The critique must return structured findings with severity, location, evidence, and recommended correction.

At most two automatic repair passes should run by default. Every repair must be followed by full deterministic validation. The original draft and each repaired version must be retained.

### 15.4 Human review gates

The application must produce a review checklist and require explicit human approval for:

- Open factual conflicts.
- Transfer behavior.
- Booking and eligibility policy.
- Runtime variables.
- Tool names and arguments.
- Caller-detail collection.
- Final unified prompt.

## 16. Local CLI experience

Recommended commands:

```text
speaksport init
speaksport facility create <slug>
speaksport crawl <slug>
speaksport extract <slug>
speaksport generate <slug>
speaksport validate <slug>
speaksport diff <slug> [--against <run-id>]
speaksport package <slug>
speaksport run <slug>
speaksport references list
speaksport references activate <mode> <version>
```

`speaksport run` should execute every eligible stage and stop at human-decision gates. Each command must support `--help`, clear progress output, and nonzero exit codes on failure.

## 17. Recommended project structure

```text
speaksport-prompt-pipeline/
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── config/
│   ├── global-conventions.yaml
│   ├── runtime-variables.yaml
│   ├── validators.yaml
│   └── tool-contracts/
│       └── current.yaml
├── references/
│   ├── integrated/<version>/
│   ├── non-integrated/<version>/
│   └── eligibility/<version>/
├── facilities/<facility-slug>/
│   ├── facility.yaml
│   ├── client-notes.md
│   ├── booking-policies.md
│   └── known-exclusions.md
├── src/speaksport_pipeline/
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── crawling/
│   ├── extraction/
│   ├── generation/
│   ├── validation/
│   ├── packaging/
│   └── providers/
├── runs/<facility-slug>/<run-id>/
│   ├── manifest.json
│   ├── crawl/raw/
│   ├── crawl/normalized/
│   ├── facts/
│   ├── drafts/
│   ├── validation/
│   └── output/
└── tests/
    ├── unit/
    ├── integration/
    ├── fixtures/
    └── golden/
```

## 18. Output package

Every successful generation run must produce:

```text
output/
├── unified-vapi-prompt.md
├── eligibility-backoffice-policy.md   # integrated only
├── transfer-destinations.md
├── knowledge-base/
│   ├── facility-overview.md
│   ├── golf-and-booking.md
│   └── other-topic-files.md
├── source-manifest.md
├── open-questions.md
├── qa-report.md
├── generation-manifest.json
└── approval-checklist.md
```

The generation manifest must record input hashes, reference versions, tool-contract version, model configuration, crawl job ID, timestamps, word counts, validation outcome, and application version.

## 19. Testing strategy

### 19.1 Unit tests

- URL normalization.
- Secret redaction.
- Content hashing.
- Crawl-state transitions.
- Firecrawl pagination.
- Retry policies.
- Tag balancing.
- Runtime-variable validation.
- Tool-contract validation.
- Time conversion and TTS detection.
- Transfer destination matching.
- Prompt assembly.

### 19.2 Integration tests

- Mocked Firecrawl start/status lifecycle.
- Mocked OpenRouter structured output.
- Resume after interrupted crawl.
- Cache reuse based on hashes.
- Full integrated run with fixtures.
- Full non-integrated run with fixtures.

### 19.3 Golden tests

Use sanitized versions of:

- Sugarmill Woods as the integrated fixture.
- Bobby Jones Golf Course as the non-integrated fixture.

Golden tests should validate architecture, required logic, output files, and absence of cross-facility leakage. They should not require byte-identical natural-language output unless using a pinned model and deterministic fixture mode.

### 19.4 Security tests

- Refuse committed `.env` files.
- Scan outputs and logs for API-key patterns.
- Verify redaction in exceptions.
- Ensure HTTP clients never log authorization headers.

## 20. Non-functional requirements

### 20.1 Maintainability

- Python 3.11 or newer is recommended.
- Use typed models for configuration and intermediate schemas.
- Keep provider, crawler, generator, validator, and packager components isolated.
- Prefer explicit configuration over hidden constants.
- Document public interfaces and complex business rules.

### 20.2 Reproducibility

- Hash every material input.
- Retain exact sanitized LLM requests and responses.
- Pin dependency versions in the lock file.
- Support a pinned model mode.
- Never overwrite a previous run directory.

### 20.3 Performance

- Avoid re-crawling or re-running LLM stages when inputs are unchanged.
- A normal 50-page facility run should complete without manual file manipulation.
- Progress should remain visible during long crawl and inference stages.

### 20.4 Privacy and security

- Treat API keys as secrets.
- Treat client-supplied documents as confidential operational data.
- Do not send unrelated local files to Firecrawl or OpenRouter.
- Make remote data transmission explicit in logs without exposing content unnecessarily.
- Allow a future zero-data-retention configuration where provider capabilities permit it.

## 21. Error handling

The application must provide actionable errors for:

- Missing or invalid secrets.
- Firecrawl authentication, credit, rate-limit, and crawl failures.
- OpenRouter authentication, model capability, rate-limit, provider, and schema failures.
- Invalid facility configuration.
- Missing reference versions.
- Conflicting authoritative facts.
- Validation failures.
- Incomplete output packaging.

Failures must preserve intermediate state and explain the exact resume command.

## 22. Success metrics

- 100% of generated production packages include a unified prompt with an embedded knowledge base.
- 100% of integrated packages include an eligibility policy.
- Zero API keys in committed files or generated outputs.
- Zero reference-facility name leakage in approved prompts.
- All approved prompts pass deterministic tool, variable, structure, and transfer validation.
- At least 90% of new facility onboarding work is performed through the pipeline rather than manual copy/paste synthesis.
- Human review identifies fewer than three material corrections per pilot prompt after the initial calibration phase.

## 23. Delivery milestones

### Milestone 1: Foundation

- Project scaffold, configuration models, CLI, secrets handling, run manifests.
- Versioned reference and tool-contract registries.

### Milestone 2: Crawl and normalize

- Firecrawl integration, status polling, pagination, caching, raw storage, normalized Markdown.

### Milestone 3: Extract and reconcile

- OpenRouter adapter, structured fact extraction, provenance, conflict detection, open questions.

### Milestone 4: Generate

- Integrated and non-integrated section generation.
- Unified prompt assembly.
- Eligibility policy generation.

### Milestone 5: Validate and package

- Deterministic validators, LLM critique, repair loop, diffs, final package.

### Milestone 6: Pilot and harden

- Sugarmill integrated golden run.
- Bobby Jones non-integrated golden run.
- Documentation and operator acceptance testing.

## 24. Decisions required before production use

1. Confirm the one canonical transfer protocol, including whether any failure path may transfer without fresh verbal confirmation.
2. Confirm whether phone numbers may ever appear inside prompts or whether Vapi destination configuration always owns them.
3. Confirm the canonical runtime-variable list and exact placeholder spelling.
4. Confirm the exact logical tool names available to each workflow.
5. Confirm whether availability `when` accepts only `morning`, `afternoon`, `evening`, `all`, and `HH:MM`, or additional natural-language phrases.
6. Confirm whether booking should always pass the returned course even for single-course facilities.
7. Select a default OpenRouter model slug and a maximum cost per run.
8. Decide whether reference updates require reapproval of all validators or only affected modes.

## 25. Official implementation references

- Firecrawl v2 crawl request: https://docs.firecrawl.dev/api-reference/endpoint/crawl-post
- Firecrawl v2 crawl status: https://docs.firecrawl.dev/api-reference/endpoint/crawl-get
- Firecrawl Python quickstart: https://docs.firecrawl.dev/quickstarts/python
- OpenRouter API overview: https://openrouter.ai/docs/api/reference/overview
- OpenRouter Python SDK: https://openrouter.ai/docs/client-sdks/python/overview
- OpenRouter structured outputs: https://openrouter.ai/docs/guides/features/structured-outputs
- OpenRouter authentication and key safety: https://openrouter.ai/docs/api/reference/authentication

