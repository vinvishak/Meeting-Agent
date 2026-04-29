"""Tests for interactive prompt helpers in src/quickstart/prompts.py."""

from unittest.mock import patch

import pytest

from src.quickstart.config_schema import ConfigField
from src.quickstart.prompts import mask_secret, prompt_field, prompt_secret


class TestMaskSecret:
    def test_masks_long_value(self) -> None:
        assert mask_secret("abcdefgh") == "****efgh"

    def test_masks_exactly_five_chars(self) -> None:
        assert mask_secret("abcde") == "****bcde"

    def test_short_value_returns_stars(self) -> None:
        # ≤ 4 chars → full mask
        assert mask_secret("ab") == "****"
        assert mask_secret("abcd") == "****"

    def test_empty_string(self) -> None:
        assert mask_secret("") == "****"


class TestPromptField:
    def _make_field(self, key: str = "SOME_URL", secret: bool = False) -> ConfigField:
        return ConfigField(key=key, description="A URL", example="http://x")

    def test_returns_user_input(self) -> None:
        field = self._make_field()
        with patch("builtins.input", return_value="http://entered.com"):
            result = prompt_field(field, existing=None)
        assert result == "http://entered.com"

    def test_empty_input_uses_existing(self) -> None:
        field = self._make_field()
        with patch("builtins.input", return_value=""):
            result = prompt_field(field, existing="http://existing.com")
        assert result == "http://existing.com"

    def test_empty_input_uses_default(self) -> None:
        field = ConfigField(
            key="LOG_LEVEL", description="Level", example="INFO", default="INFO", required=False
        )
        with patch("builtins.input", return_value=""):
            result = prompt_field(field, existing=None)
        assert result == "INFO"

    def test_empty_input_no_existing_no_default_returns_empty(self) -> None:
        field = self._make_field()
        with patch("builtins.input", return_value=""):
            result = prompt_field(field, existing=None)
        assert result == ""


class TestPromptSecret:
    def test_uses_getpass(self) -> None:
        field = ConfigField(key="TOKEN", description="Token", example="t", secret=True)
        with patch("src.quickstart.prompts.getpass.getpass", return_value="secret-value") as mock_gp:
            result = prompt_secret(field, existing=None)
        mock_gp.assert_called_once()
        assert result == "secret-value"

    def test_empty_getpass_uses_existing(self) -> None:
        field = ConfigField(key="TOKEN", description="Token", example="t", secret=True)
        with patch("src.quickstart.prompts.getpass.getpass", return_value=""):
            result = prompt_secret(field, existing="existing-token")
        assert result == "existing-token"

    def test_empty_getpass_no_existing_returns_empty(self) -> None:
        field = ConfigField(key="TOKEN", description="Token", example="t", secret=True)
        with patch("src.quickstart.prompts.getpass.getpass", return_value=""):
            result = prompt_secret(field, existing=None)
        assert result == ""
