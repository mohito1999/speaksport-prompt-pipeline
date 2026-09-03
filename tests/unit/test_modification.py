from pathlib import Path

import pytest
from pydantic import ValidationError

from speaksport_pipeline.exceptions import ConfigurationError
from speaksport_pipeline.models import (
    AvailabilityPricingPolicy,
    BookingFeeApplication,
    CourseConfiguration,
    FacilityConfig,
    GeneratedSections,
    IntegrationType,
    ModificationPreservationPolicy,
    PromptModificationConfig,
    ReferenceSelection,
    TeeSheetProvider,
)
from speaksport_pipeline.modification import (
    PromptModificationPipeline,
    extract_original_knowledge_base,
    extract_original_policy_evidence,
    validate_modification_requirements,
    write_modification_outputs,
)

ORIGINAL = """<core-shell>

# Identity
You are Birdie.

</core-shell>

<knowledge-base>

# Detailed facts
- Membership Alpha costs one hundred dollars and includes range access.
- The restaurant opens at eleven o'clock A M.

</knowledge-base>

<logic-module>

Use legacy booking tools.

</logic-module>
"""


def _facility() -> FacilityConfig:
    return FacilityConfig(
        slug="legacy-club",
        display_name="Legacy Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
        enabled_tools=[
            "check-booking-eligibility-staging",
            "get-available-tee-times-staging",
            "book-tee-time-staging",
            "transfer_call-staging",
        ],
    )


def _sections(knowledge_base: str = "Model-generated summary") -> GeneratedSections:
    return GeneratedSections(
        core_shell="Use the current runtime and transfer conventions.",
        knowledge_base=knowledge_base,
        logic_module="Use the current integrated tools in their required order.",
        eligibility_policy=(
            "Initialize the following variables:\n"
            "'date' = requested booking date.\n"
            "'time' = requested booking time.\n"
            "'current_date' = today's local date.\n\n"
            "Apply these rules in order:\n"
            "- If the requested date is before today, return ineligible.\n"
            "- Do not apply any other eligibility criteria."
        ),
        generation_notes=["Migrated legacy booking tools."],
    )


def test_extract_original_knowledge_base_requires_one_block() -> None:
    assert "Membership Alpha" in extract_original_knowledge_base(ORIGINAL)
    with pytest.raises(Exception, match="exactly one"):
        extract_original_knowledge_base("No knowledge block")


def test_extract_original_policy_evidence_finds_business_rules() -> None:
    original = ORIGINAL.replace(
        "Use legacy booking tools.",
        "Public players may book seven calendar days in advance.\n"
        "Members may book fourteen calendar days in advance.\n"
        "Cancellations require at least twenty-four hours notice.",
    )

    booking = extract_original_policy_evidence(original, kind="booking")
    cancellation = extract_original_policy_evidence(original, kind="cancellation")

    assert "seven calendar days" in booking
    assert "fourteen calendar days" in booking
    assert "twenty-four hours" in cancellation


def test_exact_mode_restores_original_knowledge_base_and_writes_diffs(tmp_path: Path) -> None:
    modification = PromptModificationConfig(
        slug="legacy-club",
        display_name="Legacy Club",
        preservation=ModificationPreservationPolicy(knowledge_base="exact"),
    )
    finalized = PromptModificationPipeline._finalize(
        _sections(), _facility(), modification, ORIGINAL
    )

    assert finalized.knowledge_base == extract_original_knowledge_base(ORIGINAL)
    prompt_path = write_modification_outputs(
        run_directory=tmp_path,
        facility=_facility(),
        modification=modification,
        original_prompt=ORIGINAL,
        sections=finalized,
    )

    updated = prompt_path.read_text(encoding="utf-8")
    assert "Membership Alpha costs one hundred dollars" in updated
    assert (tmp_path / "output" / "original-vs-updated.diff.md").is_file()
    assert (tmp_path / "output" / "original-vs-updated.html").is_file()
    report = (tmp_path / "output" / "preservation-report.json").read_text()
    assert '"knowledge_base_exactly_preserved": true' in report


def test_revise_mode_accepts_updated_knowledge_base() -> None:
    modification = PromptModificationConfig(
        slug="legacy-club",
        display_name="Legacy Club",
        preservation=ModificationPreservationPolicy(knowledge_base="revise"),
    )
    finalized = PromptModificationPipeline._finalize(
        _sections("Approved revised knowledge."), _facility(), modification, ORIGINAL
    )

    assert finalized.knowledge_base == "Approved revised knowledge."


def test_modification_rejects_shallow_policy_when_original_has_booking_rules() -> None:
    original = ORIGINAL.replace(
        "Use legacy booking tools.",
        "Public players may book seven calendar days in advance.",
    )
    shallow = _sections().model_copy(
        update={
            "eligibility_policy": (
                "Initialize the following variables:\n"
                "'date' = requested booking date.\n"
                "'time' = requested booking time.\n"
                "'current_date' = today's local date.\n\n"
                "Apply these rules in order:\n"
                "- The requested booking date and time must be valid.\n"
                "- Do not apply any other eligibility criteria."
            )
        }
    )

    with pytest.raises(ConfigurationError, match="ignored substantive rules"):
        PromptModificationPipeline._finalize(
            shallow,
            _facility(),
            PromptModificationConfig(slug="legacy-club", display_name="Legacy Club"),
            original,
        )


def test_modification_config_rejects_paths_outside_project() -> None:
    with pytest.raises(ValidationError, match="safe relative paths"):
        PromptModificationConfig(
            slug="legacy-club",
            display_name="Legacy Club",
            original_prompt_file="../outside.md",
        )


def test_modification_specific_required_and_forbidden_content_is_validated() -> None:
    modification = PromptModificationConfig(
        slug="legacy-club",
        display_name="Legacy Club",
        required_output_markers=["Pro Shop is closed"],
        forbidden_output_patterns=["legacy-tool"],
    )

    findings = validate_modification_requirements("Use legacy-tool.", modification)
    codes = {finding.code for finding in findings}
    assert "MISSING_MODIFICATION_REQUIREMENT" in codes
    assert "FORBIDDEN_MODIFICATION_CONTENT" in codes


def test_club_caddie_modification_adds_cancellation_and_booking_fee_rules(
    tmp_path: Path,
) -> None:
    facility = _facility().model_copy(
        update={
            "tee_sheet": TeeSheetProvider.CLUB_CADDIE,
            "enabled_tools": [
                *_facility().enabled_tools,
                "get-bookings",
                "get-eligibility-for-cancellation",
                "cancel-reservation",
            ],
            "availability_pricing": AvailabilityPricingPolicy(
                speaksport_per_booking_model=True,
                booking_fee_application=BookingFeeApplication.ALL_CALLERS,
            ),
        }
    )
    modification = PromptModificationConfig(
        slug="legacy-club",
        display_name="Legacy Club",
        preservation=ModificationPreservationPolicy(knowledge_base="exact"),
    )

    prompt_path = write_modification_outputs(
        run_directory=tmp_path,
        facility=facility,
        modification=modification,
        original_prompt=ORIGINAL,
        sections=_sections(),
    )
    updated = prompt_path.read_text(encoding="utf-8")

    assert "## ClubCaddie Provider Rules — Mandatory" in updated
    assert "with only `booking_reference` and `date`" in updated
    assert "`apply_booking_fee: true`" in updated
    assert "expected to return all four" in updated
