from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from speaksport_pipeline.cache import StageCache
from speaksport_pipeline.exceptions import ConfigurationError
from speaksport_pipeline.models import (
    AvailabilityPolicy,
    AvailabilityPricingPolicy,
    BookingFeeApplication,
    CourseConfiguration,
    FacilityConfig,
    Fact,
    FactInventory,
    GeneratedSections,
    IntegrationType,
    LLMResult,
    NormalizedPage,
    ReferenceSelection,
    TeeSheetProvider,
    TransferPolicy,
)
from speaksport_pipeline.pipeline import (
    AFTER_HOURS_VOICEMAIL_TRANSFER_PROTOCOL,
    BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
    CANCELLATION_ELIGIBILITY_REQUIRED_VARIABLES,
    CLUB_CADDIE_GUARDRAILS,
    CLUB_PROPHET_IDENTITY_GUARDRAILS,
    MANDATORY_AVAILABILITY_GUARDRAILS,
    MANDATORY_DATE_RESOLUTION_GUARDRAILS,
    MANDATORY_TRANSFER_PROTOCOL,
    SINGLE_PLAYER_PARTIAL_SLOT_GUARDRAIL,
    SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL,
    PromptPipeline,
    _normalize_deprecated_runtime_placeholders,
    _normalize_eligibility_decision_prompt,
    _validate_eligibility_decision_prompt,
    availability_pricing_guardrail,
    write_generation_outputs,
)

OutputT = TypeVar("OutputT", bound=BaseModel)


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate_structured(
        self,
        *,
        messages: list[dict[str, str]],
        output_model: type[OutputT],
        schema_name: str,
        audit_directory: Path | None = None,
    ) -> tuple[OutputT, LLMResult]:
        self.calls += 1
        if output_model is FactInventory:
            output: BaseModel = FactInventory(
                facts=[
                    Fact(
                        category="identity",
                        subject="Example Club",
                        fact_text="Example Club is a golf facility.",
                        source_type="website",
                        source_identifier="WEB-001",
                        source_url_or_file="https://example.com",
                        source_excerpt="golf facility",
                        confidence=1,
                    )
                ]
            )
        else:
            output = GeneratedSections(
                core_shell="Use the initialized runtime variables.",
                knowledge_base="Example Club is a golf facility.",
                logic_module="Use the configured booking tools in order.",
                eligibility_policy=(
                    "Initialize the following variables:\n\n"
                    "'date' = requested booking date.\n"
                    "'time' = requested tee time.\n"
                    "'current_date' = today's date in the facility's local timezone.\n\n"
                    "Apply these rules in order:\n\n"
                    "- If the requested booking date is before today's date, the caller is not "
                    'eligible. Reason: "That date has already passed."\n'
                    "- Do not apply any other eligibility criteria.\n"
                    '- Otherwise, the caller is eligible. Reason: "Eligible to book."'
                ),
                transfer_destinations=["golf_shop"],
            )
        result = LLMResult(
            request_id=f"request-{self.calls}",
            requested_model="model",
            returned_model="model",
            content=output.model_dump(mode="json"),
            usage={"total_tokens": 10},
            cost_usd=0.01,
        )
        return output_model.model_validate(output.model_dump()), result


def _facility() -> FacilityConfig:
    return FacilityConfig(
        slug="example-club",
        display_name="Example Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
    )


def test_pipeline_caches_fact_and_generation_stages(tmp_path: Path) -> None:
    llm = FakeLLM()
    pipeline = PromptPipeline(llm, StageCache(tmp_path / "cache"))
    page = NormalizedPage(
        source_identifier="WEB-001",
        source_url="https://example.com",
        markdown="# Example",
        content_hash="a" * 64,
    )
    kwargs = {
        "facility": _facility(),
        "pages": [page],
        "client_documents": {},
        "audit_directory": tmp_path / "audit",
    }

    facts, _, first_cached = pipeline.extract_facts(**kwargs)
    _, _, second_cached = pipeline.extract_facts(**kwargs)
    generation_kwargs = {
        "facility": _facility(),
        "facts": facts,
        "reference_prompt": "reference",
        "generation_instructions": "instructions",
        "runtime_registry": "variables",
        "tool_contracts": "tools",
        "global_conventions": "conventions",
        "eligibility_conventions": "eligibility conventions",
        "audit_directory": tmp_path / "audit",
    }
    sections, _, generated_cached = pipeline.generate_sections(**generation_kwargs)
    _, _, generated_second_cached = pipeline.generate_sections(**generation_kwargs)

    assert not first_cached
    assert second_cached
    assert not generated_cached
    assert generated_second_cached
    # One authoritative-source extraction, one website extraction, and one generation call.
    assert llm.calls == 3
    prompt_path = write_generation_outputs(tmp_path / "output", _facility(), facts, sections)
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "<knowledge-base>" in prompt
    assert "{{phone_recognized}}" in prompt
    assert "{{current_status}}" in prompt
    assert "{{opening_time}}" in prompt
    assert "{{closing_time}}" in prompt
    assert MANDATORY_TRANSFER_PROTOCOL in prompt
    assert MANDATORY_DATE_RESOLUTION_GUARDRAILS in prompt
    assert MANDATORY_AVAILABILITY_GUARDRAILS in prompt
    assert "## Mandatory Availability Pricing Policy" in prompt
    assert SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL in prompt
    assert (tmp_path / "output" / "eligibility-backoffice-policy.md").is_file()


