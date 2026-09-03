from __future__ import annotations

import difflib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import __version__
from .cache import StageCache
from .exceptions import ConfigurationError
from .hashing import sha256_file, sha256_text, stable_hash
from .models import (
    FacilityConfig,
    FactInventory,
    GeneratedSections,
    IntegrationType,
    LLMResult,
    ModelConfiguration,
    PromptModificationConfig,
)
from .pipeline import (
    BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
    CANCELLATION_ELIGIBILITY_REQUIRED_VARIABLES,
    StructuredLLMClient,
    _normalize_eligibility_decision_prompt,
    _validate_eligibility_decision_prompt,
    write_generation_outputs,
)
from .validation.prompt import ValidationFinding

PRESERVE_KNOWLEDGE_BASE_SENTINEL = "__PRESERVE_ORIGINAL_KNOWLEDGE_BASE_EXACTLY__"

BOOKING_POLICY_EVIDENCE_PATTERN = re.compile(
    r"(?i)(?:booking window|book.{0,28}(?:days? in advance|calendar days?|before|after|through)|"
    r"(?:maximum|minimum).{0,20}players?|fivesomes?|single golfers?|card on file|prepay|"
    r"public players?|members?.{0,24}book|cannot book|may book)"
)
CANCELLATION_POLICY_EVIDENCE_PATTERN = re.compile(
    r"(?i)(?:cancel(?:lation|led|ing)?|no[- ]show|refund|reschedul|modif(?:y|ication))"
)


def extract_original_policy_evidence(original_prompt: str, *, kind: str) -> str:
    """Highlight likely policy lines so migration generation cannot overlook them."""
    pattern = (
        BOOKING_POLICY_EVIDENCE_PATTERN
        if kind == "booking"
        else CANCELLATION_POLICY_EVIDENCE_PATTERN
    )
    source_lines = original_prompt.splitlines()
    selected: set[int] = set()
    for index, line in enumerate(source_lines):
        if pattern.search(line):
            selected.update(range(max(0, index - 1), min(len(source_lines), index + 2)))
    evidence = "\n".join(source_lines[index] for index in sorted(selected)).strip()
    return evidence[:16_000]


def _policy_has_substantive_decision_rule(content: str) -> bool:
    if "Apply these rules in order:" not in content:
        return False
    rules = content.split("Apply these rules in order:", maxsplit=1)[1]
    candidates = [
        line.strip().lstrip("-* ").strip()
        for line in rules.splitlines()
        if line.strip().startswith(("-", "*"))
        and "do not apply any other" not in line.casefold()
    ]
    generic = re.compile(
        r"(?i)^(?:the )?(?:requested booking|reservation)?\s*date(?: and .{0,30}time)? "
        r"must be (?:present and )?valid\.?$"
    )
    return any(candidate and not generic.fullmatch(candidate) for candidate in candidates)


def extract_original_knowledge_base(prompt: str) -> str:
    matches = re.findall(r"<knowledge-base>\s*(.*?)\s*</knowledge-base>", prompt, flags=re.DOTALL)
    if len(matches) != 1:
        raise ConfigurationError(
            "Original prompt must contain exactly one <knowledge-base>...</knowledge-base> block"
        )
    content = matches[0].strip()
    if not content:
        raise ConfigurationError("Original prompt knowledge base is empty")
    return content


