from __future__ import annotations

import difflib
import json
import os
import re
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from pydantic import ValidationError

from . import __version__
from .cache import StageCache
from .config import (
    ReferenceRegistry,
    dump_yaml,
    find_project_root,
    load_effective_model_configuration,
    load_facility,
    load_modification,
    load_modification_facility,
    load_runtime_registry,
    load_tool_registry,
    load_yaml,
)
from .crawling import normalize_raw_pages
from .exceptions import BudgetExceededError, SpeakSportError
from .generation import assemble_prompt
from .hashing import sha256_file
from .manifests import (
    create_run_manifest,
    latest_run_directory,
    load_manifest,
    save_manifest,
)
from .models import (
    AvailabilityPolicy,
    CourseConfiguration,
    CrawlRequest,
    FacilityConfig,
    InputArtifact,
    IntegrationType,
    ModificationPreservationPolicy,
    PromptModificationConfig,
    PromptSectionBundle,
    ReferenceMode,
    ReferenceSelection,
    TransferDestination,
    TransferPolicy,
)
from .modification import (
    PromptModificationPipeline,
    create_modification_run,
    extract_original_knowledge_base,
    save_modification_manifest,
    validate_modification_requirements,
    write_modification_outputs,
)
from .pipeline import PromptPipeline, write_generation_outputs
from .providers import FirecrawlClient, OpenRouterClient
from .security import redact_text
from .validation import PromptValidator

app = typer.Typer(
    name="speaksport",
    help="Build and validate auditable SpeakSport facility prompt packages.",
    no_args_is_help=True,
)
facility_app = typer.Typer(help="Create and inspect facility intake directories.")
references_app = typer.Typer(help="Inspect and activate versioned reference assets.")
manifest_app = typer.Typer(help="Create immutable local run manifests.")
modify_app = typer.Typer(
    help="Update existing production prompts without invoking the new-facility crawl pipeline."
)
app.add_typer(facility_app, name="facility")
app.add_typer(references_app, name="references")
app.add_typer(manifest_app, name="manifest")
app.add_typer(modify_app, name="modify")


def _root() -> Path:
    return find_project_root()


def _fail(exc: Exception, exit_code: int = 1) -> None:
    typer.secho(redact_text(str(exc)), fg=typer.colors.RED, err=True)
    raise typer.Exit(exit_code) from exc


def _validator(root: Path) -> PromptValidator:
    return PromptValidator(
        runtime_registry=load_runtime_registry(root),
        tool_registry=load_tool_registry(root),
        validator_config=load_yaml(root / "config" / "validators.yaml"),
        global_conventions=load_yaml(root / "config" / "global-conventions.yaml"),
    )


