from pathlib import Path

from speaksport_pipeline.config import (
    load_runtime_registry,
    load_tool_registry,
    load_yaml,
)
from speaksport_pipeline.generation import assemble_prompt
from speaksport_pipeline.models import (
    AvailabilityPolicy,
    CourseConfiguration,
    FacilityConfig,
    IntegrationType,
    PromptSectionBundle,
    ReferenceSelection,
    TransferPolicy,
)
from speaksport_pipeline.pipeline import (
    MANDATORY_AVAILABILITY_GUARDRAILS,
    SINGLE_PLAYER_PARTIAL_SLOT_GUARDRAIL,
    SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL,
)
from speaksport_pipeline.validation import PromptValidator

ROOT = Path(__file__).resolve().parents[2]


def _facility(mode: IntegrationType = IntegrationType.INTEGRATED) -> FacilityConfig:
    return FacilityConfig(
        slug="example-club",
        display_name="Example Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=mode,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        transfer_policy=TransferPolicy(first_shop_transfer_deflection=True),
        references=ReferenceSelection(
            prompt="2026-07-10",
            eligibility="2026-07-10" if mode == IntegrationType.INTEGRATED else None,
        ),
        booking_url="https://example.com/book" if mode == IntegrationType.NON_INTEGRATED else None,
        enabled_tools=(
            [
                "check-booking-eligibility-staging",
                "get-available-tee-times-staging",
                "book-tee-time-staging",
                "transfer_call-staging",
            ]
            if mode == IntegrationType.INTEGRATED
            else ["send_sms", "transfer_call-staging"]
        ),
    )


def _validator() -> PromptValidator:
    return PromptValidator(
        load_runtime_registry(ROOT),
        load_tool_registry(ROOT),
        load_yaml(ROOT / "config" / "validators.yaml"),
        load_yaml(ROOT / "config" / "global-conventions.yaml"),
    )


def _prompt(
    core: str = (
        "Use {{phone_recognized}}, {{greeting}}, {{disclaimer}}, and {{announcement}}. "
        'Today is {{"now" | date: "%A, %B %d, %Y", "America/New_York"}}, '
        'and the current time is {{"now" | date: "%I:%M %p", "America/New_York"}}. '
        "You are strictly forbidden from calling the `transfer_call-staging` tool without "
        "explicit, verbal confirmation. Our staff in the Golf Shop is currently busy with "
        "guests. Do not call the transfer tool and ask the confirmation question in the same "
        "response turn."
    ),
    logic: str = (
        "Call check-booking-eligibility-staging, then get-available-tee-times-staging, "
        "then book-tee-time-staging. Use transfer_call-staging when confirmed."
    )
    + "\n"
    + MANDATORY_AVAILABILITY_GUARDRAILS
    + "\n"
    + SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL,
    knowledge: str = "Example Club is an example facility.",
) -> str:
    return assemble_prompt(
        PromptSectionBundle(
            core_shell=core,
            knowledge_base=knowledge,
            logic_module=logic,
        )
    )


def test_valid_minimal_prompt_passes_errors_and_reports_length() -> None:
    report = _validator().validate(_prompt(), _facility())

    assert report.valid
    assert report.metrics["knowledge_base_words"] > 0
    assert any(finding.code == "PROMPT_BELOW_TARGET_LENGTH" for finding in report.findings)


def test_missing_or_wrong_local_time_context_is_rejected() -> None:
    missing_time = _prompt(
        core=(
            "Use {{phone_recognized}}, {{greeting}}, {{disclaimer}}, and {{announcement}}. "
            'Today is {{"now" | date: "%A, %B %d, %Y", "America/New_York"}}. '
            "You are strictly forbidden from calling the `transfer_call-staging` tool "
            "without explicit, verbal confirmation. Our staff in the Golf Shop is currently "
            "busy with guests. Do not call the transfer tool and ask the confirmation "
            "question in the same response turn."
        )
    )
    wrong_timezone = _prompt().replace("America/New_York", "America/Detroit")

    for prompt in (missing_time, wrong_timezone):
        report = _validator().validate(prompt, _facility())
        assert any(finding.code == "MISSING_LOCAL_DATETIME_CONTEXT" for finding in report.findings)


def test_shop_transfer_deflection_is_controlled_by_facility_policy() -> None:
    deflection_disabled = _facility().model_copy(
        update={"transfer_policy": TransferPolicy(first_shop_transfer_deflection=False)}
    )
    report_with_unrequested_deflection = _validator().validate(_prompt(), deflection_disabled)
    assert any(
        finding.code == "UNREQUESTED_SHOP_TRANSFER_DEFLECTION"
        for finding in report_with_unrequested_deflection.findings
    )

    prompt_without_deflection = _prompt().replace(
        "Our staff in the Golf Shop is currently busy with guests. ", ""
    )
    report_without_requested_deflection = _validator().validate(
        prompt_without_deflection, _facility()
    )
    assert any(
        finding.code == "MISSING_SHOP_TRANSFER_DEFLECTION"
        for finding in report_without_requested_deflection.findings
    )

    report_without_unrequested_deflection = _validator().validate(
        prompt_without_deflection, deflection_disabled
    )
    assert report_without_unrequested_deflection.valid


def test_unknown_variable_endpoint_version_and_phone_are_rejected() -> None:
    prompt = _prompt(
        core="Use {{unknown_value}} and backend v6. Call 404-555-1212.",
    )
    report = _validator().validate(prompt, _facility())
    codes = {finding.code for finding in report.findings}

    assert not report.valid
    assert {"UNKNOWN_RUNTIME_VARIABLE", "ENDPOINT_VERSION_LABEL", "PHONE_NUMBER_IN_PROMPT"} <= codes


