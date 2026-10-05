"""Tests for browser_stt_model_url_for (app/features/api_keys/resolve.py) — the decision of whether a
project's public chat should transcribe voice input on the visitor's own device. On by default,
but the deployment (Settings.browser_stt_enabled) and the project itself
(Project.stt_browser_enabled) can each turn it off on their own."""

from app.core.config import settings
from app.features.api_keys.resolve import browser_stt_model_url_for
from app.features.projects.models import Project


def _make_project(**overrides) -> Project:
    defaults = dict(user_id="user-1", title="Test Project", stt_enabled=True)
    return Project(**{**defaults, **overrides})


def test_on_by_default_for_a_new_project(monkeypatch) -> None:
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    monkeypatch.setattr(settings, "browser_stt_model_url", "/models/some-model/v1/")
    assert browser_stt_model_url_for(_make_project()) == "/models/some-model/v1/"


def test_none_when_deployment_turned_it_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "browser_stt_enabled", False)
    assert browser_stt_model_url_for(_make_project()) is None


def test_none_when_project_opted_out(monkeypatch) -> None:
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    assert browser_stt_model_url_for(_make_project(stt_browser_enabled=False)) is None


def test_none_when_project_stt_is_disabled_entirely(monkeypatch) -> None:
    # A project's own "voice input" checkbox is off — there's no mic button to transcribe for.
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    assert browser_stt_model_url_for(_make_project(stt_enabled=False)) is None


def test_same_model_regardless_of_spoken_language(monkeypatch) -> None:
    # Parakeet Redux is multilingual, unlike the old per-language Whisper models.
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    de = browser_stt_model_url_for(_make_project(spoken_language="de"))
    en = browser_stt_model_url_for(_make_project(spoken_language="en"))
    assert de == en == settings.browser_stt_model_url
