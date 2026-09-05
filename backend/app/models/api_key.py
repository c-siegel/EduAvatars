"""
Stored API Key Table

One user-provided API key for an LLM/TTS provider — the "bring your own key" feature. See
app/core/providers.py for the provider registry these are validated against.

How to use:
    from app.models.api_key import UserApiKey

    key = session.get(UserApiKey, key_id)
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

from app.core.providers import KEY_TYPE_LLM


class UserApiKey(SQLModel, table=True):
    """One user's API key for a provider, plus how it's configured (endpoint, model, ...)."""

    # Deliberately NO UniqueConstraint(user_id, provider): a user may store several keys for the
    # same provider (e.g. an LLM and a TTS key at OpenAI, or two OpenAI keys with different
    # models). Keys are therefore addressed by their id.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    # Provider / communication protocol, see app/core/providers.py (validated on create).
    provider: str
    # What the key is used for: "llm" | "tts" (see app/core/providers.py).
    key_type: str = KEY_TYPE_LLM
    # The user's own name for it ("school account"), optional — empty means the UI shows the
    # provider's label instead.
    label: str | None = None
    encrypted_api_key: str  # via app.core.security.encrypt_api_key (Fernet)
    masked_key: str  # e.g. "sk-ant-•••••••••••4f2a" — computed from the plaintext on create and
    # stored, NOT recomputed from encrypted_api_key when listing (see Gap #5)
    status: str = "unverified"  # active | unverified | error
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Endpoint address. Pre-filled in the form from ProviderSpec.default_api_base and stays
    # editable; only passed on to litellm if it differs from the default (see
    # services/api_key_service.py::effective_api_base) — otherwise a merely pre-filled value
    # would change the existing SaaS providers' call behavior.
    api_base: str | None = None
    # The chosen model without the litellm prefix (e.g. "gpt-4o", "llama3.1"). Required, except
    # for a TTS key with a provider-fixed speech model (see ProviderSpec.tts_model). If the value
    # itself contains a "/", it's treated as a full litellm model string (free-text entry in the
    # key form).
    model_id: str | None = None
    # Only for providers with ProviderSpec.requires_arcana_id (currently GWDG Arcana) — selects
    # the knowledge base (RAG) to query, see services/llm_service.py::_send_chat_arcana.
    arcana_id: str | None = None