@app.callback()
def main(
    version: Annotated[
        bool | None, typer.Option("--version", help="Show the application version and exit.")
    ] = None,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command("init")
def initialize() -> None:
    """Validate the project scaffold without creating or reading live secrets."""
    try:
        root = _root()
        (root / "facilities").mkdir(exist_ok=True)
        (root / "runs").mkdir(exist_ok=True)
        runtime_registry = load_runtime_registry(root)
        tool_registry = load_tool_registry(root)
        load_dotenv(root / ".env")
        model_configuration = load_effective_model_configuration(root)
        references = ReferenceRegistry(root).all()
        typer.secho("Project scaffold is valid.", fg=typer.colors.GREEN)
        typer.echo(f"Runtime registry: {runtime_registry.status}")
        typer.echo(f"Tool contracts: {tool_registry.version} ({tool_registry.status})")
        typer.echo(f"Model configuration: {model_configuration.status}")
        typer.echo(f"Verified references: {len(references)}")
        typer.echo("No remote API was called. Copy .env.example to .env only when ready.")
    except (SpeakSportError, ValidationError) as exc:
        _fail(exc)


@facility_app.command("create")
def create_facility(
    slug: Annotated[str, typer.Argument(help="Lowercase facility slug.")],
    name: Annotated[str, typer.Option("--name", help="Facility display name.")],
    website: Annotated[str, typer.Option("--website", help="Primary website with scheme.")],
    mode: Annotated[IntegrationType, typer.Option("--mode")],
    timezone: Annotated[str, typer.Option("--timezone")],
    course_configuration: Annotated[
        CourseConfiguration, typer.Option("--course-configuration")
    ] = CourseConfiguration.SINGLE_COURSE,
    course: Annotated[
        list[str] | None,
        typer.Option("--course", help="Exact runtime course value; repeat for multiple courses."),
    ] = None,
    booking_url: Annotated[
        str | None, typer.Option("--booking-url", help="Required for non-integrated facilities.")
    ] = None,
    first_shop_transfer_deflection: Annotated[
        bool,
        typer.Option(
            "--first-shop-transfer-deflection",
            help=(
                "Deflect the caller's first general or Golf/Pro Shop transfer request "
                "before using the normal transfer flow."
            ),
        ),
    ] = False,
    single_player_requires_partially_filled_slot: Annotated[
        bool,
        typer.Option(
            "--single-player-requires-partially-filled-slot",
            help=(
                "For solo callers, present only returned tee times whose "
                "spots_remaining value is below four."
            ),
        ),
    ] = False,
) -> None:
    """Create a validated, human-editable facility intake directory."""
    try:
        root = _root()
        facility_dir = root / "facilities" / slug
        if facility_dir.exists():
            raise SpeakSportError(f"Facility already exists: {slug}")
        tool_registry = load_tool_registry(root)
        active = ReferenceRegistry(root).active_versions()
        core_capabilities = (
            {"eligibility", "availability", "booking", "transfer"}
            if mode == IntegrationType.INTEGRATED
            else {"sms", "transfer"}
        )
        enabled_tools = [
            tool.logical_name
            for tool in tool_registry.tools
            if mode in tool.compatible_modes and tool.capability in core_capabilities
        ]
        config = FacilityConfig(
            slug=slug,
            display_name=name,
            website_url=website,
            timezone=timezone,
            integration_type=mode,
            course_configuration=course_configuration,
            exact_course_values=course or [],
            references=ReferenceSelection(
                prompt=active[mode.value],
                eligibility=active.get(ReferenceMode.ELIGIBILITY.value)
                if mode == IntegrationType.INTEGRATED
                else None,
            ),
            enabled_tools=enabled_tools,
            booking_url=booking_url,
            transfer_policy=TransferPolicy(
                first_shop_transfer_deflection=first_shop_transfer_deflection
            ),
            availability_policy=AvailabilityPolicy(
                single_player_requires_partially_filled_slot=(
                    single_player_requires_partially_filled_slot
                )
            ),
        )
        facility_dir.mkdir(parents=True)
        dump_yaml(facility_dir / "facility.yaml", config.model_dump(mode="json"))
        note_files = {
            "client-notes.md": "# Client notes\n\n",
            "booking-policies.md": "# Booking policies\n\n",
            "transfer-notes.md": "# Transfer notes\n\n",
            "known-exclusions.md": "# Known exclusions\n\n",
        }
        for filename, content in note_files.items():
            (facility_dir / filename).write_text(content, encoding="utf-8")
        typer.secho(f"Created facilities/{slug}/", fg=typer.colors.GREEN)
        typer.echo(
            "Complete policies, destinations, greeting, disclaimer, and announcement before use."
        )
    except (SpeakSportError, ValidationError, KeyError) as exc:
        _fail(exc)


@modify_app.command("create")
def create_modification(
    slug: Annotated[str, typer.Argument(help="Lowercase modification slug.")],
    name: Annotated[str, typer.Option("--name", help="Facility display name.")],
    source_prompt: Annotated[Path, typer.Option("--source-prompt", exists=True, dir_okay=False)],
    website: Annotated[str, typer.Option("--website", help="Facility website metadata.")],
    timezone: Annotated[str, typer.Option("--timezone")],
    course_configuration: Annotated[
        CourseConfiguration, typer.Option("--course-configuration")
    ] = CourseConfiguration.SINGLE_COURSE,
    course: Annotated[
        list[str] | None,
        typer.Option("--course", help="Exact runtime course value; repeat when needed."),
    ] = None,
    knowledge_base_mode: Annotated[
        str,
        typer.Option(
            "--knowledge-base-mode",
            help="Use 'exact' to preserve the original block or 'revise' for requested edits.",
        ),
    ] = "exact",
    first_shop_transfer_deflection: Annotated[
        bool, typer.Option("--first-shop-transfer-deflection")
    ] = False,
    single_player_requires_partially_filled_slot: Annotated[
        bool, typer.Option("--single-player-requires-partially-filled-slot")
    ] = False,
) -> None:
    """Scaffold a separate existing-prompt modification project."""
    try:
        root = _root()
        directory = root / "modifications" / slug
        if directory.exists():
            raise SpeakSportError(f"Prompt modification already exists: {slug}")
        if knowledge_base_mode not in {"exact", "revise"}:
            raise SpeakSportError("--knowledge-base-mode must be exact or revise")
        original = source_prompt.read_text(encoding="utf-8")
        if "<knowledge-base>" not in original or "</knowledge-base>" not in original:
            raise SpeakSportError("Source prompt must contain a knowledge-base block")
        tool_registry = load_tool_registry(root)
        enabled_capabilities = {
            "eligibility",
            "availability",
            "booking",
            "booking_lookup",
            "cancellation_eligibility",
            "cancellation",
            "transfer",
            "day_of_week",
            "inventory_warmup",
            "weather",
        }
        enabled_tools = [
            tool.logical_name
            for tool in tool_registry.tools
            if IntegrationType.INTEGRATED in tool.compatible_modes
            and tool.capability in enabled_capabilities
        ]
        destination_ids = sorted(
            set(
                re.findall(
                    r"destination\s*(?:=|:)\s*['\"]([a-z0-9][a-z0-9_-]*)['\"]",
                    original,
                )
            )
        )
        destinations = [
            TransferDestination(
                identifier=identifier,
                display_name=identifier.replace("_", " ").title(),
                responsibility="Preserved from the original prompt; review and refine before run.",
            )
            for identifier in destination_ids
        ]
        active = ReferenceRegistry(root).active_versions()
        facility = FacilityConfig(
            slug=slug,
            display_name=name,
            website_url=website,
            timezone=timezone,
            integration_type=IntegrationType.INTEGRATED,
            course_configuration=course_configuration,
            exact_course_values=course or [],
            references=ReferenceSelection(
                prompt=active[ReferenceMode.INTEGRATED.value],
                eligibility=active[ReferenceMode.ELIGIBILITY.value],
            ),
            enabled_tools=enabled_tools,
            transfer_policy=TransferPolicy(
                first_shop_transfer_deflection=first_shop_transfer_deflection
            ),
            availability_policy=AvailabilityPolicy(
                single_player_requires_partially_filled_slot=(
                    single_player_requires_partially_filled_slot
                )
            ),
            transfer_destinations=destinations,
        )
        modification = PromptModificationConfig(
            slug=slug,
            display_name=name,
            preservation=ModificationPreservationPolicy(
                knowledge_base=knowledge_base_mode,
            ),
        )
        directory.mkdir(parents=True)
        (directory / "original-prompt.md").write_text(original, encoding="utf-8")
        (directory / "update-notes.md").write_text(
            "# Requested prompt updates\n\n"
            "Describe tool migrations, policy changes, routing changes, knowledge-base "
            "updates, and behavior that must be retained or removed.\n",
            encoding="utf-8",
        )
        dump_yaml(directory / "facility.yaml", facility.model_dump(mode="json"))
        dump_yaml(directory / "modification.yaml", modification.model_dump(mode="json"))
        typer.secho(f"Created modifications/{slug}/", fg=typer.colors.GREEN)
        typer.echo(
            "Review facility.yaml and update-notes.md, then run "
            f"speaksport modify run {slug}. The new-facility pipeline is not invoked."
        )
    except (SpeakSportError, ValidationError, KeyError, UnicodeDecodeError) as exc:
        _fail(exc)


def _modification_paths(
    root: Path, modification: PromptModificationConfig, facility: FacilityConfig
) -> list[Path]:
    directory = root / "modifications" / modification.slug
    paths = [
        directory / "modification.yaml",
        directory / "facility.yaml",
        directory / modification.original_prompt_file,
        directory / modification.update_notes_file,
    ]
    paths.extend(directory / name for name in modification.additional_context_files)
    reference = ReferenceRegistry(root).get(ReferenceMode.INTEGRATED, facility.references.prompt)
    paths.extend(
        [
            root / reference.content_file,
            root / "config" / "global-conventions.yaml",
            root / "config" / "eligibility-conventions.yaml",
            root / "config" / "runtime-variables.yaml",
            root / "config" / "tool-contracts" / "current.yaml",
            root / "config" / "model.yaml",
        ]
    )
    if reference.generation_instructions_file:
        paths.append(root / reference.generation_instructions_file)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise SpeakSportError(
            "Modification input files are missing: " + ", ".join(str(path) for path in missing)
        )
    return paths


@modify_app.command("check")
def check_modification(slug: str) -> None:
    """Validate modification inputs locally without calling a remote provider."""
    try:
        root = _root()
        modification = load_modification(root, slug)
        facility = load_modification_facility(root, slug)
        input_paths = _modification_paths(root, modification, facility)
        original = (root / "modifications" / slug / modification.original_prompt_file).read_text(
            encoding="utf-8"
        )
        knowledge_base = extract_original_knowledge_base(original)
        registry = load_tool_registry(root)
        contracts = {tool.logical_name: tool for tool in registry.tools}
        unknown = sorted(set(facility.enabled_tools) - set(contracts))
        incompatible = sorted(
            name
            for name in facility.enabled_tools
            if name in contracts
            and facility.integration_type not in contracts[name].compatible_modes
        )
        if unknown or incompatible:
            raise SpeakSportError(
                "Invalid modification tools; unknown="
                f"{unknown or 'none'}, incompatible={incompatible or 'none'}"
            )
        typer.secho(f"Modification inputs are valid: {slug}", fg=typer.colors.GREEN)
        typer.echo(f"Original prompt characters: {len(original)}")
        typer.echo(f"Preserved knowledge-base characters: {len(knowledge_base)}")
        typer.echo(f"Enabled tools: {len(facility.enabled_tools)}")
        typer.echo(f"Tracked input files: {len(input_paths)}")
        typer.echo("No Firecrawl or OpenRouter call was made.")
    except (SpeakSportError, ValidationError, UnicodeDecodeError) as exc:
        _fail(exc)


@modify_app.command("run")
def run_modification(slug: str) -> None:
    """Generate and validate an updated prompt without crawling a website."""
    try:
        root = _root()
        load_dotenv(root / ".env")
        modification = load_modification(root, slug)
        facility = load_modification_facility(root, slug)
        if modification.slug != facility.slug:
            raise SpeakSportError("Modification and facility slugs must match")
        directory = root / "modifications" / slug
        input_paths = _modification_paths(root, modification, facility)
        model = load_effective_model_configuration(root)
        tools = load_tool_registry(root)
        run_directory, manifest = create_modification_run(
            root, facility, modification, model, tools.version, input_paths
        )
        typer.echo(f"Created modification run {manifest['run_id']}")
        reference = ReferenceRegistry(root).get(
            ReferenceMode.INTEGRATED, facility.references.prompt
        )
        if not reference.generation_instructions_file:
            raise SpeakSportError("Active integrated reference has no generation instructions")
        original_prompt = (directory / modification.original_prompt_file).read_text(
            encoding="utf-8"
        )
        update_notes = (directory / modification.update_notes_file).read_text(encoding="utf-8")
        additional_context = {
            name: (directory / name).read_text(encoding="utf-8")
            for name in modification.additional_context_files
        }
        client = OpenRouterClient(os.getenv("OPENROUTER_API_KEY", ""), model)
        pipeline = PromptModificationPipeline(
            client, StageCache(root / ".cache" / "modification-stages")
        )
        typer.echo("Sending the original prompt and requested updates to OpenRouter.")
        sections, result, cached = pipeline.generate(
            facility=facility,
            modification=modification,
            original_prompt=original_prompt,
            update_notes=update_notes,
            additional_context=additional_context,
            reference_prompt=(root / reference.content_file).read_text(encoding="utf-8"),
            generation_instructions=(root / reference.generation_instructions_file).read_text(
                encoding="utf-8"
            ),
            runtime_registry=(root / "config" / "runtime-variables.yaml").read_text(
                encoding="utf-8"
            ),
            tool_contracts=(root / "config" / "tool-contracts" / "current.yaml").read_text(
                encoding="utf-8"
            ),
            global_conventions=(root / "config" / "global-conventions.yaml").read_text(
                encoding="utf-8"
            ),
            eligibility_conventions=(root / "config" / "eligibility-conventions.yaml").read_text(
                encoding="utf-8"
            ),
            audit_directory=run_directory / "drafts" / "llm-audit",
        )
        prompt_path = write_modification_outputs(
            run_directory=run_directory,
            facility=facility,
            modification=modification,
            original_prompt=original_prompt,
            sections=sections,
        )
        report = _validator(root).validate(
            prompt_path.read_text(encoding="utf-8"),
            facility,
            allow_phone_numbers_in_exact_knowledge_base=(
                modification.preservation.knowledge_base == "exact"
            ),
        )
        modification_findings = validate_modification_requirements(
            prompt_path.read_text(encoding="utf-8"), modification
        )
        if modification_findings:
            report = report.model_copy(
                update={
                    "findings": [*report.findings, *modification_findings],
                    "valid": report.valid
                    and not any(finding.severity == "error" for finding in modification_findings),
                }
            )
        (run_directory / "validation" / "deterministic-report.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest.update(
            {
                "status": "VALIDATED" if report.valid else "GENERATED",
                "returned_model": result.returned_model,
                "cost_usd": 0 if cached else result.cost_usd,
                "token_usage": {} if cached else result.usage,
                "validation_outcome": "PASS" if report.valid else "FAIL",
                "word_counts": {
                    key: value for key, value in report.metrics.items() if key.endswith("_words")
                },
            }
        )
        save_modification_manifest(run_directory, manifest)
        output = run_directory / "output"
        findings = [
            "# QA report",
            "",
            f"Outcome: {'PASS' if report.valid else 'FAIL'}",
            "",
            *(
                f"- [{finding.severity.upper()}] {finding.code}: {finding.message}"
                for finding in report.findings
            ),
        ]
        (output / "qa-report.md").write_text("\n".join(findings) + "\n", encoding="utf-8")
        (output / "approval-checklist.md").write_text(
            "# Prompt modification approval checklist\n\n"
            "- [ ] Original-versus-updated diff reviewed\n"
            "- [ ] Knowledge-base preservation report reviewed\n"
            "- [ ] Requested customer changes verified\n"
            "- [ ] Tool names, arguments, and response behavior verified\n"
            "- [ ] Booking and cancellation eligibility policies approved\n"
            "- [ ] Transfer behavior and destinations approved\n"
            "- [ ] Updated prompt approved for Vapi\n",
            encoding="utf-8",
        )
        (output / "generation-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        typer.secho(
            f"Modified prompt ({'cache hit' if cached else 'OpenRouter'}): {prompt_path}",
            fg=typer.colors.GREEN if report.valid else typer.colors.RED,
        )
        typer.echo(f"Markdown diff: {output / 'original-vs-updated.diff.md'}")
        typer.echo(f"Side-by-side HTML diff: {output / 'original-vs-updated.html'}")
        if not report.valid:
            raise typer.Exit(1)
    except (SpeakSportError, ValidationError, UnicodeDecodeError) as exc:
        _fail(exc)


def _latest_modification_run(root: Path, slug: str) -> Path:
    directory = root / "modification-runs" / slug
    if directory.is_dir():
        candidates = sorted(
            path
            for path in directory.iterdir()
            if (path / "output" / "original-vs-updated.diff.md").is_file()
        )
        if candidates:
            return candidates[-1]
    raise SpeakSportError(f"No completed prompt modification run exists for {slug}")


@modify_app.command("diff")
def show_modification_diff(
    slug: str,
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
) -> None:
    """Print the original-versus-updated unified diff for a modification run."""
    try:
        root = _root()
        run_directory = (
            root / "modification-runs" / slug / run_id
            if run_id
            else _latest_modification_run(root, slug)
        )
        diff_path = run_directory / "output" / "original-vs-updated.diff.md"
        if not diff_path.is_file():
            raise SpeakSportError(f"Modification diff does not exist: {diff_path}")
        typer.echo(diff_path.read_text(encoding="utf-8"))
    except SpeakSportError as exc:
        _fail(exc)


@facility_app.command("show")
def show_facility(slug: str) -> None:
    """Validate and print a facility configuration."""
    try:
        facility = load_facility(_root(), slug)
        typer.echo(json.dumps(facility.model_dump(mode="json"), indent=2))
    except SpeakSportError as exc:
        _fail(exc)


@references_app.command("list")
def list_references() -> None:
    """List references after verifying their immutable content hashes."""
    try:
        registry = ReferenceRegistry(_root())
        active = registry.active_versions()
        for record in registry.all():
            marker = "*" if active.get(record.mode.value) == record.metadata.version else " "
            typer.echo(
                f"{marker} {record.mode.value:15} {record.metadata.version:12} "
                f"{record.metadata.status.value:10} {record.metadata.content_hash[:12]}"
            )
    except SpeakSportError as exc:
        _fail(exc)


@references_app.command("activate")
def activate_reference(mode: ReferenceMode, version: str) -> None:
    """Activate a verified reference version for future facility creation."""
    try:
        ReferenceRegistry(_root()).activate(mode, version)
        typer.secho(f"Activated {mode.value}/{version}", fg=typer.colors.GREEN)
    except SpeakSportError as exc:
        _fail(exc)


@manifest_app.command("create")
def create_manifest(slug: str) -> None:
    """Create an immutable run directory and foundation manifest."""
    try:
        root = _root()
        facility_path = root / "facilities" / slug / "facility.yaml"
        run_dir, manifest = create_run_manifest(
            root,
            load_facility(root, slug),
            load_tool_registry(root),
            load_effective_model_configuration(root),
            input_paths=[facility_path],
        )
        typer.secho(f"Created run {manifest.run_id}", fg=typer.colors.GREEN)
        typer.echo(run_dir)
    except SpeakSportError as exc:
        _fail(exc)


@app.command("assemble")
def assemble(
    slug: str,
    core_shell: Annotated[Path, typer.Option("--core-shell", exists=True, dir_okay=False)],
    knowledge_base: Annotated[Path, typer.Option("--knowledge-base", exists=True, dir_okay=False)],
    logic_module: Annotated[Path, typer.Option("--logic-module", exists=True, dir_okay=False)],
    closing_core_shell: Annotated[
        list[Path] | None,
        typer.Option(
            "--closing-core-shell", exists=True, dir_okay=False, help="Repeat when needed."
        ),
    ] = None,
) -> None:
    """Deterministically assemble and validate a unified Vapi prompt."""
    try:
        root = _root()
        facility_path = root / "facilities" / slug / "facility.yaml"
        facility = load_facility(root, slug)
        input_paths = [facility_path, core_shell, knowledge_base, logic_module]
        input_paths.extend(closing_core_shell or [])
        run_dir, manifest = create_run_manifest(
            root,
            facility,
            load_tool_registry(root),
            load_effective_model_configuration(root),
            input_paths=input_paths,
        )
        bundle = PromptSectionBundle(
            core_shell=core_shell.read_text(encoding="utf-8"),
            knowledge_base=knowledge_base.read_text(encoding="utf-8"),
            logic_module=logic_module.read_text(encoding="utf-8"),
            closing_core_shells=[
                path.read_text(encoding="utf-8") for path in (closing_core_shell or [])
            ],
        )
        prompt = assemble_prompt(bundle)
        prompt_path = run_dir / "output" / "unified-vapi-prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        report = _validator(root).validate(prompt, facility)
        report_path = run_dir / "validation" / "deterministic-report.json"
        report_path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest.status = "VALIDATED" if report.valid else "ASSEMBLED"
        manifest.word_counts = {
            key: value for key, value in report.metrics.items() if key.endswith("_words")
        }
        manifest.validation_outcome = "PASS" if report.valid else "FAIL"
        manifest.inputs.append(
            InputArtifact(path=str(prompt_path.relative_to(root)), sha256=sha256_file(prompt_path))
        )
        save_manifest(run_dir, manifest)
        typer.secho(
            f"Assembled {prompt_path} ({'PASS' if report.valid else 'FAIL'})",
            fg=typer.colors.GREEN if report.valid else typer.colors.RED,
        )
        typer.echo(f"Validation report: {report_path}")
        if not report.valid:
            raise typer.Exit(1)
    except (SpeakSportError, ValidationError) as exc:
        _fail(exc)


@app.command("validate")
def validate_prompt(
    slug: str, prompt: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]
) -> None:
    """Validate an existing unified prompt without changing it."""
    try:
        root = _root()
        report = _validator(root).validate(
            prompt.read_text(encoding="utf-8"), load_facility(root, slug)
        )
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
        if not report.valid:
            raise typer.Exit(1)
    except SpeakSportError as exc:
        _fail(exc)


