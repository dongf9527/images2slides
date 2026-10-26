"""Tests for auth module token path handling."""

import os

import pytest

from images2slides.auth import TOKEN_PATH_ENV_VAR, default_token_path


class TestDefaultTokenPath:
    """Tests for default_token_path resolution."""

    def test_env_var_overrides_everything(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that IMAGES2SLIDES_TOKEN_PATH takes priority."""
        monkeypatch.setenv(TOKEN_PATH_ENV_VAR, "/custom/dir/token.json")
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg")
        assert default_token_path() == "/custom/dir/token.json"

    def test_xdg_config_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test XDG_CONFIG_HOME is honored on posix systems."""
        monkeypatch.delenv(TOKEN_PATH_ENV_VAR, raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg")
        monkeypatch.setattr(os, "name", "posix")
        assert default_token_path() == "/xdg/images2slides/token.json"

    def test_posix_falls_back_to_home_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ~/.config/images2slides/token.json when no env vars are set."""
        monkeypatch.delenv(TOKEN_PATH_ENV_VAR, raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(os, "name", "posix")
        expected = os.path.join(os.path.expanduser("~/.config"), "images2slides", "token.json")
        assert default_token_path() == expected

    def test_windows_uses_appdata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test %APPDATA%/images2slides/token.json on Windows."""
        monkeypatch.delenv(TOKEN_PATH_ENV_VAR, raising=False)
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setenv("APPDATA", os.path.join("C:", "Users", "t", "AppData", "Roaming"))
        expected = os.path.join(
            os.path.join("C:", "Users", "t", "AppData", "Roaming"),
            "images2slides",
            "token.json",
        )
        assert default_token_path() == expected

    def test_windows_falls_back_to_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test home directory fallback when APPDATA is unset on Windows."""
        monkeypatch.delenv(TOKEN_PATH_ENV_VAR, raising=False)
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.delenv("APPDATA", raising=False)
        expected = os.path.join(os.path.expanduser("~"), "images2slides", "token.json")
        assert default_token_path() == expected
