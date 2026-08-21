"""
Provider Registry for the "Bring Your Own Key" Feature

This module is the single source of truth for which LLM/TTS providers a user can connect
with their own API key, and what each one needs (endpoint, model list, whether a key is
required, ...). The frontend fetches this list via GET /api-keys/providers, so the UI and
the backend's validation never drift apart.

What is a provider registry?
Instead of hardcoding provider-specific logic in several places (a frontend dropdown, backend
validation, a hardcoded test-model list), each provider is described once as a ProviderSpec —
its labels, required fields, curated models, and litellm prefix. Adding a new provider means
adding one ProviderSpec entry here, nowhere else.

How to use:
    from app.core.providers import get_provider, build_model_string

    spec = get_provider("anthropic")
    model_string = build_model_string("anthropic", "claude-sonnet-4-5")
    # -> "anthropic/claude-sonnet-4-5"
"""

from dataclasses import dataclass

from app.core.error_codes import ErrorCode

# What a stored API key is used for. LLM = large language model (chat), TTS = text-to-speech.
# STT runs entirely through the instance-wide Whisper server, see services/stt_service.py)

KEY_TYPE_LLM = "llm"
KEY_TYPE_TTS = "tts"
KEY_TYPES = (KEY_TYPE_LLM, KEY_TYPE_TTS)

KEY_TYPE_LABELS = {KEY_TYPE_LLM: "LLM", KEY_TYPE_TTS: "TTS"}

# Generic provider for anything that mimics the OpenAI API (self-hosted models, Together.ai, Groq, ...).
OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"
OLLAMA_PROVIDER = "ollama"

# Own integrations, independent of litellm (see services/tts_service.py:_synthesize_cartesia) —
# Cartesia has a proprietary API that litellm doesn't support.
CARTESIA_PROVIDER = "cartesia"
# Also independent of litellm (see services/llm_service.py::_send_chat_arcana) — the GWDG
# Academic Cloud knowledge base (RAG) needs an extra request header and an "arcana" field that
# litellm's OpenAI-compatible call path doesn't know about.
GWDG_ARCANA_PROVIDER = "gwdg_arcana"