def test_pipeline_writes_after_hours_voicemail_transfer_policy_when_enabled(
    tmp_path: Path,
) -> None:
    facility = _facility().model_copy(
        update={"transfer_policy": TransferPolicy(allow_after_hours_transfers=True)}
    )
    sections = GeneratedSections(
        core_shell="Use the initialized runtime variables.",
        knowledge_base="Example Club is a golf facility.",
        logic_module="Use the configured booking tools in order.",
        eligibility_policy=(
            "Initialize the following variables:\n"
            "'date' = requested booking date.\n"
            "'time' = requested tee time.\n"
            "'current_date' = today's date.\n\n"
            "Apply these rules in order:\n"
            "- Do not apply any other eligibility criteria."
        ),
    )

    prompt = write_generation_outputs(
        tmp_path / "output", facility, FactInventory(facts=[]), sections
    ).read_text()

    assert AFTER_HOURS_VOICEMAIL_TRANSFER_PROTOCOL in prompt
    assert MANDATORY_TRANSFER_PROTOCOL not in prompt


def test_pipeline_writes_restricted_single_player_policy(tmp_path: Path) -> None:
    facility = _facility().model_copy(
        update={
            "availability_policy": AvailabilityPolicy(
                single_player_requires_partially_filled_slot=True
            )
        }
    )
    facts = FactInventory(facts=[])
    sections = GeneratedSections(
        core_shell="Use the configured runtime context.",
        knowledge_base="Example Club is a golf facility.",
        logic_module="Use the integrated booking workflow.",
        eligibility_policy=(
            "Initialize the following variables:\n"
            "'date' = requested booking date.\n"
            "'time' = requested tee time.\n"
            "'current_date' = today's date.\n\n"
            "Apply these rules in order:\n"
            "- Do not apply any other eligibility criteria."
        ),
    )

    prompt = write_generation_outputs(tmp_path / "output", facility, facts, sections).read_text()

    assert SINGLE_PLAYER_PARTIAL_SLOT_GUARDRAIL in prompt
    assert SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL not in prompt


def test_pipeline_writes_club_prophet_identity_runtime_and_guardrails(tmp_path: Path) -> None:
    facility = FacilityConfig(
        slug="cps-club",
        display_name="CPS Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        tee_sheet=TeeSheetProvider.CLUB_PROPHET,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
        enabled_tools=["get_customer_records", "confirm_identity"],
    )
    sections = GeneratedSections(
        core_shell=(
            "Identity Confirmed: {{identity_confirmed}}, initialized to false.\n"
            "Use the configured runtime context."
        ),
        knowledge_base="CPS Club is a golf facility.",
        logic_module=(
            "## Club Prophet On-Call Identity — Mandatory\nPartial model section.\n\n"
            "## Mandatory Availability Search Guardrails\nPartial model section."
        ),
        eligibility_policy=(
            "Initialize the following variables:\n"
            "'date' = requested booking date.\n"
            "'time' = requested tee time.\n"
            "'current_date' = today's date.\n\n"
            "Apply these rules in order:\n"
            "- Do not apply any other eligibility criteria."
        ),
    )

    prompt = write_generation_outputs(
        tmp_path / "output", facility, FactInventory(facts=[]), sections
    ).read_text()

    assert "Identity Confirmed: {{identity_confirmed}}" in prompt
    assert "initialized to false" not in prompt
    assert CLUB_PROPHET_IDENTITY_GUARDRAILS in prompt


def test_pipeline_writes_club_caddie_provider_lookup_and_cancellation_rules(
    tmp_path: Path,
) -> None:
    facility = FacilityConfig(
        slug="club-caddie-course",
        display_name="ClubCaddie Course",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        tee_sheet=TeeSheetProvider.CLUB_CADDIE,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
        enabled_tools=[
            "get-bookings",
            "get-eligibility-for-cancellation",
            "cancel-reservation",
        ],
    )
    sections = GeneratedSections(
        core_shell="Use the configured runtime context.",
        knowledge_base="ClubCaddie Course is a golf facility.",
        logic_module="Use the integrated booking workflow.",
        eligibility_policy=(
            "Initialize the following variables:\n"
            "'date' = requested booking date.\n"
            "'time' = requested tee time.\n"
            "'current_date' = today's date.\n\n"
            "Apply these rules in order:\n"
            "- Do not apply any other eligibility criteria."
        ),
        cancellation_eligibility_policy=(
            "Initialize the following variables:\n"
            "'date' = reservation date.\n"
            "'time' = reservation tee time.\n"
            "'current_date' = today's date.\n"
            "'current_datetime' = current date and time.\n"
            "'hours_until_tee_off' = exact hours until tee off.\n\n"
            "Apply these rules in order:\n"
            "- Do not apply any other eligibility criteria."
        ),
    )

    prompt = write_generation_outputs(
        tmp_path / "output", facility, FactInventory(facts=[]), sections
    ).read_text()

    assert CLUB_CADDIE_GUARDRAILS in prompt
    assert "with only `booking_reference` and `date`" in prompt
    assert "also pass `num_holes` when the lookup returned it" in prompt
    assert "{{identity_confirmed}}" not in prompt