def _facility_input_paths(root: Path, facility: FacilityConfig) -> list[Path]:
    facility_directory = root / "facilities" / facility.slug
    paths = [path for path in facility_directory.iterdir() if path.is_file()]
    reference_mode = ReferenceMode(facility.integration_type.value)
    reference = ReferenceRegistry(root).get(reference_mode, facility.references.prompt)
    paths.extend(
        [
            root / reference.content_file,
            root / "config" / "global-conventions.yaml",
            root / "config" / "runtime-variables.yaml",
            root / "config" / "tool-contracts" / "current.yaml",
            root / "config" / "model.yaml",
        ]
    )
    if reference.generation_instructions_file:
        paths.append(root / reference.generation_instructions_file)
    return paths


def _resolve_run(root: Path, slug: str, run_id: str | None, required_child: str) -> Path:
    if run_id:
        candidate = root / "runs" / slug / run_id
        if not (candidate / required_child).exists():
            raise SpeakSportError(f"Run {run_id} does not contain {required_child}")
        return candidate
    facility_runs = root / "runs" / slug
    if facility_runs.is_dir():
        for candidate in sorted(facility_runs.iterdir(), reverse=True):
            if candidate.is_dir() and (candidate / required_child).exists():
                return candidate
    raise SpeakSportError(f"No run for {slug} contains {required_child}")


