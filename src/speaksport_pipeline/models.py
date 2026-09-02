from __future__ import annotations

import re
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntegrationType(StrEnum):
    INTEGRATED = "integrated"
    NON_INTEGRATED = "non_integrated"


class CourseConfiguration(StrEnum):
    SINGLE_COURSE = "single_course"
    MULTI_COURSE = "multi_course"


class CourseValuesSource(StrEnum):
    CONFIGURED = "configured"
    RUNTIME = "runtime"


class TeeSheetProvider(StrEnum):
    UNSPECIFIED = "unspecified"
    FOREUP = "foreup"
    CLUB_PROPHET = "club_prophet"
    OTHER = "other"


class BookingFeeApplication(StrEnum):
    NONE = "none"
    ALL_CALLERS = "all_callers"
    CONDITIONAL = "conditional"


class ReferenceStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class ReferenceMode(StrEnum):
    INTEGRATED = "integrated"
    NON_INTEGRATED = "non_integrated"
    ELIGIBILITY = "eligibility"


class CrawlStatus(StrEnum):
    CREATED = "created"
    SCRAPING = "scraping"
    COMPLETED = "completed"
    FAILED = "failed"


class ReferenceSelection(StrictModel):
    prompt: str
    eligibility: str | None = None


class TransferDestination(StrictModel):
    identifier: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    responsibility: str = Field(min_length=1)
    display_name: str | None = None


class CallerDetailRequirements(StrictModel):
    first_name: bool = True
    last_name: bool = True
    email: bool = True
    confirm_existing_email: bool = True


class TransferPolicy(StrictModel):
    first_shop_transfer_deflection: bool = False
    allow_after_hours_transfers: bool = False


class AvailabilityPolicy(StrictModel):
    single_player_requires_partially_filled_slot: bool = False


class AvailabilityPricingPolicy(StrictModel):
    speaksport_per_booking_model: bool = False
    booking_fee_application: BookingFeeApplication = BookingFeeApplication.NONE
    disclose_booking_fee_when_applied: bool = False
    booking_fee_rules: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_booking_fee_configuration(self) -> AvailabilityPricingPolicy:
        if (
            not self.speaksport_per_booking_model
            and self.booking_fee_application != BookingFeeApplication.NONE
        ):
            raise ValueError(
                "booking fees require speaksport_per_booking_model to be true"
            )
        if (
            self.booking_fee_application == BookingFeeApplication.CONDITIONAL
            and not self.booking_fee_rules
        ):
            raise ValueError("conditional booking fees require booking_fee_rules")
        if (
            self.booking_fee_application != BookingFeeApplication.CONDITIONAL
            and self.booking_fee_rules
        ):
            raise ValueError(
                "booking_fee_rules are valid only for conditional booking fees"
            )
        return self


