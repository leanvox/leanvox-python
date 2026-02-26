"""API key resolution chain: constructor > env > config file."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .errors import AuthenticationError

_VALID_PREFIXES = ("lv_live_", "lv_test_")
_ENV_VAR = "LEANVOX_API_KEY"
_CONFIG_PATH = Path.home() / ".lvox" / "config.toml"


def _read_config_file() -> str | None:
    """Read API key from ~/.lvox/config.toml."""
    if not _CONFIG_PATH.exists():
        return None
    try:
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[no-redef]
        with open(_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return data.get("api_key") or data.get("auth", {}).get("api_key")
    except Exception:
        return None


def resolve_api_key(api_key: str | None = None) -> str | None:
    """Resolve API key from constructor param, env, or config file.

    Returns None if no key found (lazy auth — error on first call).
    """
    # 1. Constructor param (highest priority)
    if api_key is not None:
        _validate_prefix(api_key)
        return api_key

    # 2. Environment variable
    env_key = os.environ.get(_ENV_VAR)
    if env_key:
        _validate_prefix(env_key)
        return env_key

    # 3. Config file (lowest priority)
    config_key = _read_config_file()
    if config_key:
        _validate_prefix(config_key)
        return config_key

    return None


def _validate_prefix(key: str) -> None:
    """Validate API key prefix."""
    if not key:
        raise AuthenticationError(
            "API key cannot be empty",
            code="invalid_api_key",
            status_code=401,
        )
    if not key.startswith(_VALID_PREFIXES):
        raise AuthenticationError(
            f"API key must start with {' or '.join(_VALID_PREFIXES)}, got '{key[:10]}...'",
            code="invalid_api_key",
            status_code=401,
        )


def ensure_api_key(key: str | None) -> str:
    """Ensure we have a valid API key, raising if not."""
    if key is None:
        raise AuthenticationError(
            "No API key provided. Pass api_key to the constructor, "
            f"set {_ENV_VAR} env var, or create {_CONFIG_PATH}",
            code="invalid_api_key",
            status_code=401,
        )
    return key
