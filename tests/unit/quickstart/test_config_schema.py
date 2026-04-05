"""Tests for ConfigField dataclass and canonical QUICKSTART_FIELDS list."""

import pytest

from src.quickstart.config_schema import ConfigField, QUICKSTART_FIELDS


class TestConfigField:
    def test_required_attributes(self) -> None:
        field = ConfigField(
            key="SOME_KEY",
            description="A description",
            example="example-value",
        )
        assert field.key == "SOME_KEY"
        assert field.description == "A description"
        assert field.example == "example-value"
        assert field.default is None
        assert field.secret is False
        assert field.required is True
        assert field.validator is None

    def test_optional_field_with_default(self) -> None:
        field = ConfigField(
            key="LOG_LEVEL",
            description="Log level",
            example="INFO",
            default="INFO",
            required=False,
        )
        assert field.default == "INFO"
        assert field.required is False

    def test_secret_field(self) -> None:
        field = ConfigField(
            key="API_KEY",
            description="Secret key",
            example="sk-...",
            secret=True,
        )
        assert field.secret is True

    def test_validator_attribute(self) -> None:
        def my_validator(v: str) -> str | None:
            return None if v else "Value required"

        field = ConfigField(
            key="X",
            description="x",
            example="x",
            validator=my_validator,
        )
        assert field.validator is my_validator
        assert field.validator("hello") is None
        assert field.validator("") == "Value required"


class TestQuickstartFields:
    def test_is_list(self) -> None:
        assert isinstance(QUICKSTART_FIELDS, list)

    def test_all_config_field_instances(self) -> None:
        for f in QUICKSTART_FIELDS:
            assert isinstance(f, ConfigField)

    def test_required_keys_present(self) -> None:
        keys = {f.key for f in QUICKSTART_FIELDS}
        required_keys = {
            "JIRA_MCP_URL",
            "JIRA_MCP_TOKEN",
            "COPILOT_MCP_URL",
            "COPILOT_MCP_TOKEN",
            "ANTHROPIC_API_KEY",
            "DATABASE_URL",
            "SYNC_INTERVAL_MINUTES",
            "STALE_THRESHOLD_DAYS",
            "JIRA_PROJECT_KEYS",
            "HIGH_CONFIDENCE_THRESHOLD",
            "AUTO_APPLY_ENABLED",
            "LOG_LEVEL",
        }
        assert required_keys.issubset(keys)

    def test_secret_fields(self) -> None:
        secret_keys = {f.key for f in QUICKSTART_FIELDS if f.secret}
        assert "JIRA_MCP_TOKEN" in secret_keys
        assert "COPILOT_MCP_TOKEN" in secret_keys
        assert "ANTHROPIC_API_KEY" in secret_keys

    def test_required_fields(self) -> None:
        required = {f.key for f in QUICKSTART_FIELDS if f.required}
        assert "JIRA_MCP_URL" in required
        assert "JIRA_MCP_TOKEN" in required
        assert "COPILOT_MCP_URL" in required
        assert "COPILOT_MCP_TOKEN" in required
        assert "ANTHROPIC_API_KEY" in required

    def test_optional_fields_have_defaults(self) -> None:
        for f in QUICKSTART_FIELDS:
            if not f.required:
                assert f.default is not None, f"{f.key} is optional but has no default"

    def test_no_duplicate_keys(self) -> None:
        keys = [f.key for f in QUICKSTART_FIELDS]
        assert len(keys) == len(set(keys))
