"""Offline acceptance tests for typed configuration.

Every case here is deterministic and touches no network, no model and no
credential. The point of the module is that an unset or malformed setting is a
loud configuration error, never a silent fallback.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from f1show.config import Mode, ModelProvider

#: A fictional model ID. No real model ID may appear in this repository until it
#: is enumerated with the account and its GA status is confirmed (see F01).
TEST_MODEL_ID = "test-model"

REPLAY: dict[str, Any] = {
    "mode": "replay",
    "replay": {"session_key": 9462},
    "booth": {"model_id": TEST_MODEL_ID, "language": "en"},
}


# --------------------------------------------------------------------------
# Mode
# --------------------------------------------------------------------------


def test_mode_enum_has_exactly_replay_and_live() -> None:
    assert {mode.value for mode in Mode} == {"replay", "live"}


def test_malformed_mode_is_a_validation_error(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "mode": "practice"})
    assert "mode" in str(excinfo.value)
    assert "practice" in str(excinfo.value)


# --------------------------------------------------------------------------
# Source settings: documented defaults, overridable endpoints
# --------------------------------------------------------------------------


def test_source_base_url_defaults_to_the_documented_endpoint(make_settings: Any) -> None:
    settings = make_settings(**REPLAY)
    assert settings.source.base_url == "https://api.openf1.org/v1"


def test_source_base_url_is_overridable(make_settings: Any) -> None:
    settings = make_settings(**{**REPLAY, "source": {"base_url": "http://127.0.0.1:8080/v1"}})
    assert settings.source.base_url == "http://127.0.0.1:8080/v1"


def test_request_timeout_has_a_sane_default_and_is_overridable(make_settings: Any) -> None:
    assert make_settings(**REPLAY).source.timeout_seconds == 10.0
    overridden = make_settings(**{**REPLAY, "source": {"timeout_seconds": 2.5}})
    assert overridden.source.timeout_seconds == 2.5


# --------------------------------------------------------------------------
# Replay settings: explicit positive integer session selector
# --------------------------------------------------------------------------


def test_replay_requires_a_session_selector(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "replay": {}})
    assert "session_key" in str(excinfo.value)


def test_replay_rejects_the_latest_magic_value(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "replay": {"session_key": "latest"}})
    message = str(excinfo.value)
    assert "latest" in message
    assert "positive integer" in message

    # The magic value is case-insensitive in OpenF1's documentation.
    with pytest.raises(ValidationError) as upper:
        make_settings(**{**REPLAY, "replay": {"session_key": "LATEST"}})
    assert "positive integer" in str(upper.value)


@pytest.mark.parametrize("selector", [0, -1, -9462, "0", "-42"])
def test_replay_rejects_zero_and_negative_selectors(make_settings: Any, selector: object) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "replay": {"session_key": selector}})
    assert "positive integer" in str(excinfo.value)


def test_replay_accepts_an_explicit_positive_integer(make_settings: Any) -> None:
    settings = make_settings(**{**REPLAY, "replay": {"session_key": 9462}})
    assert settings.replay.session_key == 9462


def test_live_mode_does_not_require_a_replay_selector(make_settings: Any) -> None:
    settings = make_settings(
        mode="live",
        credentials={"openf1_username": "u", "openf1_password": "p"},
        booth={"model_id": TEST_MODEL_ID, "language": "en"},
    )
    assert settings.replay.session_key is None


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------


def test_live_mode_requires_both_openf1_credentials(make_settings: Any) -> None:
    booth = {"model_id": TEST_MODEL_ID, "language": "en"}
    with pytest.raises(ValidationError) as missing_both:
        make_settings(mode="live", booth=booth)
    message = str(missing_both.value)
    assert "live" in message
    assert "openf1_username" in message and "openf1_password" in message

    with pytest.raises(ValidationError) as missing_password:
        make_settings(
            mode="live",
            credentials={"openf1_username": "u"},
            booth=booth,
        )
    assert "openf1_password" in str(missing_password.value)


def test_live_mode_with_credentials_is_accepted(make_settings: Any) -> None:
    settings = make_settings(
        mode="live",
        credentials={"openf1_username": "u", "openf1_password": "p"},
        booth={"model_id": TEST_MODEL_ID, "language": "en"},
    )
    assert settings.mode is Mode.live


def test_replay_with_the_fake_provider_requires_no_credentials(make_settings: Any) -> None:
    settings = make_settings(**REPLAY)
    assert settings.booth.provider is ModelProvider.fake
    assert settings.credentials.openf1_username is None
    assert settings.credentials.openf1_password is None
    assert settings.credentials.gemini_api_key is None


def test_gemini_provider_requires_an_api_key(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "booth": {"model_id": TEST_MODEL_ID, "language": "en", "provider": "gemini"}})
    message = str(excinfo.value)
    assert "gemini" in message
    assert "gemini_api_key" in message

    settings = make_settings(
        **{
            **REPLAY,
            "booth": {"model_id": TEST_MODEL_ID, "language": "en", "provider": "gemini"},
            "credentials": {"gemini_api_key": "fake-key"},
        }
    )
    assert settings.booth.provider is ModelProvider.gemini


def test_model_provider_defaults_to_fake(make_settings: Any) -> None:
    assert make_settings(**REPLAY).booth.provider is ModelProvider.fake
    assert {provider.value for provider in ModelProvider} == {"fake", "gemini"}


# --------------------------------------------------------------------------
# Booth settings: no defaults for model ID and language
# --------------------------------------------------------------------------


def test_model_id_is_required(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "booth": {"language": "en"}})
    assert "model_id" in str(excinfo.value)


def test_commentary_language_is_required(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "booth": {"model_id": TEST_MODEL_ID}})
    assert "language" in str(excinfo.value)


def test_blank_model_id_is_rejected(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "booth": {"model_id": "   ", "language": "en"}})
    assert "model_id" in str(excinfo.value)


def test_blank_language_is_rejected(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "booth": {"model_id": TEST_MODEL_ID, "language": ""}})
    assert "language" in str(excinfo.value)


# --------------------------------------------------------------------------
# Time bounds must be timezone-aware
# --------------------------------------------------------------------------


def test_naive_since_is_rejected(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "window": {"since": dt.datetime(2024, 3, 2, 15, 0, 0)}})
    message = str(excinfo.value)
    assert "since" in message
    assert "timezone-aware" in message


def test_naive_until_is_rejected(make_settings: Any) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**REPLAY, "window": {"until": dt.datetime(2024, 3, 2, 17, 0, 0)}})
    assert "timezone-aware" in str(excinfo.value)


def test_aware_bounds_are_accepted(make_settings: Any) -> None:
    since = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=dt.timezone.utc)
    until = dt.datetime(2024, 3, 2, 17, 0, 0, tzinfo=dt.timezone.utc)
    settings = make_settings(**{**REPLAY, "window": {"since": since, "until": until}})
    assert settings.window.since == since
    assert settings.window.until == until


def test_time_bounds_are_optional(make_settings: Any) -> None:
    settings = make_settings(**REPLAY)
    assert settings.window.since is None
    assert settings.window.until is None


# --------------------------------------------------------------------------
# Secrets never surface
# --------------------------------------------------------------------------


def test_secrets_are_usable_but_never_exposed(make_settings: Any) -> None:
    secrets = {
        "openf1_username": "openf1-user-secret",
        "openf1_password": "openf1-pass-secret",
        "gemini_api_key": "gemini-key-secret",
    }
    settings = make_settings(
        **{
            **REPLAY,
            "booth": {"model_id": TEST_MODEL_ID, "language": "en", "provider": "gemini"},
            "credentials": secrets,
        }
    )

    surfaces = {
        "repr": repr(settings),
        "str": str(settings),
        "model_dump": str(settings.model_dump()),
        "model_dump_json": settings.model_dump_json(),
    }
    for surface, rendered in surfaces.items():
        for name, value in secrets.items():
            assert value not in rendered, f"{name} leaked through {surface}"

    # The values are still readable through the explicit accessor.
    assert settings.credentials.openf1_password.get_secret_value() == "openf1-pass-secret"
    assert settings.credentials.gemini_api_key.get_secret_value() == "gemini-key-secret"


def test_empty_string_credential_is_treated_as_missing(make_settings: Any) -> None:
    """An exported-but-empty variable must behave exactly like an absent one."""
    gemini_booth = {"model_id": TEST_MODEL_ID, "language": "en", "provider": "gemini"}

    with pytest.raises(ValidationError) as absent:
        make_settings(**{**REPLAY, "booth": gemini_booth})
    assert "gemini_api_key" in str(absent.value)

    with pytest.raises(ValidationError) as empty:
        make_settings(
            **{**REPLAY, "booth": gemini_booth, "credentials": {"gemini_api_key": ""}}
        )
    assert "gemini_api_key" in str(empty.value)

    # The blank value is dropped rather than stored as an empty secret.
    settings = make_settings(**{**REPLAY, "credentials": {"gemini_api_key": ""}})
    assert settings.credentials.gemini_api_key is None


def test_live_mode_rejects_empty_openf1_credentials(make_settings: Any) -> None:
    booth = {"model_id": TEST_MODEL_ID, "language": "en"}
    with pytest.raises(ValidationError) as excinfo:
        make_settings(
            mode="live",
            credentials={"openf1_username": "", "openf1_password": ""},
            booth=booth,
        )
    assert "openf1_username" in str(excinfo.value)


def test_settings_are_forbidden_from_accepting_unknown_keys(make_settings: Any) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{**REPLAY, "unknown_section": {"anything": 1}})
