"""Tests for ApiKeyCreate's api_base validation (app/features/api_keys/schemas.py) — guards
against using this field for SSRF (server-side request forgery) against cloud-metadata
endpoints, while still allowing the arbitrary self-hosted/LAN addresses that Ollama and
"OpenAI-compatible" keys legitimately need (see app/core/providers.py)."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.features.api_keys.schemas import _BLOCKED_API_BASE_HOSTNAMES, ApiKeyCreate


def _openai_compatible(api_base: str | None) -> ApiKeyCreate:
    return ApiKeyCreate(
        provider="openai_compatible",
        key_type="llm",
        api_key="secret",
        api_base=api_base,
        model_id="some-model",
    )


@pytest.mark.parametrize(
    "api_base",
    [
        "https://api.example.com/v1",
        "http://localhost:11434",
        "http://192.168.1.50:11434",  # a school's own LAN Ollama box — must keep working
        "http://ollama.internal.school.example:11434",
    ],
)
def test_accepts_ordinary_endpoints(api_base: str) -> None:
    assert _openai_compatible(api_base).api_base == api_base


@pytest.mark.parametrize(
    "api_base",
    [
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP/Azure metadata IP
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[fd00:ec2::254]/latest/api/token",  # AWS IMDSv2 IPv6 alias
        "http://[fe80::1]/",  # link-local
        "ftp://example.com",  # non-http(s) scheme
        "not-a-url",
    ],
)
def test_rejects_ssrf_targets(api_base: str) -> None:
    with pytest.raises(ValidationError):
        _openai_compatible(api_base)


def test_none_api_base_passes_through_for_providers_that_dont_need_one() -> None:
    key = ApiKeyCreate(provider="anthropic", key_type="llm", api_key="secret", model_id="claude-sonnet-4-5")
    assert key.api_base is None


COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker" / "docker-compose.yml"
COMPOSE_SERVICES = sorted(yaml.safe_load(COMPOSE_FILE.read_text())["services"])


@pytest.mark.parametrize("service", COMPOSE_SERVICES)
def test_rejects_the_deployments_own_services(service: str) -> None:
    # Reachable by name from the backend container, but never a teacher's LLM/TTS server.
    for api_base in (f"http://{service}:8080/v1", f"http://{service.upper()}./v1"):
        with pytest.raises(ValidationError):
            _openai_compatible(api_base)


def test_every_compose_service_is_blocked() -> None:
    # A service added to docker-compose.yml must be added to the block list too.
    assert set(COMPOSE_SERVICES) <= _BLOCKED_API_BASE_HOSTNAMES
