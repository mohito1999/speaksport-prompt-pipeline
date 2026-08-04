from pathlib import Path

import pytest
from pydantic import ValidationError

from speaksport_pipeline.models import (
    CourseConfiguration,
    FacilityConfig,
    GeneratedSections,
    IntegrationType,
    ModificationPreservationPolicy,
    PromptModificationConfig,
    ReferenceSelection,
)
from speaksport_pipeline.modification import (
    PromptModificationPipeline,
    extract_original_knowledge_base,
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
