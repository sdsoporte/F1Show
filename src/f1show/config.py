"""Typed configuration for F1Show.

Everything the application can be pointed at lives here and is validated at
construction time. Two rules shape this module:

* **Endpoints have documented defaults and are overridable.** They are safe
  because a wrong endpoint fails loudly on the first request.
* **Model IDs and credentials have no defaults.** An unset model ID is a
  configuration error, never a silent fallback to whatever an SDK happens to offer.
* **The commentary language defaults to Argentine Spanish (es-AR).** This is a
  declared audience choice, overridable by any explicit non-blank language.
* **Local file paths have documented defaults and are overridable.** A path is
  not a secret and a wrong one fails loudly when the file cannot be opened,
  unlike a credential, whose absence would otherwise be a silent downgrade.

No model ID and no credential is written into this module. Tests use obviously
fictional placeholders.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Documented OpenF1 base URL. Historical data is free and unauthenticated;
#: live access is an authenticated tier. See ``docs/EXTERNAL-CONTRACTS.md``.
DEFAULT_OPENF1_BASE_URL = "https://api.openf1.org/v1"

#: A request timeout that fails before an operator loses patience, but tolerates
#: the source's ~3 second update cadence.
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0

#: Documented default database file for the single-writer local store. It lives
#: under ``var/`` and ``.gitignore`` already excludes both ``var/`` and
#: ``*.sqlite3``, so a local database is never committed.
DEFAULT_STORE_PATH = "var/f1show.sqlite3"


class Mode(str, Enum):
    """How the pipeline obtains its data."""

    replay = "replay"
    live = "live"


class ModelProvider(str, Enum):
    """Which commentary model backend is wired in."""

    fake = "fake"
    gemini = "gemini"


class _Section(BaseModel):
    """Common behaviour for the nested configuration sections."""

    model_config = ConfigDict(extra="forbid")


class SourceSettings(_Section):
    """The OpenF1 source: documented defaults, overridable by the operator."""

    base_url: str = DEFAULT_OPENF1_BASE_URL
    timeout_seconds: float = Field(default=DEFAULT_REQUEST_TIMEOUT_SECONDS, gt=0)


class StoreSettings(_Section):
    """The local store: a path is safe to default, so it is not a secret."""

    path: str = DEFAULT_STORE_PATH

    @field_validator("path", mode="after")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                "store.path must not be blank; sqlite3 reads an empty path as a "
                "private temporary database, which would silently discard every write"
            )
        return stripped


class ReplaySettings(_Section):
    """Replay selection.

    The selector must be an explicit positive integer. OpenF1 documents a
    ``latest`` magic value for live use; in a replay it would silently make the
    run non-deterministic, so it is rejected here with a specific message.
    """

    session_key: int | None = None

    @field_validator("session_key", mode="before")
    @classmethod
    def _reject_latest(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() == "latest":
            raise ValueError(
                "replay session selector must be an explicit positive integer; "
                "'latest' is a live-only convenience and would make a replay non-deterministic"
            )
        return value

    @field_validator("session_key", mode="after")
    @classmethod
    def _require_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError(
                f"replay session selector must be a positive integer, got {value}"
            )
        return value


class BoothSettings(_Section):
    """The commentary booth: required model ID and overridable es-AR language."""

    model_id: Annotated[str, Field(min_length=1)]
    language: Annotated[str, Field(min_length=1)] = "es-AR"
    provider: ModelProvider = ModelProvider.fake

    @field_validator("model_id", "language", mode="after")
    @classmethod
    def _reject_blank(cls, value: str, info: ValidationInfo) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{info.field_name} must not be blank")
        return stripped


class CredentialsSettings(_Section):
    """Credentials, stored as secrets so they cannot leak through logging.

    An empty string is treated as *missing*, so an exported-but-empty
    environment variable fails the same way as an absent one.
    """

    openf1_username: SecretStr | None = None
    openf1_password: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    @field_validator(
        "openf1_username", "openf1_password", "gemini_api_key", mode="before"
    )
    @classmethod
    def _empty_string_is_missing(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class TimeWindowSettings(_Section):
    """Optional replay bounds. Every timestamp must be timezone-aware."""

    since: dt.datetime | None = None
    until: dt.datetime | None = None

    @field_validator("since", "until", mode="after")
    @classmethod
    def _require_timezone(
        cls, value: dt.datetime | None, info: ValidationInfo
    ) -> dt.datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError(
                f"{info.field_name} must be timezone-aware; naive datetimes are ambiguous and are rejected"
            )
        return value

    @model_validator(mode="after")
    def _check_ordering(self) -> TimeWindowSettings:
        if (
            self.since is not None
            and self.until is not None
            and self.since > self.until
        ):
            raise ValueError("window.since must not be later than window.until")
        return self


class Settings(BaseSettings):
    """The whole application configuration.

    Environment variables are read with the ``F1SHOW_`` prefix and ``__`` as the
    nested delimiter, e.g. ``F1SHOW_BOOTH__MODEL_ID``.
    """

    model_config = SettingsConfigDict(
        env_prefix="F1SHOW_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="forbid",
    )

    mode: Mode = Mode.replay
    source: SourceSettings = Field(default_factory=SourceSettings)
    store: StoreSettings = Field(default_factory=StoreSettings)
    replay: ReplaySettings = Field(default_factory=ReplaySettings)
    booth: BoothSettings
    credentials: CredentialsSettings = Field(default_factory=CredentialsSettings)
    window: TimeWindowSettings = Field(default_factory=TimeWindowSettings)

    @model_validator(mode="after")
    def _check_dependencies(self) -> Settings:
        if self.mode is Mode.replay and self.replay.session_key is None:
            raise ValueError(
                "replay mode requires replay.session_key to be an explicit positive integer"
            )
        if self.mode is Mode.live and (
            self.credentials.openf1_username is None
            or self.credentials.openf1_password is None
        ):
            raise ValueError(
                "live mode requires OpenF1 credentials: set credentials.openf1_username "
                "and credentials.openf1_password; live access needs an OAuth2 token obtained with them"
            )
        if (
            self.booth.provider is ModelProvider.gemini
            and self.credentials.gemini_api_key is None
        ):
            raise ValueError(
                "the 'gemini' model provider requires credentials.gemini_api_key"
            )
        return self