def test_exact_preserved_knowledge_base_may_retain_phone_without_allowing_it_elsewhere() -> None:
    prompt = _prompt(knowledge="Historical contact: 404-555-1212.")

    exact_preservation_report = _validator().validate(
        prompt,
        _facility(),
        allow_phone_numbers_in_exact_knowledge_base=True,
    )
    assert not any(
        finding.code == "PHONE_NUMBER_IN_PROMPT"
        for finding in exact_preservation_report.findings
    )

    phone_outside_knowledge = prompt.replace(
        "<core-shell>", "<core-shell>\nCall 404-555-1212.", 1
    )
    unsafe_report = _validator().validate(
        phone_outside_knowledge,
        _facility(),
        allow_phone_numbers_in_exact_knowledge_base=True,
    )
    assert any(finding.code == "PHONE_NUMBER_IN_PROMPT" for finding in unsafe_report.findings)


def test_non_integrated_prompt_rejects_inventory_tool() -> None:
    prompt = _prompt(logic="Use send_sms, then invoke the get-available-tee-times-staging tool.")
    report = _validator().validate(prompt, _facility(IntegrationType.NON_INTEGRATED))

    assert not report.valid
    assert any(
        finding.code == "INTEGRATED_TOOL_IN_NON_INTEGRATED_PROMPT" for finding in report.findings
    )


def test_reference_facility_leakage_is_rejected() -> None:
    prompt = _prompt(logic="Copy behavior from Sugarmill Woods.")
    report = _validator().validate(prompt, _facility())

    assert any(finding.code == "REFERENCE_FACILITY_LEAKAGE" for finding in report.findings)


def test_missing_availability_guardrails_are_rejected() -> None:
    prompt = _prompt(
        logic=(
            "Call check-booking-eligibility-staging, then get-available-tee-times-staging, "
            "then book-tee-time-staging. Use transfer_call-staging when confirmed."
        )
    )
    report = _validator().validate(prompt, _facility())

    assert any(finding.code == "MISSING_AVAILABILITY_GUARDRAIL" for finding in report.findings)


def test_single_player_availability_policy_must_match_facility() -> None:
    restricted_facility = _facility().model_copy(
        update={
            "availability_policy": AvailabilityPolicy(
                single_player_requires_partially_filled_slot=True
            )
        }
    )
    restricted_prompt = _prompt().replace(
        SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL,
        SINGLE_PLAYER_PARTIAL_SLOT_GUARDRAIL,
    )

    assert _validator().validate(restricted_prompt, restricted_facility).valid
    mismatched = _validator().validate(_prompt(), restricted_facility)
    codes = {finding.code for finding in mismatched.findings}
    assert "MISSING_SINGLE_PLAYER_AVAILABILITY_POLICY" in codes
    assert "CONFLICTING_SINGLE_PLAYER_AVAILABILITY_POLICY" in codes


def test_complete_existing_booking_and_cancellation_flow_passes() -> None:
    facility = _facility().model_copy(
        update={
            "enabled_tools": [
                *_facility().enabled_tools,
                "get-bookings",
                "get-eligibility-for-cancellation",
                "cancel-reservation",
            ]
        }
    )
    prompt = _prompt(
        logic=(
            "Call check-booking-eligibility-staging, then get-available-tee-times-staging, "
            "then book-tee-time-staging. Use transfer_call-staging when confirmed. "
            "For existing reservations, call get-bookings with no parameters. If needed, "
            "call get-bookings again with only booking_reference. Never speak the reference. "
            "For cancellation, call get-eligibility-for-cancellation with the selected date "
            "and time, then call cancel-reservation with the hidden booking_reference only."
        )
        + "\n"
        + MANDATORY_AVAILABILITY_GUARDRAILS
        + "\n"
        + SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL
    )

    report = _validator().validate(prompt, facility)

    assert report.valid


def test_booking_lookup_accepts_no_arguments_wording() -> None:
    facility = _facility().model_copy(
        update={"enabled_tools": [*_facility().enabled_tools, "get-bookings"]}
    )
    prompt = _prompt(
        logic=(
            "Call check-booking-eligibility-staging, then get-available-tee-times-staging, "
            "then book-tee-time-staging. Use transfer_call-staging when confirmed. "
            "Call get-bookings first with no arguments. For fallback, call get-bookings "
            "again with only booking_reference."
        )
        + "\n"
        + MANDATORY_AVAILABILITY_GUARDRAILS
        + "\n"
        + SINGLE_PLAYER_UNRESTRICTED_GUARDRAIL
    )

    assert _validator().validate(prompt, facility).valid


def test_do_not_deflect_wording_is_not_mistaken_for_deflection() -> None:
    facility = _facility().model_copy(
        update={"transfer_policy": TransferPolicy(first_shop_transfer_deflection=False)}
    )
    prompt = _prompt().replace(
        "Our staff in the Golf Shop is currently busy with guests. ",
        "If a caller initially requests the Pro Shop, do not deflect or delay the request. ",
    )

    report = _validator().validate(prompt, facility)
    assert not any(
        finding.code == "UNREQUESTED_SHOP_TRANSFER_DEFLECTION" for finding in report.findings
    )


def test_partial_cancellation_tool_set_is_rejected() -> None:
    facility = _facility().model_copy(
        update={
            "enabled_tools": [
                *_facility().enabled_tools,
                "get-eligibility-for-cancellation",
                "cancel-reservation",
            ]
        }
    )

    report = _validator().validate(_prompt(), facility)

    assert any(finding.code == "INCOMPLETE_CANCELLATION_TOOL_SET" for finding in report.findings)
