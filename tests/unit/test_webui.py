from __future__ import annotations

import json
from pathlib import Path

import pytest

from speaksport_pipeline.exceptions import SpeakSportError
from speaksport_pipeline.webui import (
    STATIC_ROOT,
    UIService,
    _facility_payload,
    _modification_payload,
    _scan_runs,
    _write_facility,
    _write_modification,
)


def _facility_config(slug: str = "example-golf") -> dict[str, object]:
    return {
        "schema_version": "1",
        "slug": slug,
        "display_name": "Example Golf Club",
        "website_url": "https://example.com/",
        "timezone": "America/New_York",
        "integration_type": "integrated",
        "tee_sheet": "foreup",
        "course_configuration": "single_course",
        "course_values_source": "configured",
        "expected_course_count": None,
        "search_all_courses_for_availability": False,
        "exact_course_values": [],
        "references": {"prompt": "2026-07-10", "eligibility": "2026-07-10"},
        "enabled_tools": [
            "check-booking-eligibility-staging",
            "get-available-tee-times-staging",
            "book-tee-time-staging",
            "transfer_call-staging",
        ],
        "greeting": "",
        "disclaimer": "",
        "announcement": "",
        "booking_url": None,
        "transfer_policy": {"first_shop_transfer_deflection": True},
        "availability_policy": {"single_player_requires_partially_filled_slot": False},
        "availability_pricing": {
            "speaksport_per_booking_model": False,
            "booking_fee_application": "none",
            "disclose_booking_fee_when_applied": False,
            "booking_fee_rules": [],
        },
        "transfer_destinations": [
            {
                "identifier": "pro_shop",
                "display_name": "Pro Shop",
                "responsibility": "General golf operations.",
            }
        ],
        "booking_rules": ["Public players may book seven days in advance."],
        "cancellation_modification_policy": "Cancellations require 24 hours.",
        "walking_riding_cart_policies": [],
        "caller_details": {
            "first_name": True,
            "last_name": True,
            "email": True,
            "confirm_existing_email": True,
        },
        "allowed_source_urls": ["https://example.com/"],
        "included_source_paths": [],
        "excluded_source_paths": [],
        "crawl_entire_domain": False,
        "allow_subdomains": False,
        "ignored_facts": [],
        "reference_leakage_exceptions": [],
    }


def test_ui_static_product_surface_exists() -> None:
    assert (STATIC_ROOT / "index.html").is_file()
    assert (STATIC_ROOT / "styles.css").is_file()
    assert (STATIC_ROOT / "app.js").is_file()
    assert "New facility" in (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    assert "Prompt update" in (STATIC_ROOT / "index.html").read_text(encoding="utf-8")


def test_write_and_edit_facility_without_hand_editing_yaml(tmp_path: Path) -> None:
    payload = {
        "config": _facility_config(),
        "notes": {
            "client_notes": "Use the complete integrated flow.",
            "booking_policies": "Seven-day public window.",
            "transfer_notes": "Only use pro_shop.",
            "known_exclusions": "Do not invent rates.",
        },
    }

    assert _write_facility(tmp_path, payload) == "example-golf"
    saved = _facility_payload(tmp_path, "example-golf")
    assert saved["config"]["display_name"] == "Example Golf Club"
    assert saved["config"]["transfer_policy"]["first_shop_transfer_deflection"] is True
    assert saved["notes"]["client_notes"].startswith("# Client notes")

    payload["config"]["display_name"] = "Edited Golf Club"
    _write_facility(tmp_path, payload, replace=True)
    assert _facility_payload(tmp_path, "example-golf")["config"]["display_name"] == (
        "Edited Golf Club"
    )


def test_write_modification_preserves_original_prompt_and_notes(tmp_path: Path) -> None:
    config = _facility_config("example-update")
    config["tee_sheet"] = "club_prophet"
    config["enabled_tools"] = [
        *config["enabled_tools"],  # type: ignore[index]
        "get_customer_records",
        "confirm_identity",
    ]
    payload = {
        "config": {
            "schema_version": "1",
            "slug": "example-update",
            "display_name": "Example Golf Club",
            "original_prompt_file": "original-prompt.md",
            "update_notes_file": "update-notes.md",
            "additional_context_files": [],
            "required_output_markers": ["`confirm_identity`"],
            "forbidden_output_patterns": [],
            "preservation": {
                "knowledge_base": "exact",
                "identity_and_voice": "preserve",
                "transfer_destinations": "preserve",
                "unmentioned_behavior": "preserve_when_compatible",
            },
        },
        "facility": config,
        "original_prompt": "<core-shell>Voice</core-shell>\n<knowledge-base>Facts</knowledge-base>",
        "update_notes": "Add the current Club Prophet identity flow.",
    }

    assert _write_modification(tmp_path, payload) == "example-update"
    saved = _modification_payload(tmp_path, "example-update")
    assert "<knowledge-base>Facts</knowledge-base>" in saved["original_prompt"]
    assert "Club Prophet identity" in saved["update_notes"]

    payload["update_notes"] = "Keep the identity flow and revise transfer routing."
    _write_modification(tmp_path, payload, replace=True)
    edited = _modification_payload(tmp_path, "example-update")
    assert "revise transfer routing" in edited["update_notes"]


def test_run_history_and_safe_artifact_view(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "example-golf" / "run-123"
    output = run / "output"
    output.mkdir(parents=True)
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-123",
                "facility_slug": "example-golf",
                "status": "VALIDATED",
                "created_at": "2026-08-25T12:00:00+00:00",
                "cost_usd": 0.42,
                "validation_outcome": "PASS",
            }
        ),
        encoding="utf-8",
    )
    (output / "unified-vapi-prompt.md").write_text("Prompt", encoding="utf-8")
    (output / "qa-report.md").write_text("Outcome: PASS\n", encoding="utf-8")

    runs = _scan_runs(tmp_path)
    assert runs[0]["run_id"] == "run-123"
    assert runs[0]["artifacts"][0]["name"] == "unified-vapi-prompt.md"

    service = UIService(tmp_path)
    assert service.safe_file(runs[0]["artifacts"][0]["path"]).read_text() == "Prompt"
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    with pytest.raises(SpeakSportError):
        service.safe_file(".env")
