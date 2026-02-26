"""Tests for auth chain and API key validation."""

import os
import pytest
from leanvox._auth import resolve_api_key, ensure_api_key
from leanvox.errors import AuthenticationError


class TestResolveApiKey:
    def test_constructor_param_highest_priority(self, monkeypatch):
        monkeypatch.setenv("LEANVOX_API_KEY", "lv_live_env_key")
        key = resolve_api_key("lv_live_constructor_key")
        assert key == "lv_live_constructor_key"

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("LEANVOX_API_KEY", "lv_live_env_key")
        key = resolve_api_key(None)
        assert key == "lv_live_env_key"

    def test_no_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("LEANVOX_API_KEY", raising=False)
        key = resolve_api_key(None)
        assert key is None

    def test_invalid_prefix_raises(self):
        with pytest.raises(AuthenticationError, match="must start with"):
            resolve_api_key("invalid_key_123")

    def test_empty_string_raises(self):
        with pytest.raises(AuthenticationError, match="cannot be empty"):
            resolve_api_key("")

    def test_test_prefix_accepted(self):
        key = resolve_api_key("lv_test_some_key")
        assert key == "lv_test_some_key"


class TestEnsureApiKey:
    def test_none_raises(self):
        with pytest.raises(AuthenticationError, match="No API key"):
            ensure_api_key(None)

    def test_valid_key_passes(self):
        assert ensure_api_key("lv_live_xxx") == "lv_live_xxx"
