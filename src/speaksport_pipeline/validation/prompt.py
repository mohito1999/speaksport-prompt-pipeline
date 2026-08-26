from __future__ import annotations

import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..models import (
    BookingFeeApplication,
    FacilityConfig,
    IntegrationType,
    RuntimeVariableRegistry,
    TeeSheetProvider,
    ToolContractRegistry,
)
from ..security import scan_text

TAG_PATTERN = re.compile(r"<(/?)(core-shell|knowledge-base|logic-module)>")
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
TOOL_MENTION_PATTERN = re.compile(
    r"(?i)(?:call|invoke|execute|use)\s+(?:the\s+)?[`<]?([A-Za-z][A-Za-z0-9_-]*)[`>]?\s+tool"
)
WORD_PATTERN = re.compile(r"\b[\w'-]+\b")


class ValidationFinding(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    location: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    findings: list[ValidationFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(finding.severity == "error" for finding in self.findings)


class PromptValidator:
    def __init__(
        self,
        runtime_registry: RuntimeVariableRegistry,
        tool_registry: ToolContractRegistry,
        validator_config: dict[str, Any],
        global_conventions: dict[str, Any],
    ):
        self.runtime_registry = runtime_registry
        self.tool_registry = tool_registry
        self.config = validator_config
        self.global_conventions = global_conventions

    def validate(
        self,
        prompt: str,
        facility: FacilityConfig,
        *,
        allow_phone_numbers_in_exact_knowledge_base: bool = False,
    ) -> ValidationReport:
        findings: list[ValidationFinding] = []
        metrics: dict[str, Any] = {}
        findings.extend(self._validate_structure(prompt, metrics))
        findings.extend(self._validate_variables(prompt))
        findings.extend(self._validate_tools(prompt, facility))
        findings.extend(self._validate_booking_flow(prompt, facility))
        findings.extend(self._validate_existing_booking_and_cancellation_flow(prompt, facility))
        findings.extend(self._validate_club_prophet_identity_flow(prompt, facility))
        findings.extend(self._validate_reference_fidelity(prompt, facility))
        findings.extend(
            self._validate_forbidden_content(
                prompt,
                facility,
                allow_phone_numbers_in_exact_knowledge_base=(
                    allow_phone_numbers_in_exact_knowledge_base
                ),
            )
        )
        findings.extend(self._validate_mode(prompt, facility))
        word_count = len(WORD_PATTERN.findall(prompt))
        metrics["total_words"] = word_count
        target = self.config.get("report_target_prompt_words", {})
        if word_count < int(target.get("minimum", 0)):
            findings.append(
                ValidationFinding(
                    code="PROMPT_BELOW_TARGET_LENGTH",
                    severity="info",
                    message=(
                        f"Prompt has {word_count} words; target starts at {target.get('minimum')}"
                    ),
                )
            )
        return ValidationReport(
            valid=not any(finding.severity == "error" for finding in findings),
            findings=findings,
            metrics=metrics,
        )

    def _validate_structure(self, prompt: str, metrics: dict[str, Any]) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        stack: list[str] = []
        top_level_sequence: list[str] = []
        counts: Counter[str] = Counter()
        for match in TAG_PATTERN.finditer(prompt):
            closing, tag = match.groups()
            if not closing:
                if not stack:
                    top_level_sequence.append(tag)
                stack.append(tag)
                counts[tag] += 1
            elif not stack or stack[-1] != tag:
                findings.append(
                    ValidationFinding(
                        code="UNBALANCED_TAG",
                        severity="error",
                        message=f"Unexpected closing tag </{tag}>",
                    )
                )
            else:
                stack.pop()
        for tag in reversed(stack):
            findings.append(
                ValidationFinding(
                    code="UNBALANCED_TAG",
                    severity="error",
                    message=f"Missing closing tag </{tag}>",
                )
            )
        required_prefix = ["core-shell", "knowledge-base", "logic-module"]
        order_valid = top_level_sequence[:3] == required_prefix and all(
            tag == "core-shell" for tag in top_level_sequence[3:]
        )
        if not order_valid:
            findings.append(
                ValidationFinding(
                    code="INVALID_SECTION_ORDER",
                    severity="error",
                    message=(
                        "Top-level sections must begin core-shell, knowledge-base, logic-module; "
                        "only intentional core-shell blocks may follow"
                    ),
                )
            )
        for required_tag in required_prefix:
            if counts[required_tag] == 0:
                findings.append(
                    ValidationFinding(
                        code="MISSING_SECTION",
                        severity="error",
                        message=f"Missing <{required_tag}> section",
                    )
                )
        minimum_words = self.config.get("minimum_section_words", {})
        for tag, metric_name in (
            ("core-shell", "core_shell_words"),
            ("knowledge-base", "knowledge_base_words"),
            ("logic-module", "logic_module_words"),
        ):
            bodies = re.findall(rf"<{tag}>(.*?)</{tag}>", prompt, flags=re.DOTALL)
            words = sum(len(WORD_PATTERN.findall(body)) for body in bodies)
            metrics[metric_name] = words
            configured_key = tag.replace("-", "_")
            if words < int(minimum_words.get(configured_key, 1)):
                findings.append(
                    ValidationFinding(
                        code="EMPTY_SECTION",
                        severity="error",
                        message=f"<{tag}> must contain meaningful content",
                    )
                )
        return findings

    def _validate_variables(self, prompt: str) -> list[ValidationFinding]:
        allowed = {variable.name for variable in self.runtime_registry.variables}
        used = set(PLACEHOLDER_PATTERN.findall(prompt))
        findings = [
            ValidationFinding(
                code="UNKNOWN_RUNTIME_VARIABLE",
                severity="error",
                message=f"Unknown runtime variable {{{{{name}}}}}",
            )
            for name in sorted(used - allowed)
        ]
        required = {
            variable.name for variable in self.runtime_registry.variables if variable.required
        }
        findings.extend(
            ValidationFinding(
                code="MISSING_REQUIRED_RUNTIME_VARIABLE",
                severity="error",
                message=f"Required runtime variable {{{{{name}}}}} is not initialized",
            )
            for name in sorted(required - used)
        )
        return findings

    def _validate_tools(self, prompt: str, facility: FacilityConfig) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        enabled = set(facility.enabled_tools)
        contracts = {tool.logical_name: tool for tool in self.tool_registry.tools}
        for name in sorted(enabled - set(contracts)):
            findings.append(
                ValidationFinding(
                    code="UNKNOWN_ENABLED_TOOL",
                    severity="error",
                    message=f"Facility enables unknown tool {name}",
                )
            )
        incompatible = {
            name
            for name in enabled
            if name in contracts
            and facility.integration_type not in contracts[name].compatible_modes
        }
        for name in sorted(incompatible):
            findings.append(
                ValidationFinding(
                    code="INCOMPATIBLE_ENABLED_TOOL",
                    severity="error",
                    message=f"Tool {name} is not compatible with {facility.integration_type.value}",
                )
            )
        for name in sorted(enabled):
            if not re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])", prompt):
                findings.append(
                    ValidationFinding(
                        code="MISSING_ENABLED_TOOL",
                        severity="error",
                        message=f"Prompt does not define behavior for enabled tool {name}",
                    )
                )
        for name in sorted(set(contracts) - enabled):
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])", prompt):
                findings.append(
                    ValidationFinding(
                        code="DISABLED_TOOL_MENTION",
                        severity="error",
                        message=f"Prompt mentions disabled tool {name}",
                    )
                )
        generic_tool_labels = {
            "a",
            "approved",
            "availability",
            "booking",
            "eligibility",
            "general",
            "sms",
            "transfer",
        }
        unknown_mentions = {
            name
            for name in TOOL_MENTION_PATTERN.findall(prompt)
            if name not in contracts and name.casefold() not in generic_tool_labels | {"the"}
        }
        for name in sorted(unknown_mentions):
            findings.append(
                ValidationFinding(
                    code="UNKNOWN_TOOL_MENTION",
                    severity="error",
                    message=f"Prompt appears to invoke unknown tool {name}",
                )
            )
        return findings

    def _validate_forbidden_content(
        self,
        prompt: str,
        facility: FacilityConfig,
        *,
        allow_phone_numbers_in_exact_knowledge_base: bool,
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        for pattern in self.config.get("forbidden_endpoint_version_patterns", []):
            if match := re.search(pattern, prompt):
                findings.append(
                    ValidationFinding(
                        code="ENDPOINT_VERSION_LABEL",
                        severity="error",
                        message=f"Endpoint version label is forbidden: {match.group(0)}",
                    )
                )
        for secret in scan_text(prompt):
            findings.append(
                ValidationFinding(
                    code="SECRET_LIKE_CONTENT",
                    severity="error",
                    message=f"Secret-like content detected ({secret.kind})",
                    location=f"line {secret.line}",
                )
            )
        phone_policy = self.global_conventions.get("phone_numbers_in_prompts", {})
        if not phone_policy.get("allowed", False):
            phone_pattern = self.config.get("phone_number_pattern")
            phone_scan_text = prompt
            if allow_phone_numbers_in_exact_knowledge_base:
                phone_scan_text = re.sub(
                    r"(?is)<knowledge-base>.*?</knowledge-base>",
                    "<knowledge-base></knowledge-base>",
                    phone_scan_text,
                )
            if phone_pattern and re.search(phone_pattern, phone_scan_text):
                findings.append(
                    ValidationFinding(
                        code="PHONE_NUMBER_IN_PROMPT",
                        severity="error",
                        message="Phone numbers are disallowed by the current global convention",
                    )
                )
        configured_terms = self.config.get("forbidden_reference_leakage_terms", {})
        mode_terms = configured_terms.get(facility.integration_type.value, [])
        exceptions = {value.casefold() for value in facility.reference_leakage_exceptions}
        facility_name = facility.display_name.casefold()
        for term in mode_terms:
            normalized = term.casefold()
            if normalized in exceptions or normalized in facility_name:
                continue
            if normalized in prompt.casefold():
                findings.append(
                    ValidationFinding(
                        code="REFERENCE_FACILITY_LEAKAGE",
                        severity="error",
                        message=f"Reference-facility term leaked into prompt: {term}",
                    )
                )
        return findings

    def _validate_mode(self, prompt: str, facility: FacilityConfig) -> list[ValidationFinding]:
        if facility.integration_type != IntegrationType.NON_INTEGRATED:
            return []
        prohibited_capabilities = {"eligibility", "availability", "booking"}
        prohibited_names = {
            tool.logical_name
            for tool in self.tool_registry.tools
            if tool.capability in prohibited_capabilities
        }
        return [
            ValidationFinding(
                code="INTEGRATED_TOOL_IN_NON_INTEGRATED_PROMPT",
                severity="error",
                message=f"Non-integrated prompt must not mention {name}",
            )
            for name in sorted(prohibited_names)
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])", prompt)
        ]

    def _validate_booking_flow(
        self, prompt: str, facility: FacilityConfig
    ) -> list[ValidationFinding]:
        contracts = {tool.capability: tool.logical_name for tool in self.tool_registry.tools}
        findings: list[ValidationFinding] = []
        if facility.integration_type == IntegrationType.INTEGRATED:
            sequence = [
                contracts[capability]
                for capability in ("eligibility", "availability", "booking")
                if capability in contracts
            ]
            positions = [prompt.find(name) for name in sequence]
            for name, position in zip(sequence, positions, strict=True):
                if position < 0:
                    findings.append(
                        ValidationFinding(
                            code="MISSING_BOOKING_TOOL",
                            severity="error",
                            message=f"Integrated prompt must orchestrate {name}",
                        )
                    )
            present_positions = [position for position in positions if position >= 0]
            if len(present_positions) == len(sequence) and present_positions != sorted(
                present_positions
            ):
                findings.append(
                    ValidationFinding(
                        code="INVALID_BOOKING_TOOL_ORDER",
                        severity="error",
                        message="Eligibility must precede availability, which must precede booking",
                    )
                )
            if facility.course_configuration.value == "multi_course" and (
                "{{courses}}" not in prompt or "course_name" not in prompt
            ):
                findings.append(
                    ValidationFinding(
                        code="MISSING_MULTI_COURSE_FLOW",
                        severity="error",
                        message=(
                            "Multi-course prompts must initialize {{courses}} and pass an "
                            "exact selected course_name"
                        ),
                    )
                )
            for marker in self.config.get(
                "integrated_required_date_resolution_markers", []
            ):
                if marker not in prompt:
                    findings.append(
                        ValidationFinding(
                            code="MISSING_DATE_RESOLUTION_GUARDRAIL",
                            severity="error",
                            message=(
                                "Integrated prompt omitted mandatory date-resolution "
                                f"guardrail: {marker}"
                            ),
                        )
                    )
            for marker in self.config.get("integrated_required_availability_markers", []):
                if marker not in prompt:
                    findings.append(
                        ValidationFinding(
                            code="MISSING_AVAILABILITY_GUARDRAIL",
                            severity="error",
                            message=(
                                "Integrated prompt omitted mandatory availability "
                                f"guardrail: {marker}"
                            ),
                        )
                    )
            pricing_markers = {
                BookingFeeApplication.NONE: (
                    "This facility does not charge the caller a SpeakSport booking fee."
                ),
                BookingFeeApplication.ALL_CALLERS: (
                    "The booking fee applies to every caller."
                ),
                BookingFeeApplication.CONDITIONAL: (
                    "Booking-fee application is conditional."
                ),
            }
            expected_pricing_marker = pricing_markers[
                facility.availability_pricing.booking_fee_application
            ]
            if expected_pricing_marker not in prompt:
                findings.append(
                    ValidationFinding(
                        code="MISSING_AVAILABILITY_PRICING_POLICY",
                        severity="error",
                        message=(
                            "Integrated prompt does not match the configured availability "
                            "pricing policy"
                        ),
                    )
                )
            restricted_marker = (
                "This facility restricts solo bookings to partially filled tee times."
            )
            unrestricted_marker = (
                "This facility does not restrict solo callers to partially filled tee times."
            )
            if facility.availability_policy.single_player_requires_partially_filled_slot:
                required_marker = restricted_marker
                forbidden_marker = unrestricted_marker
            else:
                required_marker = unrestricted_marker
                forbidden_marker = restricted_marker
            if required_marker not in prompt:
                findings.append(
                    ValidationFinding(
                        code="MISSING_SINGLE_PLAYER_AVAILABILITY_POLICY",
                        severity="error",
                        message="Integrated prompt omitted the configured single-player policy",
                    )
                )
            if forbidden_marker in prompt:
                findings.append(
                    ValidationFinding(
                        code="CONFLICTING_SINGLE_PLAYER_AVAILABILITY_POLICY",
                        severity="error",
                        message="Integrated prompt contains the opposite single-player policy",
                    )
                )
        elif sms_name := contracts.get("sms"):
            if sms_name not in prompt:
                findings.append(
                    ValidationFinding(
                        code="MISSING_SMS_BOOKING_FLOW",
                        severity="error",
                        message=(
                            f"Non-integrated prompt must offer the booking link with {sms_name}"
                        ),
                    )
                )
        return findings

    def _validate_existing_booking_and_cancellation_flow(
        self, prompt: str, facility: FacilityConfig
    ) -> list[ValidationFinding]:
        contracts = {tool.capability: tool.logical_name for tool in self.tool_registry.tools}
        lookup = contracts.get("booking_lookup")
        eligibility = contracts.get("cancellation_eligibility")
        cancellation = contracts.get("cancellation")
        enabled = set(facility.enabled_tools)
        findings: list[ValidationFinding] = []

        if eligibility in enabled or cancellation in enabled:
            required = {name for name in (lookup, eligibility, cancellation) if name}
            missing = required - enabled
            for name in sorted(missing):
                findings.append(
                    ValidationFinding(
                        code="INCOMPLETE_CANCELLATION_TOOL_SET",
                        severity="error",
                        message=(
                            "Cancellation capability requires get-bookings, "
                            "get-eligibility-for-cancellation, and cancel-reservation; "
                            f"missing {name}"
                        ),
                    )
                )

        cancellation_chain = [lookup, eligibility, cancellation]
        logic_bodies = re.findall(r"<logic-module>(.*?)</logic-module>", prompt, flags=re.DOTALL)
        flow_text = "\n".join(logic_bodies)
        flow_lower = flow_text.casefold()
        if lookup and lookup in enabled:
            if not re.search(
                r"(?is)(?:booking_reference|(?:with|using) only (?:that |the )?(?:supplied )?(?:exact )?"
                r"(?:numeric )?booking reference)",
                flow_text,
            ):
                findings.append(
                    ValidationFinding(
                        code="INCOMPLETE_BOOKING_LOOKUP_FLOW",
                        severity="error",
                        message="Booking lookup fallback must pass only booking_reference",
                    )
                )
            if not re.search(r"\bno (?:parameters|arguments)\b", flow_lower):
                findings.append(
                    ValidationFinding(
                        code="INCOMPLETE_BOOKING_LOOKUP_FLOW",
                        severity="error",
                        message="Initial get-bookings lookup must use no parameters",
                    )
                )

        if all(name and name in enabled for name in cancellation_chain):
            ordered_chain = re.search(
                rf"(?is){re.escape(lookup or '')}.*"
                rf"{re.escape(eligibility or '')}.*{re.escape(cancellation or '')}",
                flow_text,
            )
            if ordered_chain is None:
                findings.append(
                    ValidationFinding(
                        code="INVALID_CANCELLATION_TOOL_ORDER",
                        severity="error",
                        message=(
                            "Cancellation flow must use get-bookings, then "
                            "get-eligibility-for-cancellation, then cancel-reservation"
                        ),
                    )
                )
        return findings

    def _validate_club_prophet_identity_flow(
        self, prompt: str, facility: FacilityConfig
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        is_club_prophet = facility.tee_sheet == TeeSheetProvider.CLUB_PROPHET
        uses_identity_variable = "identity_confirmed" in set(
            PLACEHOLDER_PATTERN.findall(prompt)
        )
        if not is_club_prophet:
            if uses_identity_variable:
                findings.append(
                    ValidationFinding(
                        code="UNREQUESTED_CLUB_PROPHET_IDENTITY_FLOW",
                        severity="error",
                        message=(
                            "Only club_prophet facilities may initialize "
                            "{{identity_confirmed}}"
                        ),
                    )
                )
            return findings

        if not uses_identity_variable:
            findings.append(
                ValidationFinding(
                    code="MISSING_CLUB_PROPHET_IDENTITY_VARIABLE",
                    severity="error",
                    message=(
                        "Club Prophet prompts must initialize {{identity_confirmed}}"
                    ),
                )
            )
        if re.search(
            r"{{identity_confirmed}}\s*,?\s*initialized to false",
            prompt,
            flags=re.IGNORECASE,
        ):
            findings.append(
                ValidationFinding(
                    code="INVALID_CLUB_PROPHET_IDENTITY_INITIALIZATION",
                    severity="error",
                    message=(
                        "Identity Confirmed must use the runtime boolean value and must not "
                        "be hard-coded or described as initialized to false"
                    ),
                )
            )
        for marker in self.config.get("club_prophet_identity_required_markers", []):
            if marker not in prompt:
                findings.append(
                    ValidationFinding(
                        code="MISSING_CLUB_PROPHET_IDENTITY_GUARDRAIL",
                        severity="error",
                        message=f"Club Prophet identity flow omitted: {marker}",
                    )
                )
        booking_flow_conflicts = (
            r"(?is)#\s*Booking(?: a Tee Time)? Flow.{0,2600}"
            r"check-booking-eligibility-staging.{0,1400}"
            r"(?:complete|run|perform).{0,100}(?:Club Prophet )?Identity Flow",
            r"(?is)do not ask.{0,120}identity.{0,120}before eligibility succeeds",
        )
        if any(re.search(pattern, prompt) for pattern in booking_flow_conflicts):
            findings.append(
                ValidationFinding(
                    code="CLUB_PROPHET_IDENTITY_AFTER_ELIGIBILITY",
                    severity="error",
                    message=(
                        "Club Prophet booking flow must complete identity resolution before "
                        "collecting booking details or calling booking eligibility"
                    ),
                )
            )
        return findings

    def _validate_reference_fidelity(
        self, prompt: str, facility: FacilityConfig
    ) -> list[ValidationFinding]:
        expected_datetime_context = (
            f'Today is {{{{"now" | date: "%A, %B %d, %Y", "{facility.timezone}"}}}}, '
            f'and the current time is {{{{"now" | date: "%I:%M %p", '
            f'"{facility.timezone}"}}}}.'
        )
        findings: list[ValidationFinding] = []
        if expected_datetime_context not in prompt:
            findings.append(
                ValidationFinding(
                    code="MISSING_LOCAL_DATETIME_CONTEXT",
                    severity="error",
                    message=(
                        "Prompt must initialize the current facility-local date and time "
                        f"exactly as: {expected_datetime_context}"
                    ),
                )
            )
        deflection_pattern = str(self.config.get("shop_transfer_deflection_pattern", ""))
        has_shop_deflection = bool(deflection_pattern and re.search(deflection_pattern, prompt))
        wants_shop_deflection = facility.transfer_policy.first_shop_transfer_deflection
        if wants_shop_deflection and not has_shop_deflection:
            findings.append(
                ValidationFinding(
                    code="MISSING_SHOP_TRANSFER_DEFLECTION",
                    severity="error",
                    message=(
                        "Facility enables first-shop-transfer deflection, but the prompt "
                        "does not include it"
                    ),
                )
            )
        elif not wants_shop_deflection and has_shop_deflection:
            findings.append(
                ValidationFinding(
                    code="UNREQUESTED_SHOP_TRANSFER_DEFLECTION",
                    severity="error",
                    message=(
                        "Facility disables first-shop-transfer deflection, but the prompt "
                        "still gatekeeps the caller's first transfer request"
                    ),
                )
            )
        busy_shop_pattern = str(self.config.get("busy_shop_claim_pattern", ""))
        # Mandatory guardrails commonly say "do not say the Pro Shop is busy".
        # Remove those explicit prohibitions before looking for an affirmative
        # busy-shop claim so the validator does not reject its own guardrail.
        busy_claim_scan_text = re.sub(
            r"(?is)\b(?:do not|never)\s+(?:say|claim|state|imply)\b.{0,140}?\bbusy\b",
            "",
            prompt,
        )
        if busy_shop_pattern and re.search(busy_shop_pattern, busy_claim_scan_text):
            findings.append(
                ValidationFinding(
                    code="OBSOLETE_BUSY_SHOP_DEFLECTION",
                    severity="error",
                    message=(
                        "Transfer assistance checks must not claim that the Golf/Pro Shop "
                        "is busy"
                    ),
                )
            )
        for marker in self.config.get("all_modes_required_transfer_markers", []):
            if marker not in prompt:
                findings.append(
                    ValidationFinding(
                        code="MISSING_HOURS_AWARE_TRANSFER_GUARDRAIL",
                        severity="error",
                        message=f"Prompt omitted mandatory transfer behavior: {marker}",
                    )
                )
        after_hours_block_pattern = str(
            self.config.get("after_hours_non_transfer_block_pattern", "")
        )
        if after_hours_block_pattern and re.search(after_hours_block_pattern, prompt):
            findings.append(
                ValidationFinding(
                    code="AFTER_HOURS_BLOCKS_SELF_SERVICE",
                    severity="error",
                    message=(
                        "Current operating status may restrict only transfer_call-staging; "
                        "enabled non-transfer tools and workflows must remain available 24/7"
                    ),
                )
            )
        if facility.integration_type != IntegrationType.INTEGRATED:
            return findings
        used = set(PLACEHOLDER_PATTERN.findall(prompt))
        forbidden = set(self.config.get("integrated_forbidden_runtime_variables", []))
        if "send_sms" in facility.enabled_tools:
            forbidden -= {"caller_phone", "booking_url"}
        findings.extend(
            ValidationFinding(
                code="UNAPPROVED_INTEGRATED_RUNTIME_VARIABLE",
                severity="error",
                message=f"Integrated prompt initializes unapproved variable {{{{{name}}}}}",
            )
            for name in sorted(used & forbidden)
        )
        for marker in self.config.get("integrated_required_reference_markers", []):
            if marker not in prompt:
                findings.append(
                    ValidationFinding(
                        code="MISSING_REFERENCE_CONVENTION",
                        severity="error",
                        message=(
                            f"Integrated prompt omitted required reference convention: {marker}"
                        ),
                    )
                )
        for requirement in self.config.get("integrated_required_reference_patterns", []):
            name = str(requirement.get("name", "reference convention"))
            pattern = str(requirement.get("pattern", ""))
            if pattern and not re.search(pattern, prompt):
                findings.append(
                    ValidationFinding(
                        code="MISSING_REFERENCE_CONVENTION",
                        severity="error",
                        message=f"Integrated prompt omitted required reference convention: {name}",
                    )
                )
        return findings