@dataclass(frozen=True)
class ProviderSpec:
    """Describes one LLM/TTS provider a user can configure with their own API key."""

    value: str
    label: str
    key_placeholder: str
    # Pre-filled in the form but stays editable. None = the user must enter their own endpoint's
    # address themselves.
    default_api_base: str | None
    api_base_required: bool
    key_required: bool
    supported_types: tuple[str, ...]
    # litellm prefix put in front of the stored model ID (e.g. "anthropic/").
    model_prefix: str
    # Curated shortlist, deliberately not exhaustive — the key form also accepts any
    # freely-typed model ID.
    models: tuple[tuple[str, str], ...] = ()
    # Cheap/fast model used only to check whether a key is valid (the "Test" button).
    test_model: str | None = None
    tts_model: str | None = None
    default_voice: str | None = None
    hint: str | None = None
    # Only relevant for GWDG Arcana — requires an Arcana ID (which knowledge base to query) in
    # addition to the model, see services/llm_service.py: _send_chat_arcana.
    requires_arcana_id: bool = False


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        value="anthropic",
        label="Anthropic",
        key_placeholder="sk-ant-api03-…",
        default_api_base="https://api.anthropic.com",
        api_base_required=False,
        key_required=True,
        supported_types=(KEY_TYPE_LLM,),
        model_prefix="anthropic/",
        models=(
            ("claude-sonnet-4-5", "Claude Sonnet 4.5"),
            ("claude-haiku-4-5", "Claude Haiku 4.5"),
            ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
        ),
        test_model="anthropic/claude-3-5-haiku-20241022",
    ),
    ProviderSpec(
        value="openai",
        label="OpenAI",
        key_placeholder="sk-…",
        default_api_base="https://api.openai.com/v1",
        api_base_required=False,
        key_required=True,
        supported_types=(KEY_TYPE_LLM, KEY_TYPE_TTS),
        model_prefix="openai/",
        models=(
            ("gpt-4o", "GPT-4o"),
            ("gpt-4o-mini", "GPT-4o mini"),
        ),
        test_model="openai/gpt-4o-mini",
        tts_model="openai/tts-1",
        default_voice="alloy",
    ),
    ProviderSpec(
        value="gemini",
        label="Google Gemini",
        key_placeholder="AIza…",
        default_api_base="https://generativelanguage.googleapis.com",
        api_base_required=False,
        key_required=True,
        supported_types=(KEY_TYPE_LLM, KEY_TYPE_TTS),
        model_prefix="gemini/",
        models=(
            ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
            ("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ),
        test_model="gemini/gemini-2.5-flash-lite",
        # No default_voice: no verified Gemini voice name on hand — better to leave it unset
        # (fails visibly via litellm instead of silently using a made-up voice).
        tts_model="gemini/gemini-2.5-flash-preview-tts",
    ),
    ProviderSpec(
        value="mistral",
        label="Mistral",
        key_placeholder="…",
        default_api_base="https://api.mistral.ai/v1",
        api_base_required=False,
        key_required=True,
        supported_types=(KEY_TYPE_LLM,),
        model_prefix="mistral/",
        models=(
            ("mistral-small-latest", "Mistral Small"),
            ("mistral-large-latest", "Mistral Large"),
        ),
        test_model="mistral/mistral-small-latest",
    ),
    ProviderSpec(
        value=OLLAMA_PROVIDER,
        label="Ollama (selbst gehostet)",
        key_placeholder="optional, falls dein Server einen Key verlangt",
        # No sensible default endpoint: an Ollama server runs locally or on a school's internal
        # network — only the user knows the address. The suggestion still helps as a starting point.
        default_api_base="http://localhost:11434",
        api_base_required=True,
        key_required=False,
        supported_types=(KEY_TYPE_LLM,),
        # litellm recommends "ollama_chat/" (not "ollama/") for chat models.
        model_prefix="ollama_chat/",
        models=(
            ("llama3.1", "Llama 3.1"),
            ("llama3.2", "Llama 3.2"),
            ("qwen2.5", "Qwen 2.5"),
        ),
        test_model="ollama_chat/llama3.2",
        hint="Ollama läuft meist ohne Zugriffsschutz im (Schul-)Netz — ein API-Key ist nur nötig, "
        "falls dein Server das verlangt.",
    ),
    ProviderSpec(
        value=OPENAI_COMPATIBLE_PROVIDER,
        label="OpenAI-kompatibel (eigener Endpunkt)",
        key_placeholder="…",
        default_api_base=None,
        api_base_required=True,
        key_required=True,
        supported_types=(KEY_TYPE_LLM, KEY_TYPE_TTS),
        # Addressed via litellm's "openai/" prefix + api_base, regardless of which provider
        # actually sits behind it.
        model_prefix="openai/",
        models=(),
        test_model=None,
        hint="Für selbst gehostete oder Drittanbieter-Endpunkte, die die OpenAI-API nachbilden "
        "(z. B. Together.ai, Groq, vLLM). Für TTS: ein Endpunkt, der OpenAIs Sprach-API "
        "(/v1/audio/speech) nachbildet.",
    ),
    ProviderSpec(
        value=CARTESIA_PROVIDER,
        label="Cartesia",
        key_placeholder="…",
        default_api_base="https://api.cartesia.ai",
        api_base_required=False,
        key_required=True,
        supported_types=(KEY_TYPE_TTS,),
        # Unused — Cartesia doesn't go through litellm, see services/tts_service.py.
        model_prefix="",
        # Verified against https://docs.cartesia.ai/api-reference/tts/bytes (see the comment in
        # tts_service.py::_synthesize_cartesia for when) — previously there was no selection here
        # at all, so a mistyped/outdated model name only surfaced live as a "model_not_found"
        # error from Cartesia, not already when the key was created.
        models=(
            ("sonic-3.5", "Sonic 3.5 (Standard)"),
            ("sonic-3", "Sonic 3"),
            ("sonic-preview", "Sonic Preview"),
            ("sonic-latest", "Sonic Latest"),
        ),
        test_model=None,
        hint="Direkte Cartesia-Anbindung (litellm unterstützt Cartesia nicht). Ohne hinterlegte "
        "Stimme (Feld „Stimme“ im Projekt) schlägt die Sprachausgabe fehl — die Stimmen-ID kommt "
        "aus der Cartesia-Dokumentation, dafür gibt es hier keine kuratierte Auswahl.",
    ),
    ProviderSpec(
        value=GWDG_ARCANA_PROVIDER,
        label="GWDG Arcana",
        key_placeholder="…",
        default_api_base="https://chat-ai.academiccloud.de/v1",
        api_base_required=False,
        key_required=True,
        supported_types=(KEY_TYPE_LLM,),
        # Unused — doesn't go through litellm, see services/llm_service.py: _send_chat_arcana.
        model_prefix="",
        models=(),
        test_model=None,
        hint="Direkte Anbindung an die GWDG Academic-Cloud-Wissensbasis (RAG) — litellm kennt weder "
        "den nötigen Anfrage-Header noch das Arcana-Feld, es gibt hier keine kuratierte Modell-Auswahl. "
        "Arcana-ID im Format \"nutzername/Projektname\", siehe "
        "https://docs.hpc.gwdg.de/services/ai-services/arcana/.",
        requires_arcana_id=True,
    ),
)

_BY_VALUE = {spec.value: spec for spec in PROVIDERS}


def get_provider(value: str) -> ProviderSpec | None:
    """Look up a provider by its `value` (e.g. "anthropic"), or None if unknown."""
    return _BY_VALUE.get(value)


def require_provider(value: str) -> ProviderSpec:
    """Like get_provider, but raises ValueError instead of returning None for an unknown value."""
    spec = _BY_VALUE.get(value)
    if spec is None:
        raise ValueError(ErrorCode.UNKNOWN_PROVIDER)
    return spec


def provider_label(value: str) -> str:
    """Human-readable label for a provider value, falling back to the raw value if unknown."""
    spec = _BY_VALUE.get(value)
    return spec.label if spec else value


def build_model_string(provider: str, model_id: str) -> str:
    """Build the litellm model string from a stored provider + model ID.

    If model_id already contains a "/", it was entered as a full litellm string (the free-text
    case) and is returned unchanged.
    """
    if "/" in model_id:
        return model_id
    spec = _BY_VALUE.get(provider)
    return f"{spec.model_prefix}{model_id}" if spec else model_id
