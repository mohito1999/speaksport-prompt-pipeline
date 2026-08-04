from typer.testing import CliRunner

from speaksport_pipeline.cli import app

runner = CliRunner()


def test_init_validates_scaffold_without_remote_calls() -> None:
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.output
    assert "Project scaffold is valid" in result.output
    assert "No remote API was called" in result.output


def test_crawl_help_is_visible_without_spending_api_credits() -> None:
    result = runner.invoke(app, ["crawl", "--help"])

    assert result.exit_code == 0
    assert "Start or resume a Firecrawl job" in result.output


def test_modify_commands_are_separate_from_new_facility_run() -> None:
    result = runner.invoke(app, ["modify", "--help"])

    assert result.exit_code == 0
    assert "existing production prompts" in result.output
    assert "create" in result.output
    assert "run" in result.output
    assert "diff" in result.output