class FacilityConfig(StrictModel):
    schema_version: Literal["1"] = "1"
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
    display_name: str = Field(min_length=1)
    website_url: HttpUrl
    timezone: str = Field(min_length=1)
    integration_type: IntegrationType
    tee_sheet: TeeSheetProvider = TeeSheetProvider.UNSPECIFIED
    course_configuration: CourseConfiguration
    course_values_source: CourseValuesSource = CourseValuesSource.CONFIGURED
    expected_course_count: int | None = Field(default=None, ge=2)
    search_all_courses_for_availability: bool = False
    exact_course_values: list[str] = Field(default_factory=list)
    references: ReferenceSelection
    enabled_tools: list[str] = Field(default_factory=list)
    greeting: str = ""
    disclaimer: str = ""
    announcement: str = ""
    booking_url: HttpUrl | None = None
    transfer_policy: TransferPolicy = Field(default_factory=TransferPolicy)
    availability_policy: AvailabilityPolicy = Field(default_factory=AvailabilityPolicy)
    availability_pricing: AvailabilityPricingPolicy = Field(
        default_factory=AvailabilityPricingPolicy
    )
    transfer_destinations: list[TransferDestination] = Field(default_factory=list)
    booking_rules: list[str] = Field(default_factory=list)
    cancellation_modification_policy: str = ""
    walking_riding_cart_policies: list[str] = Field(default_factory=list)
    caller_details: CallerDetailRequirements = Field(default_factory=CallerDetailRequirements)
    allowed_source_urls: list[str] = Field(default_factory=list)
    included_source_paths: list[str] = Field(default_factory=list)
    excluded_source_paths: list[str] = Field(default_factory=list)
    crawl_entire_domain: bool = False
    allow_subdomains: bool = False
    ignored_facts: list[str] = Field(default_factory=list)
    reference_leakage_exceptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> FacilityConfig:
        if self.course_configuration == CourseConfiguration.MULTI_COURSE:
            if (
                self.course_values_source == CourseValuesSource.CONFIGURED
                and not self.exact_course_values
            ):
                raise ValueError("multi_course facilities require exact_course_values")
            if len(set(self.exact_course_values)) != len(self.exact_course_values):
                raise ValueError("exact_course_values must not contain duplicates")
            if self.course_values_source == CourseValuesSource.RUNTIME:
                if self.exact_course_values:
                    raise ValueError(
                        "runtime course values must come from {{courses}}, not exact_course_values"
                    )
                if self.expected_course_count is None:
                    raise ValueError(
                        "runtime multi_course facilities require expected_course_count"
                    )
        else:
            if self.course_values_source != CourseValuesSource.CONFIGURED:
                raise ValueError("runtime course values require multi_course configuration")
            if self.expected_course_count is not None:
                raise ValueError("expected_course_count is only valid for runtime course values")
            if self.search_all_courses_for_availability:
                raise ValueError(
                    "search_all_courses_for_availability requires multi_course configuration"
                )
        if self.integration_type == IntegrationType.NON_INTEGRATED and self.booking_url is None:
            raise ValueError("non_integrated facilities require booking_url")
        if self.integration_type == IntegrationType.INTEGRATED and not self.references.eligibility:
            raise ValueError("integrated facilities require an eligibility reference version")
        if len(set(self.enabled_tools)) != len(self.enabled_tools):
            raise ValueError("enabled_tools must not contain duplicates")
        identity_tools = {"get_customer_records", "confirm_identity"}
        enabled_identity_tools = identity_tools & set(self.enabled_tools)
        if self.tee_sheet == TeeSheetProvider.CLUB_PROPHET:
            if self.integration_type != IntegrationType.INTEGRATED:
                raise ValueError("club_prophet tee sheets require integrated mode")
            missing = identity_tools - set(self.enabled_tools)
            if missing:
                raise ValueError(
                    "club_prophet facilities require identity tools: "
                    + ", ".join(sorted(missing))
                )
        elif enabled_identity_tools:
            raise ValueError(
                "get_customer_records and confirm_identity may be enabled only when "
                "tee_sheet is club_prophet"
            )
        return self


class RuntimeVariable(StrictModel):
    name: str = Field(pattern=r"^[a-z_][a-z0-9_]*$")
    placeholder: str
    required: bool
    value_type: Literal["string", "boolean", "array", "number"]
    owner: str

    @model_validator(mode="after")
    def placeholder_matches_name(self) -> RuntimeVariable:
        if self.placeholder != "{{" + self.name + "}}":
            raise ValueError(f"placeholder for {self.name} must be {{{{{self.name}}}}}")
        return self


class RuntimeVariableRegistry(StrictModel):
    schema_version: Literal["1"] = "1"
    status: str
    variables: list[RuntimeVariable]

    @model_validator(mode="after")
    def unique_names(self) -> RuntimeVariableRegistry:
        names = [variable.name for variable in self.variables]
        if len(names) != len(set(names)):
            raise ValueError("runtime variable names must be unique")
        return self


class ToolField(StrictModel):
    type: str
    format: str | None = None
    allowed_values: list[Any] | None = None
    required: bool | None = None
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None


class ToolContract(StrictModel):
    capability: str
    logical_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    compatible_modes: list[IntegrationType]
    required_arguments: dict[str, ToolField]
    optional_arguments: dict[str, ToolField]
    result_fields: dict[str, ToolField]
    preconditions: list[str]


