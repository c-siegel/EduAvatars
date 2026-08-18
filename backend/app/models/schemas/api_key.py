"""
API Key Request/Response Shapes

The request/response shapes for app/api/api_keys.py, plus the shared validation that checks a
submitted key against the provider registry (app/core/providers.py) before it's created or
updated.

How to use:
    from app.models.schemas.api_key import ApiKeyCreate
"""

from datetime import datetime

from pydantic import model_validator

from app.core.providers import KEY_TYPE_LLM, KEY_TYPE_TTS, ProviderSpec, get_provider
from app.core.schema import CamelModel


def _validate_against_registry(
    provider: str, key_type: str, api_base: str | None, model_id: str | None, arcana_id: str | None
) -> ProviderSpec:
    """Shared check used for both creating and editing a key.

    This used to be hardcoded special cases per provider; the requirements (is a key needed? a
    URL? which types?) now come from the registry, and an unknown provider is rejected outright —
    previously `provider` was arbitrary free text.
    """
    spec = get_provider(provider)
    if spec is None:
        raise ValueError(f"Unbekannter Anbieter '{provider}'.")
    if key_type not in spec.supported_types:
        raise ValueError(f"{spec.label} unterstützt den Typ '{key_type}' nicht.")
    if spec.api_base_required and not api_base:
        raise ValueError(f"{spec.label} braucht eine Endpunkt-Adresse (API-Base-URL).")
    # TTS keys for providers with a fixed, provider-side speech model (spec.tts_model, e.g.
    # OpenAI/Gemini) don't need a model choice — tts_service.py always uses spec.tts_model for
    # them, never model_id.
    model_required = not (key_type == KEY_TYPE_TTS and spec.tts_model)
    if model_required and not model_id:
        raise ValueError("Bitte ein Modell auswählen oder eine Modell-ID eintragen.")
    if spec.requires_arcana_id and not arcana_id:
        raise ValueError(f"{spec.label} braucht eine Arcana-ID.")
    return spec


class ApiKeyCreate(CamelModel):
    provider: str
    key_type: str = KEY_TYPE_LLM
    label: str | None = None
    # Empty for providers with key_required == False (e.g. a school-internal Ollama server).
    api_key: str = ""
    api_base: str | None = None
    model_id: str | None = None
    arcana_id: str | None = None

    @model_validator(mode="after")
    def validate_against_registry(self):
        spec = _validate_against_registry(self.provider, self.key_type, self.api_base, self.model_id, self.arcana_id)
        if spec.key_required and not self.api_key:
            raise ValueError(f"Für {spec.label} wird ein API-Key benötigt.")
        return self


class ApiKeyUpdate(CamelModel):
    provider: str
    key_type: str = KEY_TYPE_LLM
    label: str | None = None
    # Empty here means "leave unchanged" — the stored plaintext is never retrievable, so the user
    # shouldn't have to retype it just to rename the key or change its model.
    api_key: str = ""
    api_base: str | None = None
    model_id: str | None = None
    arcana_id: str | None = None

    @model_validator(mode="after")
    def validate_against_registry(self):
        _validate_against_registry(self.provider, self.key_type, self.api_base, self.model_id, self.arcana_id)
        return self


class ApiKeyOut(CamelModel):
    id: str
    provider: str
    key_type: str
    label: str | None = None
    masked_key: str
    status: str
    added_at: datetime
    api_base: str | None = None
    model_id: str | None = None
    arcana_id: str | None = None
    # Number of projects using this key as a model source — lets the frontend warn before
    # deleting a key that's still referenced by projects.
    used_by_projects: int = 0


class ApiKeyTestResult(CamelModel):
    status: str
    # Plaintext error cause (truncated). Previously the exception was swallowed entirely, so the
    # UI could only show "Error" without saying why.
    message: str | None = None


class ProviderModelOut(CamelModel):
    value: str
    label: str


class ProviderSpecOut(CamelModel):
    value: str
    label: str
    key_placeholder: str
    default_api_base: str | None
    api_base_required: bool
    key_required: bool
    supported_types: list[str]
    models: list[ProviderModelOut]
    hint: str | None = None
    # This provider's speech model is fixed (e.g. OpenAI/Gemini) — the frontend hides the model
    # choice for TTS keys in that case, instead of forcing a selection that would be ignored anyway.
    tts_model_fixed: bool = False
    # Extra required "Arcana ID" field in the key form (currently only GWDG Arcana).
    requires_arcana_id: bool = False
