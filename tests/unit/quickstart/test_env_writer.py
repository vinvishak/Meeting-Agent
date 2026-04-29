"""Tests for .env file read, write, and merge operations."""

import textwrap
from pathlib import Path

import pytest

from src.quickstart.env_writer import load_env, write_env, merge_env, print_summary
from src.quickstart.config_schema import ConfigField, QUICKSTART_FIELDS


# ---------------------------------------------------------------------------
# load_env tests (T004 — foundational reader)
# ---------------------------------------------------------------------------

class TestLoadEnv:
    def test_parse_simple_env(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        result = load_env(str(env_file))
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        result = load_env(str(tmp_path / ".env.missing"))
        assert result == {}

    def test_skips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nFOO=bar\n  # indented\nBAZ=qux\n")
        result = load_env(str(env_file))
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_value_with_equals_sign(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("URL=http://example.com?a=1&b=2\n")
        result = load_env(str(env_file))
        assert result == {"URL": "http://example.com?a=1&b=2"}

    def test_empty_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("EMPTY=\n")
        result = load_env(str(env_file))
        assert result == {"EMPTY": ""}


# ---------------------------------------------------------------------------
# write_env tests (T009 — write side)
# ---------------------------------------------------------------------------

class TestWriteEnv:
    def test_writes_all_fields(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        values = {"FOO": "1", "BAR": "2"}
        fields = [
            ConfigField(key="FOO", description="Foo", example="1"),
            ConfigField(key="BAR", description="Bar", example="2"),
        ]
        write_env(str(env_file), fields, values)
        content = env_file.read_text()
        assert "FOO=1" in content
        assert "BAR=2" in content

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=old\n")
        fields = [ConfigField(key="FOO", description="Foo", example="x")]
        write_env(str(env_file), fields, {"FOO": "new"})
        assert "FOO=new" in env_file.read_text()

    def test_uses_default_when_value_missing(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        fields = [
            ConfigField(key="LEVEL", description="Log level", example="INFO", default="INFO", required=False)
        ]
        write_env(str(env_file), fields, {})
        assert "LEVEL=INFO" in env_file.read_text()


# ---------------------------------------------------------------------------
# merge_env tests (T009)
# ---------------------------------------------------------------------------

class TestMergeEnv:
    def test_new_values_override_existing(self) -> None:
        existing = {"FOO": "old", "KEEP": "this"}
        new_values = {"FOO": "new"}
        result = merge_env(existing, new_values)
        assert result["FOO"] == "new"
        assert result["KEEP"] == "this"

    def test_unrelated_keys_preserved(self) -> None:
        existing = {"UNRELATED": "value"}
        new_values = {"OTHER": "x"}
        result = merge_env(existing, new_values)
        assert result["UNRELATED"] == "value"
        assert result["OTHER"] == "x"

    def test_empty_existing(self) -> None:
        result = merge_env({}, {"A": "1"})
        assert result == {"A": "1"}


# ---------------------------------------------------------------------------
# print_summary tests (T009)
# ---------------------------------------------------------------------------

class TestPrintSummary:
    def test_secrets_masked(self, capsys: pytest.CaptureFixture) -> None:
        fields = [
            ConfigField(key="URL", description="URL", example="http://x", secret=False),
            ConfigField(key="TOKEN", description="Token", example="t", secret=True),
        ]
        values = {"URL": "http://example.com", "TOKEN": "abcdefgh"}
        print_summary(fields, values)
        captured = capsys.readouterr()
        assert "http://example.com" in captured.out
        assert "abcdefgh" not in captured.out
        assert "****efgh" in captured.out

    def test_all_fields_shown(self, capsys: pytest.CaptureFixture) -> None:
        fields = [
            ConfigField(key="A", description="A desc", example="a"),
            ConfigField(key="B", description="B desc", example="b"),
        ]
        print_summary(fields, {"A": "1", "B": "2"})
        out = capsys.readouterr().out
        assert "A" in out
        assert "B" in out