def _client_documents(root: Path, slug: str) -> dict[str, str]:
    facility_directory = root / "facilities" / slug
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(facility_directory.glob("*.md"))
    }


def _new_run(root: Path, facility: FacilityConfig) -> Path:
    run_directory, manifest = create_run_manifest(
        root,
        facility,
        load_tool_registry(root),
        load_effective_model_configuration(root),
        input_paths=_facility_input_paths(root, facility),
    )
    typer.echo(f"Created run {manifest.run_id}")
    return run_directory


def _crawl_run(root: Path, facility: FacilityConfig, run_directory: Path) -> None:
    load_dotenv(root / ".env")
    state_path = run_directory / "crawl" / "state.json"
    client = FirecrawlClient(os.getenv("FIRECRAWL_API_KEY", ""))
    if not state_path.exists():
        request = CrawlRequest(
            url=str(facility.website_url),
            crawl_entire_domain=facility.crawl_entire_domain,
            allow_subdomains=facility.allow_subdomains,
            include_paths=facility.included_source_paths,
            exclude_paths=facility.excluded_source_paths,
        )
        state = client.start_crawl(request, state_path)
        typer.echo(f"Started Firecrawl job {state.job_id}; website content is sent to Firecrawl.")

    def progress(completed: int, total: int, status: str) -> None:
        typer.echo(f"Crawl {status}: {completed}/{total or '?'} pages")

    state = client.resume_until_complete(
        state_path,
        run_directory / "crawl" / "raw",
        progress=progress,
    )
    manifest = load_manifest(run_directory)
    manifest.status = "CRAWLED"
    manifest.crawl_job_id = state.job_id
    save_manifest(run_directory, manifest)
    typer.secho(
        f"Stored {len(state.page_hashes)} immutable raw pages in {run_directory}",
        fg=typer.colors.GREEN,
    )


