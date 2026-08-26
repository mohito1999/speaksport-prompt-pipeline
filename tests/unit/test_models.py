import pytest
from pydantic import ValidationError

from speaksport_pipeline.models import (
    AvailabilityPolicy,
    AvailabilityPricingPolicy,
    BookingFeeApplication,
    CourseConfiguration,
    CourseValuesSource,
    FacilityConfig,
    IntegrationType,
    ReferenceSelection,
    TeeSheetProvider,
)


def test_availability_pricing_defaults_to_no_booking_fee_and_validates_conditions() -> None:
    policy = AvailabilityPricingPolicy()
    assert not policy.speaksport_per_booking_model
    assert policy.booking_fee_application == BookingFeeApplication.NONE

    conditional = AvailabilityPricingPolicy(
        speaksport_per_booking_model=True,
        booking_fee_application=BookingFeeApplication.CONDITIONAL,
        disclose_booking_fee_when_applied=True,
        booking_fee_rules=["Public callers pay the fee; members are exempt."],
    )
    assert conditional.booking_fee_rules

    with pytest.raises(ValidationError, match="require booking_fee_rules"):
        AvailabilityPricingPolicy(
            speaksport_per_booking_model=True,
            booking_fee_application=BookingFeeApplication.CONDITIONAL,
        )

    with pytest.raises(ValidationError, match="speaksport_per_booking_model"):
        AvailabilityPricingPolicy(
            booking_fee_application=BookingFeeApplication.ALL_CALLERS,
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


def test_multi_course_facility_accepts_runtime_course_values() -> None:
    configured = FacilityConfig(
        slug="example-club",
        display_name="Example Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        course_configuration=CourseConfiguration.MULTI_COURSE,
        course_values_source=CourseValuesSource.RUNTIME,
        expected_course_count=2,
        search_all_courses_for_availability=True,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
    )

    assert configured.exact_course_values == []
    assert configured.expected_course_count == 2


def test_runtime_course_values_require_expected_count() -> None:
    with pytest.raises(ValidationError, match="expected_course_count"):
        FacilityConfig(
            slug="example-club",
            display_name="Example Club",
            website_url="https://example.com",
            timezone="America/New_York",
            integration_type=IntegrationType.INTEGRATED,
            course_configuration=CourseConfiguration.MULTI_COURSE,
            course_values_source=CourseValuesSource.RUNTIME,
            references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
        )


def test_club_prophet_requires_both_identity_tools() -> None:
    with pytest.raises(ValidationError, match="club_prophet facilities require identity tools"):
        FacilityConfig(
            slug="example-club",
            display_name="Example Club",
            website_url="https://example.com",
            timezone="America/New_York",
            integration_type=IntegrationType.INTEGRATED,
            tee_sheet=TeeSheetProvider.CLUB_PROPHET,
            course_configuration=CourseConfiguration.SINGLE_COURSE,
            references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
            enabled_tools=["get_customer_records"],
        )

    configured = FacilityConfig(
        slug="example-club",
        display_name="Example Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        tee_sheet=TeeSheetProvider.CLUB_PROPHET,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
        enabled_tools=["get_customer_records", "confirm_identity"],
    )

    assert configured.tee_sheet == TeeSheetProvider.CLUB_PROPHET


def test_identity_tools_are_rejected_for_non_club_prophet_facility() -> None:
    with pytest.raises(ValidationError, match="only when tee_sheet is club_prophet"):
        FacilityConfig(
            slug="example-club",
            display_name="Example Club",
            website_url="https://example.com",
            timezone="America/New_York",
            integration_type=IntegrationType.INTEGRATED,
            tee_sheet=TeeSheetProvider.FOREUP,
            course_configuration=CourseConfiguration.SINGLE_COURSE,
            references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
            enabled_tools=["get_customer_records", "confirm_identity"],
        )
