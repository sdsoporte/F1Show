"""Shared test harness for F1Show.

The suite must run fully offline and must not depend on the developer's shell:
any ``F1SHOW_*`` variable is stripped and the ``.env`` file is disabled so a
stray local configuration cannot change a test outcome.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest


@pytest.fixture
def clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove every ``F1SHOW_*`` variable from the environment."""
    for name in list(os.environ):
        if name.startswith("F1SHOW_"):
            monkeypatch.delenv(name, raising=False)
    yield


@pytest.fixture
def make_settings(clean_settings_env: None) -> Callable[..., Any]:
    """Return a factory that builds ``Settings`` hermetically.

    ``_env_file=None`` disables dotenv loading for the constructed instance, so
    a developer's local ``.env`` can never leak into a test.
    """
    from f1show.config import Settings

    def _make(**overrides: Any) -> Any:
        return Settings(_env_file=None, **overrides)

    return _make
