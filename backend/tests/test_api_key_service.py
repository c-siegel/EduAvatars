"""Tests for browser_stt_model_for (app/services/api_key_service.py) — the decision of whether a
project's public chat should transcribe voice input in the visitor's own browser. It requires
both the deployment-wide opt-in (Settings.browser_stt_enabled) AND the project's own checkbox
(Project.stt_browser_enabled), so a change to only one of the two must never turn browser
transcription on."""

from app.core.config import settings
from app.models.project import Project
from app.services.api_key_service import browser_stt_model_for


def _make_project(**overrides) -> Project:
    defaults = dict(user_id="user-1", title="Test Project", stt_enabled=True, stt_browser_enabled=True)
    return Project(**{**defaults, **overrides})


def test_none_when_deployment_opt_in_is_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "browser_stt_enabled", False)
    assert browser_stt_model_for(_make_project()) is None


def test_none_when_project_opt_in_is_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    assert browser_stt_model_for(_make_project(stt_browser_enabled=False)) is None


def test_none_when_project_stt_is_disabled_entirely(monkeypatch) -> None:
    # A project's own "voice input" checkbox is off — browser transcription must not apply even
    # if both opt-ins above are otherwise on, since there's no mic button to trigger it at all.
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    assert browser_stt_model_for(_make_project(stt_enabled=False)) is None


def test_picks_german_model_for_german_projects(monkeypatch) -> None:
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    monkeypatch.setattr(settings, "browser_stt_model_de", "some/german-model")
    assert browser_stt_model_for(_make_project(spoken_language="de")) == "some/german-model"


def test_picks_english_model_for_english_projects(monkeypatch) -> None:
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    monkeypatch.setattr(settings, "browser_stt_model_en", "some/english-model")
    assert browser_stt_model_for(_make_project(spoken_language="en")) == "some/english-model"