class ToolContractRegistry(StrictModel):
    schema_version: Literal["1"] = "1"
    version: str
    status: str
    tools: list[ToolContract]

    @model_validator(mode="after")
    def unique_tools(self) -> ToolContractRegistry:
        names = [tool.logical_name for tool in self.tools]
        capabilities = [tool.capability for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("logical tool names must be unique")
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("tool capabilities must be unique")
        return self


class ModelConfiguration(StrictModel):
    schema_version: Literal["1"] = "1"
    status: str
    provider: Literal["openrouter"] = "openrouter"
    model_slug: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    max_cost_usd: float | None = Field(default=None, gt=0)
    timeout_seconds: int = Field(default=120, ge=1, le=600)
    max_output_tokens: int = Field(default=20000, ge=1000, le=128000)
    reproducibility_requires_pinned_model: bool = True


class ReferenceMetadata(StrictModel):
    version: str
    created_date: date
    status: ReferenceStatus
    summary: str
    compatible_tool_contract_version: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReferenceRecord(StrictModel):
    mode: ReferenceMode
    directory: str
    content_file: str
    metadata: ReferenceMetadata
    generation_instructions_file: str | None = None


class PromptSectionBundle(StrictModel):
    core_shell: str = Field(min_length=1)
    knowledge_base: str = Field(min_length=1)
    logic_module: str = Field(min_length=1)
    closing_core_shells: list[str] = Field(default_factory=list)


class InputArtifact(StrictModel):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class RunManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    facility_slug: str
    application_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal[
        "CREATED", "CRAWLED", "EXTRACTED", "GENERATED", "ASSEMBLED", "VALIDATED", "FAILED"
    ] = "CREATED"
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    inputs: list[InputArtifact] = Field(default_factory=list)
    reference_versions: dict[str, str]
    tool_contract_version: str
    requested_model: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    max_cost_usd: float | None = None
    timeout_seconds: int | None = None
    returned_model: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = None
    crawl_job_id: str | None = None
    word_counts: dict[str, int] = Field(default_factory=dict)
    validation_outcome: str | None = None


class CrawlRequest(StrictModel):
    url: str
    sitemap: Literal["include", "skip", "only"] = "include"
    crawl_entire_domain: bool = False
    limit: int = Field(default=50, ge=1, le=50)
    allow_external_links: bool = False
    allow_subdomains: bool = False
    ignore_robots_txt: bool = False
    exclude_paths: list[str] = Field(default_factory=list)
    include_paths: list[str] = Field(default_factory=list)
    # Golf-facility sites commonly use WordPress page builders whose actual body is
    # incorrectly discarded by Firecrawl's main-content heuristic. Full-page mode
    # retains that body; repeated navigation is handled during extraction.
    only_main_content: bool = False
    # Provisioning must reflect the site as it exists now, not a cached scrape.
    max_age: int = 0
    parsers: list[str] = Field(default_factory=lambda: ["pdf"])
    formats: list[str] = Field(default_factory=lambda: ["markdown"])


class CrawlState(StrictModel):
    schema_version: Literal["1"] = "1"
    job_id: str
    status_url: str
    status: CrawlStatus = CrawlStatus.CREATED
    request: CrawlRequest
    request_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    total: int = 0
    completed: int = 0
    credits_used: int = 0
    next_url: str | None = None
    page_hashes: list[str] = Field(default_factory=list)
    error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CrawledPage(StrictModel):
    source_url: str
    canonical_url: str | None = None
    title: str | None = None
    status_code: int | None = None
    crawl_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    markdown: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    crawl_job_id: str
    request_options_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class NormalizedPage(StrictModel):
    source_identifier: str
    source_url: str
    title: str | None = None
    markdown: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class Fact(StrictModel):
    category: str
    subject: str
    fact_text: str
    normalized_value: str | None = None
    source_type: Literal["website", "pdf", "client_note", "facility_configuration"]
    source_identifier: str
    source_url_or_file: str
    source_excerpt: str
    time_sensitive: bool = False
    confidence: float = Field(ge=0, le=1)
    conflict_group: str | None = None


class FactInventory(StrictModel):
    facts: list[Fact]
    open_questions: list[str] = Field(default_factory=list)


class GeneratedSections(StrictModel):
    core_shell: str
    knowledge_base: str
    logic_module: str
    closing_core_shells: list[str] = Field(default_factory=list)
    eligibility_policy: str | None = None
    cancellation_eligibility_policy: str | None = None
    transfer_destinations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    generation_notes: list[str] = Field(default_factory=list)


class ModificationPreservationPolicy(StrictModel):
    knowledge_base: Literal["exact", "revise"] = "exact"
    identity_and_voice: Literal["preserve", "revise"] = "preserve"
    transfer_destinations: Literal["preserve", "revise"] = "preserve"
    unmentioned_behavior: Literal[
        "preserve_when_compatible", "replace_with_current_conventions"
    ] = "preserve_when_compatible"


class PromptModificationConfig(StrictModel):
    schema_version: Literal["1"] = "1"
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
    display_name: str = Field(min_length=1)
    original_prompt_file: str = "original-prompt.md"
    update_notes_file: str = "update-notes.md"
    additional_context_files: list[str] = Field(default_factory=list)
    required_output_markers: list[str] = Field(default_factory=list)
    forbidden_output_patterns: list[str] = Field(default_factory=list)
    preservation: ModificationPreservationPolicy = Field(
        default_factory=ModificationPreservationPolicy
    )

    @model_validator(mode="after")
    def validate_local_file_names(self) -> PromptModificationConfig:
        values = [
            self.original_prompt_file,
            self.update_notes_file,
            *self.additional_context_files,
        ]
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not value.strip():
                raise ValueError("modification input files must be safe relative paths")
        if len(values) != len(set(values)):
            raise ValueError("modification input files must not contain duplicates")
        for pattern in self.forbidden_output_patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid forbidden output regex: {pattern}") from exc
        return self


class LLMResult(StrictModel):
    request_id: str
    requested_model: str
    returned_model: str
    content: dict[str, Any]
    usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = None