class PromptModificationPipeline:
    def __init__(self, llm: StructuredLLMClient, cache: StageCache):
        self.llm = llm
        self.cache = cache

    def generate(
        self,
        *,
        facility: FacilityConfig,
        modification: PromptModificationConfig,
        original_prompt: str,
        update_notes: str,
        additional_context: dict[str, str],
        reference_prompt: str,
        generation_instructions: str,
        runtime_registry: str,
        tool_contracts: str,
        global_conventions: str,
        eligibility_conventions: str,
        audit_directory: Path,
    ) -> tuple[GeneratedSections, LLMResult, bool]:
        preservation = modification.preservation
        after_hours_transfer_instruction = (
            "When current_status is after_hours, transfer_call-staging remains available so "
            "callers can leave voicemail. Explain that the requested team is closed and the "
            "call may reach voicemail before transferring. Do not prohibit or defer the transfer "
            "because the facility is closed."
            if facility.transfer_policy.allow_after_hours_transfers
            else (
                "When current_status is after_hours, do not transfer; offer help and tell the "
                "caller to call back at opening_time."
            )
        )
        knowledge_instruction = (
            "Return the exact sentinel "
            f"{PRESERVE_KNOWLEDGE_BASE_SENTINEL!r} in knowledge_base; code will restore the "
            "original knowledge base byte-for-byte. Do not rewrite or summarize it."
            if preservation.knowledge_base == "exact"
            else (
                "Revise the knowledge base only as explicitly requested. Retain every other "
                "caller-useful fact and all detailed rates, tiers, hours, policies, staff, "
                "menus, amenities, and exceptions from the original knowledge base."
            )
        )
        context_bundle = "\n\n".join(
            f"ADDITIONAL CONTEXT FILE {name}\n{content}"
            for name, content in additional_context.items()
        )
        booking_evidence = extract_original_policy_evidence(
            original_prompt, kind="booking"
        )
        cancellation_evidence = extract_original_policy_evidence(
            original_prompt, kind="cancellation"
        )
        booking_guidance = (
            "\n".join(facility.booking_rules)
            if facility.booking_rules
            else (
                "No explicit UI override was supplied. Infer and preserve every booking "
                "eligibility rule from the original prompt evidence below."
            )
        )
        cancellation_guidance = (
            facility.cancellation_modification_policy
            if facility.cancellation_modification_policy.strip()
            else (
                "No explicit UI override was supplied. Infer and preserve every cancellation "
                "eligibility rule from the original prompt evidence below. If the original "
                "contains no AI-cancellation threshold, do not invent one; retain the supported "
                "restriction and flag the missing policy in open_questions."
            )
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Update an existing production SpeakSport voice-agent prompt. This is an "
                    "editing and migration task, not new-facility research. The original prompt "
                    "is the authoritative source for facility-specific facts, identity, voice, "
                    "and established customer behavior. Explicit update notes define requested "
                    "changes. Current runtime variables, tool contracts, global conventions, "
                    "eligibility conventions, and enabled tools override obsolete workflow or "
                    "tool instructions in the original. The architectural reference supplies "
                    "current structure only; never import its facility facts, names, destinations, "
                    "or special behaviors. Do not invent facility policies. Preserve unmentioned "
                    "behavior when compatible with the current contracts unless the preservation "
                    "configuration says to replace it. Remove obsolete tool names and obsolete "
                    "test-only behavior unless update notes explicitly retain them. Enabled tools "
                    "define actionable scope; disabled tools must not be mentioned. Generate a "
                    "canonical core-shell, knowledge-base, logic-module, optional closing "
                    "core-shell blocks, booking eligibility policy, and cancellation eligibility "
                    "policy when enabled. Eligibility artifacts are business decision policies, "
                    "not input-schema checks. Apply explicit UI policy guidance first; otherwise "
                    "infer every relevant rule from the original prompt, including booking "
                    "windows, membership or public distinctions, player limits, card or prepayment "
                    "requirements, date/time restrictions, cancellation thresholds, penalties, "
                    "exceptions, routing outcomes, and exact caller-facing reasons. Never replace "
                    "those rules with only a generic statement that date and time must be valid. "
                    "When an old prompt says the assistant cannot cancel and supplies no "
                    "threshold, do not invent a standard threshold: preserve the ineligible "
                    "behavior and add "
                    "an open question. Existing booking lookup and cancellation must follow the "
                    "current ordered contracts. Current availability results contain time, course, "
                    "spots_remaining, and returned walking/riding price fields. When the facility "
                    "booking-fee toggle is on, expect all four base and fee-inclusive price "
                    "fields; when it is off, do not require all four. Follow facility "
                    "availability_pricing, "
                    "pass apply_booking_fee true or false consistently when booking, use only "
                    "riding prices for riding-only facilities, and never ask riding before "
                    "availability. Current single-player behavior is controlled "
                    "by facility availability policy. Keep booking references hidden. Initialize "
                    "current_status, opening_time, and closing_time. Current status governs only "
                    "whether a human transfer is possible; all enabled non-transfer tools and "
                    "self-service workflows remain available twenty-four hours a day, seven days "
                    "a week. Never stop booking, availability, identity, eligibility, reservation "
                    "lookup, cancellation, weather, SMS, or another enabled action merely because "
                    "the facility is after hours. "
                    f"{after_hours_transfer_instruction} "
                    "Treat a direct caller transfer request as consent without reconfirmation; "
                    "assistant-offered transfers still wait for a yes. Use only the softer "
                    "optional shop assistance check when configured and never claim the shop "
                    "is busy. "
                    "When the target tee_sheet is club_prophet, initialize identity_confirmed and "
                    "apply the complete get_customer_records and confirm_identity flow from the "
                    "current contracts; never import that flow for another tee sheet. "
                    "When the target tee_sheet is club_caddie, do not initialize "
                    "identity_confirmed or use customer-record identity tools. Apply the "
                    "ClubCaddie rules from the current contracts: spots_remaining is maximum "
                    "bookable party size, not literal open seats; use the configured four-field "
                    "walking/riding booking-fee behavior and pass apply_booking_fee when booking; "
                    "references are short numeric strings; fallback reference lookup needs the "
                    "reservation date; cancellation carries the selected reservation context; "
                    "and no booking confirmation email may be promised. "
                    "Never mention endpoint versions. Preserve the configured transfer identifiers "
                    "exactly. In generation_notes, list the material changes made and any original "
                    "instruction intentionally removed as obsolete or conflicting. Include every "
                    "configured required_output_marker verbatim in the updated caller-facing "
                    "prompt, and omit anything matching a configured forbidden_output_pattern. "
                    + knowledge_instruction
                ),
            },
            {
                "role": "user",
                "content": (
                    f"MODIFICATION CONFIGURATION\n{modification.model_dump_json(indent=2)}\n\n"
                    f"TARGET FACILITY CONFIGURATION\n{facility.model_dump_json(indent=2)}\n\n"
                    f"EXPLICIT UPDATE NOTES\n{update_notes}\n\n"
                    f"BOOKING ELIGIBILITY POLICY GUIDANCE\n{booking_guidance}\n\n"
                    f"CANCELLATION ELIGIBILITY POLICY GUIDANCE\n"
                    f"{cancellation_guidance}\n\n"
                    f"HIGHLIGHTED ORIGINAL BOOKING POLICY EVIDENCE\n"
                    f"{booking_evidence or 'No likely booking-policy lines detected.'}\n\n"
                    f"HIGHLIGHTED ORIGINAL CANCELLATION POLICY EVIDENCE\n"
                    f"{cancellation_evidence or 'No likely cancellation-policy lines detected.'}"
                    "\n\n"
                    f"{context_bundle}\n\n"
                    f"ORIGINAL PRODUCTION PROMPT\n{original_prompt}\n\n"
                    f"CURRENT GENERATION INSTRUCTIONS\n{generation_instructions}\n\n"
                    f"CURRENT GLOBAL CONVENTIONS\n{global_conventions}\n\n"
                    f"CURRENT ELIGIBILITY CONVENTIONS\n{eligibility_conventions}\n\n"
                    f"CURRENT RUNTIME VARIABLES\n{runtime_registry}\n\n"
                    f"CURRENT TOOL CONTRACTS\n{tool_contracts}\n\n"
                    f"CURRENT ARCHITECTURAL REFERENCE\n{reference_prompt}"
                ),
            },
        ]
        key = stable_hash(
            {
                "messages": messages,
                "schema": GeneratedSections.model_json_schema(),
                "schema_name": "modified_prompt_sections",
            }
        )
        cached = self.cache.load("prompt-modifications-v1", key, GeneratedSections)
        if cached:
            sections, result = cached
            assert isinstance(sections, GeneratedSections)
            return self._finalize(sections, facility, modification, original_prompt), result, True
        sections, result = self.llm.generate_structured(
            messages=messages,
            output_model=GeneratedSections,
            schema_name="modified_prompt_sections",
            audit_directory=audit_directory,
        )
        self.cache.save("prompt-modifications-v1", key, sections, result)
        return self._finalize(sections, facility, modification, original_prompt), result, False

    @staticmethod
    def _finalize(
        sections: GeneratedSections,
        facility: FacilityConfig,
        modification: PromptModificationConfig,
        original_prompt: str,
    ) -> GeneratedSections:
        knowledge_base = sections.knowledge_base
        if modification.preservation.knowledge_base == "exact":
            knowledge_base = extract_original_knowledge_base(original_prompt)
        eligibility_policy = (
            _normalize_eligibility_decision_prompt(
                sections.eligibility_policy,
                required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
            )
            if sections.eligibility_policy
            else None
        )
        cancellation_policy = (
            _normalize_eligibility_decision_prompt(
                sections.cancellation_eligibility_policy,
                required_variables=CANCELLATION_ELIGIBILITY_REQUIRED_VARIABLES,
            )
            if sections.cancellation_eligibility_policy
            else None
        )
        if facility.integration_type == IntegrationType.INTEGRATED:
            if not eligibility_policy:
                raise ConfigurationError("Modified integrated prompt omitted eligibility policy")
            _validate_eligibility_decision_prompt(
                eligibility_policy,
                label="Booking eligibility policy",
                required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
            )
            booking_source_exists = bool(
                facility.booking_rules
                or extract_original_policy_evidence(original_prompt, kind="booking")
            )
            if booking_source_exists and not _policy_has_substantive_decision_rule(
                eligibility_policy
            ):
                raise ConfigurationError(
                    "Modified booking eligibility policy ignored substantive rules from the "
                    "facility guidance or original prompt"
                )
            cancellation_enabled = "get-eligibility-for-cancellation" in facility.enabled_tools
            if cancellation_enabled and not cancellation_policy:
                raise ConfigurationError("Modified prompt omitted cancellation eligibility policy")
            if cancellation_enabled:
                _validate_eligibility_decision_prompt(
                    cancellation_policy or "",
                    label="Cancellation eligibility policy",
                    required_variables=CANCELLATION_ELIGIBILITY_REQUIRED_VARIABLES,
                )
                cancellation_source_exists = bool(
                    facility.cancellation_modification_policy.strip()
                    or extract_original_policy_evidence(
                        original_prompt, kind="cancellation"
                    )
                )
                if (
                    cancellation_source_exists
                    and not _policy_has_substantive_decision_rule(
                        cancellation_policy or ""
                    )
                ):
                    raise ConfigurationError(
                        "Modified cancellation eligibility policy ignored substantive rules "
                        "from the facility guidance or original prompt"
                    )
            if not cancellation_enabled and cancellation_policy:
                raise ConfigurationError(
                    "Cancellation eligibility policy requires its enabled tool"
                )
        return sections.model_copy(
            update={
                "knowledge_base": knowledge_base,
                "eligibility_policy": eligibility_policy,
                "cancellation_eligibility_policy": cancellation_policy,
            }
        )