def test_mandatory_transfer_protocol_keeps_self_service_available_after_hours() -> None:
    assert (
        "Current Operating Status controls only whether `transfer_call-staging` may be called."
        in MANDATORY_TRANSFER_PROTOCOL
    )
    assert "every enabled non-transfer tool operate twenty-four hours a day" in (
        MANDATORY_TRANSFER_PROTOCOL
    )
    assert "Never treat `after_hours` as a booking restriction" in (
        MANDATORY_TRANSFER_PROTOCOL
    )


def test_booking_fee_guardrails_apply_to_club_caddie_and_select_booking_boolean() -> None:
    base = _facility().model_copy(update={"tee_sheet": TeeSheetProvider.CLUB_CADDIE})
    no_fee = availability_pricing_guardrail(base)
    assert "`apply_booking_fee: false`" in no_fee
    assert "do not assume all four fields will be present" in no_fee.casefold()

    fee_facility = base.model_copy(
        update={
            "availability_pricing": AvailabilityPricingPolicy(
                speaksport_per_booking_model=True,
                booking_fee_application=BookingFeeApplication.ALL_CALLERS,
            )
        }
    )
    with_fee = availability_pricing_guardrail(fee_facility)
    assert "expected to return all four" in with_fee
    assert "`apply_booking_fee: true`" in with_fee


def test_eligibility_policy_rejects_quoted_variables_after_initialization() -> None:
    policy = """Initialize the following variables:

'date' = requested booking date.
'time' = requested tee time.
'current_date' = today's date.

Apply these rules in order:

- If 'date' is before today, the caller is not eligible.
- Do not apply any other eligibility criteria.
"""

    with pytest.raises(ConfigurationError, match="semantic language"):
        _validate_eligibility_decision_prompt(
            policy,
            label="Booking eligibility policy",
            required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
        )


def test_eligibility_policy_normalizes_colon_initialization() -> None:
    policy = """Initialize the following variables:
- 'date': requested booking date.
- 'time': requested tee time.
- 'current_date': today's date.

Apply these rules in order:
- Do not apply any additional eligibility criteria.
"""

    normalized = _normalize_eligibility_decision_prompt(policy)

    assert "'date' = requested booking date." in normalized
    assert "- 'date':" not in normalized
    assert "Do not apply any other eligibility criteria" in normalized
    _validate_eligibility_decision_prompt(
        normalized,
        label="Booking eligibility policy",
        required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
    )


def test_eligibility_normalizer_canonicalizes_no_other_criteria_wording() -> None:
    booking = """Initialize the following variables:
- 'date': requested booking date
- 'time': requested tee time
- 'current_date': today's local date

Apply these rules in order:
- The requested date and time must be valid.
- No other eligibility criteria may be applied.
"""
    cancellation = """Initialize the following variables:
- 'date': reservation date
- 'time': reservation time
- 'current_date': today's local date
- 'current_datetime': current local timestamp
- 'hours_until_tee_off': exact hours until tee off

Apply these rules in order:
- No other cancellation criteria may be applied.
"""

    normalized_booking = _normalize_eligibility_decision_prompt(
        booking, required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES
    )
    normalized_cancellation = _normalize_eligibility_decision_prompt(
        cancellation, required_variables=CANCELLATION_ELIGIBILITY_REQUIRED_VARIABLES
    )

    assert "Do not apply any other eligibility criteria" in normalized_booking
    assert "Do not apply any other cancellation criteria" in normalized_cancellation
    _validate_eligibility_decision_prompt(
        normalized_booking,
        label="Booking eligibility policy",
        required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
    )
    _validate_eligibility_decision_prompt(
        normalized_cancellation,
        label="Cancellation eligibility policy",
        required_variables=CANCELLATION_ELIGIBILITY_REQUIRED_VARIABLES,
    )


def test_deprecated_member_boolean_is_translated_to_supported_profile_context() -> None:
    normalized = _normalize_deprecated_runtime_placeholders(
        "Determine member pricing using {{customer_is_member}}."
    )

    assert "{{customer_is_member}}" not in normalized
    assert "Customer Passes" in normalized
    assert "Customer Price Class" in normalized
    assert "Customer Groups" in normalized


def test_eligibility_policy_restores_missing_required_runtime_inputs() -> None:
    policy = """Initialize the following variables:
'date' = requested booking date.
'current_date' = today's date.

Apply these rules in order:
- If the requested date has passed, the caller is not eligible.
- Do not apply any other eligibility criteria.
"""

    normalized = _normalize_eligibility_decision_prompt(
        policy,
        required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
    )

    assert "'time' = requested tee time." in normalized
    _validate_eligibility_decision_prompt(
        normalized,
        label="Booking eligibility policy",
        required_variables=BOOKING_ELIGIBILITY_REQUIRED_VARIABLES,
    )
