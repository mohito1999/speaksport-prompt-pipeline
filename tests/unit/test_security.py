from speaksport_pipeline.security import redact_text, scan_text


def test_redacts_configured_secret_without_echoing_it(monkeypatch) -> None:
    secret = "example-secret-value-123456789"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)

    redacted = redact_text(f"request failed for {secret}")
    findings = scan_text(f"request failed for {secret}")

    assert secret not in redacted
    assert "<redacted>" in redacted
    assert findings
    assert all(secret not in finding.excerpt for finding in findings)


def test_blank_env_example_values_are_not_reported_as_secrets() -> None:
    assert not scan_text("FIRECRAWL_API_KEY=\nOPENROUTER_API_KEY=\n")