def create_modification_run(
    root: Path,
    facility: FacilityConfig,
    modification: PromptModificationConfig,
    model: ModelConfiguration,
    tool_contract_version: str,
    input_paths: list[Path],
) -> tuple[Path, dict[str, object]]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{uuid4().hex[:8]}"
    run_directory = root / "modification-runs" / modification.slug / run_id
    for relative in ("drafts/llm-audit", "validation", "output"):
        (run_directory / relative).mkdir(parents=True, exist_ok=True)
    inputs = [
        {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}
        for path in sorted(input_paths)
    ]
    input_hash = stable_hash(
        {
            "facility": facility.model_dump(mode="json"),
            "modification": modification.model_dump(mode="json"),
            "tool_contract_version": tool_contract_version,
            "model": model.model_dump(mode="json"),
            "inputs": inputs,
        }
    )
    manifest: dict[str, object] = {
        "schema_version": "1",
        "run_type": "prompt_modification",
        "run_id": run_id,
        "modification_slug": modification.slug,
        "facility_slug": facility.slug,
        "application_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "CREATED",
        "input_hash": input_hash,
        "inputs": inputs,
        "tool_contract_version": tool_contract_version,
        "requested_model": model.model_slug,
        "fallback_models": model.fallback_models,
        "max_cost_usd": model.max_cost_usd,
        "timeout_seconds": model.timeout_seconds,
    }
    save_modification_manifest(run_directory, manifest)
    return run_directory, manifest


