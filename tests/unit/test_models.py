import pytest
from pydantic import ValidationError

from speaksport_pipeline.models import (
    AvailabilityPolicy,
    CourseConfiguration,
    FacilityConfig,
    IntegrationType,
    ReferenceSelection,
)


def test_single_player_partial_slot_policy_defaults_false_and_accepts_true() -> None:
    base = FacilityConfig(
        slug="example-club",
        display_name="Example Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
    )

    assert not base.availability_policy.single_player_requires_partially_filled_slot
    configured = base.model_copy(
        update={
            "availability_policy": AvailabilityPolicy(
                single_player_requires_partially_filled_slot=True
            )
        }
    )
    assert configured.availability_policy.single_player_requires_partially_filled_slot


def test_non_integrated_facility_requires_booking_url() -> None:
    with pytest.raises(ValidationError, match="booking_url"):
        FacilityConfig(
            slug="example-club",
            display_name="Example Club",
            website_url="https://example.com",
            timezone="America/New_York",
            integration_type=IntegrationType.NON_INTEGRATED,
            course_configuration=CourseConfiguration.SINGLE_COURSE,
            references=ReferenceSelection(prompt="2026-07-10"),
        )


def test_multi_course_facility_requires_exact_values() -> None:
    with pytest.raises(ValidationError, match="exact_course_values"):
        FacilityConfig(
            slug="example-club",
            display_name="Example Club",
            website_url="https://example.com",
            timezone="America/New_York",
            integration_type=IntegrationType.INTEGRATED,
            course_configuration=CourseConfiguration.MULTI_COURSE,
            references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
        )