def _pipeline(root: Path) -> PromptPipeline:
    load_dotenv(root / ".env")
    llm = OpenRouterClient(
        os.getenv("OPENROUTER_API_KEY", ""), load_effective_model_configuration(root)
    )
    return PromptPipeline(llm, StageCache(root / ".cache" / "stages"))


def _extract_run(
    root: Path, facility: FacilityConfig, run_directory: Path, pipeline: PromptPipeline
):
    pages = normalize_raw_pages(
        run_directory / "crawl" / "raw", run_directory / "crawl" / "normalized"
    )
    if not pages:
        raise SpeakSportError("No non-empty crawled pages are available for extraction")
    typer.echo(
        "Sending normalized website content and facility documents to OpenRouter for extraction."
    )
    facts, result, cached = pipeline.extract_facts(
        facility=facility,
        pages=pages,
        client_documents=_client_documents(root, facility.slug),
        audit_directory=run_directory / "facts" / "llm-audit",
    )
    (run_directory / "facts" / "fact-inventory.json").write_text(
        json.dumps(facts.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = load_manifest(run_directory)
    manifest.status = "EXTRACTED"
    manifest.requested_model = result.requested_model
    manifest.returned_model = result.returned_model
    if not cached:
        for key, value in result.usage.items():
            manifest.token_usage[key] = manifest.token_usage.get(key, 0) + value
        manifest.cost_usd = (manifest.cost_usd or 0) + (result.cost_usd or 0)
    save_manifest(run_directory, manifest)
    typer.echo(f"Extracted {len(facts.facts)} facts ({'cache hit' if cached else 'OpenRouter'}).")
    return facts, result, cached


def _write_review_artifacts(run_directory: Path, report, facts, manifest) -> None:
    output = run_directory / "output"
    source_lines = ["# Source manifest", ""]
    sources = sorted({(fact.source_identifier, fact.source_url_or_file) for fact in facts.facts})
    source_lines.extend(f"- `{identifier}`: {source}" for identifier, source in sources)
    (output / "source-manifest.md").write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    qa_lines = [
        "# QA report",
        "",
        f"Outcome: {'PASS' if report.valid else 'FAIL'}",
        f"Total words: {report.metrics.get('total_words', 0)}",
        "",
        "## Findings",
        "",
    ]
    qa_lines.extend(
        f"- [{finding.severity.upper()}] {finding.code}: {finding.message}"
        for finding in report.findings
    )
    (output / "qa-report.md").write_text("\n".join(qa_lines) + "\n", encoding="utf-8")
    checklist = """# Approval checklist

- [ ] Open factual conflicts reviewed
- [ ] Transfer destinations and behavior approved
- [ ] Booking and eligibility policy approved
- [ ] Cancellation eligibility policy approved when cancellation tools are enabled
- [ ] Runtime variables approved
- [ ] Tool names and arguments approved
- [ ] Caller-detail collection approved
- [ ] Unified prompt approved for Vapi
"""
    (output / "approval-checklist.md").write_text(checklist, encoding="utf-8")
    (output / "generation-manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _generate_run(root: Path, facility: FacilityConfig, run_directory: Path) -> bool:
    pipeline = _pipeline(root)
    facts, extraction_result, _ = _extract_run(root, facility, run_directory, pipeline)
    effective_model = load_effective_model_configuration(root)
    if effective_model.max_cost_usd and extraction_result.cost_usd:
        generation_reserve = effective_model.max_cost_usd * 0.35
        extraction_ceiling = effective_model.max_cost_usd - generation_reserve
        if extraction_result.cost_usd > extraction_ceiling:
            raise BudgetExceededError(
                f"Fact extraction cost ${extraction_result.cost_usd:.4f}; generation was not "
                f"started because ${generation_reserve:.2f} of the "
                f"${effective_model.max_cost_usd:.2f} run budget is reserved for generation. "
                "Reduce crawl scope or increase OPENROUTER_MAX_COST_USD before retrying."
            )
    mode = ReferenceMode(facility.integration_type.value)
    reference = ReferenceRegistry(root).get(mode, facility.references.prompt)
    if not reference.generation_instructions_file:
        raise SpeakSportError(
            f"Reference {mode.value}/{facility.references.prompt} has no instructions"
        )
    typer.echo("Sending approved facts and prompt references to OpenRouter for generation.")
    sections, generation_result, cached = pipeline.generate_sections(
        facility=facility,
        facts=facts,
        reference_prompt=(root / reference.content_file).read_text(encoding="utf-8"),
        generation_instructions=(root / reference.generation_instructions_file).read_text(
            encoding="utf-8"
        ),
        runtime_registry=(root / "config" / "runtime-variables.yaml").read_text(encoding="utf-8"),
        tool_contracts=(root / "config" / "tool-contracts" / "current.yaml").read_text(
            encoding="utf-8"
        ),
        global_conventions=(root / "config" / "global-conventions.yaml").read_text(
            encoding="utf-8"
        ),
        eligibility_conventions=(root / "config" / "eligibility-conventions.yaml").read_text(
            encoding="utf-8"
        ),
        audit_directory=run_directory / "drafts" / "llm-audit",
    )
    prompt_path = write_generation_outputs(run_directory / "output", facility, facts, sections)
    report = _validator(root).validate(prompt_path.read_text(encoding="utf-8"), facility)
    (run_directory / "validation" / "deterministic-report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = load_manifest(run_directory)
    manifest.status = "VALIDATED" if report.valid else "GENERATED"
    manifest.requested_model = effective_model.model_slug
    manifest.fallback_models = effective_model.fallback_models
    manifest.max_cost_usd = effective_model.max_cost_usd
    manifest.timeout_seconds = effective_model.timeout_seconds
    manifest.returned_model = generation_result.returned_model
    if not cached:
        for key, value in generation_result.usage.items():
            manifest.token_usage[key] = manifest.token_usage.get(key, 0) + value
        manifest.cost_usd = (manifest.cost_usd or 0) + (generation_result.cost_usd or 0)
    manifest.word_counts = {
        key: value for key, value in report.metrics.items() if key.endswith("_words")
    }
    manifest.validation_outcome = "PASS" if report.valid else "FAIL"
    save_manifest(run_directory, manifest)
    _write_review_artifacts(run_directory, report, facts, manifest)
    typer.echo(
        f"Generated unified prompt ({'cache hit' if cached else 'OpenRouter'}): {prompt_path}"
    )
    return report.valid


@app.command("crawl")
def crawl(
    slug: str,
    resume: Annotated[bool, typer.Option("--resume", help="Resume a persisted crawl job.")] = False,
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
) -> None:
    """Start or resume a Firecrawl job and preserve immutable raw pages."""
    try:
        root = _root()
        facility = load_facility(root, slug)
        run_directory = (
            _resolve_run(root, slug, run_id, "crawl/state.json")
            if resume
            else _new_run(root, facility)
        )
        _crawl_run(root, facility, run_directory)
    except (SpeakSportError, ValidationError) as exc:
        _fail(exc)


@app.command("extract")
def extract(slug: str, run_id: Annotated[str | None, typer.Option("--run-id")] = None) -> None:
    """Normalize crawled pages and extract a cached fact inventory through OpenRouter."""
    try:
        root = _root()
        run_directory = _resolve_run(root, slug, run_id, "crawl/raw")
        _extract_run(root, load_facility(root, slug), run_directory, _pipeline(root))
    except (SpeakSportError, ValidationError) as exc:
        _fail(exc)


@app.command("generate")
def generate(slug: str, run_id: Annotated[str | None, typer.Option("--run-id")] = None) -> None:
    """Generate, assemble, validate, and package a crawled facility run."""
    try:
        root = _root()
        run_directory = _resolve_run(root, slug, run_id, "crawl/raw")
        if not _generate_run(root, load_facility(root, slug), run_directory):
            raise typer.Exit(1)
    except (SpeakSportError, ValidationError) as exc:
        _fail(exc)


@app.command("diff")
def diff(slug: str, against: Annotated[str | None, typer.Option("--against")] = None) -> None:
    """Show a unified Markdown diff against another or the previous generated run."""
    try:
        root = _root()
        latest = latest_run_directory(root, slug)
        if latest is None:
            raise SpeakSportError(f"No runs exist for {slug}")
        latest_prompt = latest / "output" / "unified-vapi-prompt.md"
        if not latest_prompt.is_file():
            raise SpeakSportError(f"Latest run has no unified prompt: {latest.name}")
        if against:
            previous = root / "runs" / slug / against
        else:
            candidates = [
                path
                for path in sorted((root / "runs" / slug).iterdir(), reverse=True)
                if path != latest and (path / "output" / "unified-vapi-prompt.md").is_file()
            ]
            if not candidates:
                raise SpeakSportError("No earlier generated run is available for comparison")
            previous = candidates[0]
        previous_prompt = previous / "output" / "unified-vapi-prompt.md"
        if not previous_prompt.is_file():
            raise SpeakSportError(f"Run {previous.name} has no unified prompt")
        lines = difflib.unified_diff(
            previous_prompt.read_text(encoding="utf-8").splitlines(),
            latest_prompt.read_text(encoding="utf-8").splitlines(),
            fromfile=previous.name,
            tofile=latest.name,
            lineterm="",
        )
        typer.echo("\n".join(lines))
    except SpeakSportError as exc:
        _fail(exc)


@app.command("package")
def package(slug: str, run_id: Annotated[str | None, typer.Option("--run-id")] = None) -> None:
    """Verify that a generated run contains its required human-review package."""
    try:
        root = _root()
        run_directory = _resolve_run(root, slug, run_id, "output/unified-vapi-prompt.md")
        facility = load_facility(root, slug)
        required = {
            "unified-vapi-prompt.md",
            "transfer-destinations.md",
            "source-manifest.md",
            "open-questions.md",
            "qa-report.md",
            "generation-manifest.json",
            "approval-checklist.md",
        }
        if facility.integration_type == IntegrationType.INTEGRATED:
            required.add("eligibility-backoffice-policy.md")
        if "get-eligibility-for-cancellation" in facility.enabled_tools:
            required.add("cancellation-eligibility-backoffice-policy.md")
        missing = sorted(
            name for name in required if not (run_directory / "output" / name).is_file()
        )
        if missing:
            raise SpeakSportError(f"Output package is incomplete: {', '.join(missing)}")
        typer.secho(
            f"Review package is complete: {run_directory / 'output'}", fg=typer.colors.GREEN
        )
    except SpeakSportError as exc:
        _fail(exc)


@app.command("run")
def run(slug: str) -> None:
    """Crawl, extract, generate, validate, and package a facility."""
    try:
        root = _root()
        facility = load_facility(root, slug)
        run_directory = _new_run(root, facility)
        _crawl_run(root, facility, run_directory)
        if not _generate_run(root, facility, run_directory):
            raise typer.Exit(1)
    except (SpeakSportError, ValidationError) as exc:
        _fail(exc)