def save_modification_manifest(run_directory: Path, manifest: dict[str, object]) -> None:
    (run_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_prompt_diffs(output_directory: Path, original: str, updated: str) -> None:
    original_lines = original.splitlines()
    updated_lines = updated.splitlines()
    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            updated_lines,
            fromfile="original-prompt.md",
            tofile="updated-prompt.md",
            lineterm="",
        )
    )
    markdown = "# Original versus updated prompt\n\n```diff\n"
    markdown += "\n".join(diff_lines)
    markdown += "\n```\n"
    (output_directory / "original-vs-updated.diff.md").write_text(markdown, encoding="utf-8")
    html = difflib.HtmlDiff(wrapcolumn=100).make_file(
        original_lines,
        updated_lines,
        fromdesc="Original production prompt",
        todesc="Updated prompt",
        context=False,
        charset="utf-8",
    )
    (output_directory / "original-vs-updated.html").write_text(html, encoding="utf-8")


def validate_modification_requirements(
    prompt: str, modification: PromptModificationConfig
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for marker in modification.required_output_markers:
        if marker not in prompt:
            findings.append(
                ValidationFinding(
                    code="MISSING_MODIFICATION_REQUIREMENT",
                    severity="error",
                    message=f"Updated prompt omitted required marker: {marker}",
                )
            )
    for pattern in modification.forbidden_output_patterns:
        if match := re.search(pattern, prompt):
            findings.append(
                ValidationFinding(
                    code="FORBIDDEN_MODIFICATION_CONTENT",
                    severity="error",
                    message=(
                        "Updated prompt retained forbidden content matching "
                        f"{pattern}: {match.group(0)}"
                    ),
                )
            )
    return findings


def write_modification_outputs(
    *,
    run_directory: Path,
    facility: FacilityConfig,
    modification: PromptModificationConfig,
    original_prompt: str,
    sections: GeneratedSections,
) -> Path:
    output = run_directory / "output"
    prompt_path = write_generation_outputs(output, facility, FactInventory(facts=[]), sections)
    updated_prompt = prompt_path.read_text(encoding="utf-8")
    (output / "original-prompt.md").write_text(original_prompt, encoding="utf-8")
    write_prompt_diffs(output, original_prompt, updated_prompt)
    original_kb = extract_original_knowledge_base(original_prompt)
    updated_kb = extract_original_knowledge_base(updated_prompt)
    preservation_report = {
        "knowledge_base_mode": modification.preservation.knowledge_base,
        "original_knowledge_base_sha256": sha256_text(original_kb),
        "updated_knowledge_base_sha256": sha256_text(updated_kb),
        "knowledge_base_exactly_preserved": original_kb == updated_kb,
    }
    (output / "preservation-report.json").write_text(
        json.dumps(preservation_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    notes = ["# Change summary", ""]
    notes.extend(f"- {note}" for note in sections.generation_notes)
    (output / "change-summary.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    return prompt_path
