import json
from pathlib import Path

from speaksport_pipeline.config import load_model_configuration, load_tool_registry
from speaksport_pipeline.manifests import create_run_manifest
from speaksport_pipeline.models import (
    CourseConfiguration,
    FacilityConfig,
    IntegrationType,
    ReferenceSelection,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_manifest_creates_immutable_run_layout_and_hashes_inputs(tmp_path: Path) -> None:
    facility = FacilityConfig(
        slug="example-club",
        display_name="Example Club",
        website_url="https://example.com",
        timezone="America/New_York",
        integration_type=IntegrationType.INTEGRATED,
        course_configuration=CourseConfiguration.SINGLE_COURSE,
        references=ReferenceSelection(prompt="2026-07-10", eligibility="2026-07-10"),
        enabled_tools=["check-booking-eligibility-staging"],
    )
    input_path = tmp_path / "facilities" / "example-club" / "facility.yaml"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("slug: example-club\n", encoding="utf-8")

    run_dir, manifest = create_run_manifest(
        tmp_path,
        facility,
        load_tool_registry(PROJECT_ROOT),
        load_model_configuration(PROJECT_ROOT),
        input_paths=[input_path],
    )

    stored = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert stored["run_id"] == manifest.run_id
    assert stored["inputs"][0]["sha256"]
    assert (run_dir / "crawl" / "raw").is_dir()
    assert (run_dir / "output").is_dir()
