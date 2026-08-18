"""
API Key Routes

Lets a user store, edit, test, and delete their own LLM/TTS provider API keys — the "bring your
own key" (BYOK) feature — and exposes the provider registry (app/core/providers.py) so the
frontend can build its key form without duplicating that data. Keys are encrypted at rest
(see app/services/crypto_service.py) and validated against the registry on create/update.

How to use:
    from app.api import api_keys

    app.include_router(api_keys.router)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.deps import get_current_user, get_session
from app.core.providers import KEY_TYPE_TTS, PROVIDERS
from app.models.api_key import UserApiKey
from app.models.project import Project
from app.models.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyOut,
    ApiKeyTestResult,
    ApiKeyUpdate,
    ProviderModelOut,
    ProviderSpecOut,
)
from app.models.user import User
from app.services.api_key_service import get_key_by_id
from app.services.crypto_service import mask_key, store_api_key
from app.services.project_service import sync_llm_model
from app.services.llm_service import test_api_key
from app.services.tts_service import VoiceRequiredError, synthesize_speech

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# Max length of the error message sent back to the frontend — provider errors from litellm can
# contain entire request dumps, which would be unreadable in the UI callout.
_MAX_ERROR_LENGTH = 300


def _to_out(key: UserApiKey, used_by_projects: int = 0) -> ApiKeyOut:
    return ApiKeyOut(
        id=key.id,
        provider=key.provider,
        key_type=key.key_type,
        label=key.label,
        masked_key=key.masked_key,
        status=key.status,
        added_at=key.added_at,
        api_base=key.api_base,
        model_id=key.model_id,
        arcana_id=key.arcana_id,
        used_by_projects=used_by_projects,
    )


@router.get("/providers", response_model=list[ProviderSpecOut])
def list_providers(_: User = Depends(get_current_user)):
    """List all supported providers and their config, for building the API-key form."""
    # Providers, endpoint defaults, and curated models all come from a single registry
    # (app/core/providers.py), so the frontend and backend can never drift apart.
    return [
        ProviderSpecOut(
            value=spec.value,
            label=spec.label,
            key_placeholder=spec.key_placeholder,
            default_api_base=spec.default_api_base,
            api_base_required=spec.api_base_required,
            key_required=spec.key_required,
            supported_types=list(spec.supported_types),
            models=[ProviderModelOut(value=value, label=label) for value, label in spec.models],
            hint=spec.hint,
            tts_model_fixed=spec.tts_model is not None,
            requires_arcana_id=spec.requires_arcana_id,
        )
        for spec in PROVIDERS
    ]


@router.get("", response_model=list[ApiKeyOut])
def list_keys(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """List the current user's stored API keys, including how many projects use each one."""
    keys = session.exec(
        select(UserApiKey).where(UserApiKey.user_id == current_user.id).order_by(UserApiKey.added_at)
    ).all()
    # How often each key is used in projects (as the LLM or the TTS source), one query per usage
    # type instead of one per row, then merged into a single total per key.
    llm_usage = dict(
        session.exec(
            select(Project.llm_api_key_id, func.count(Project.id))
            .where(Project.user_id == current_user.id, Project.llm_api_key_id.is_not(None))
            .group_by(Project.llm_api_key_id)
        ).all()
    )
    tts_usage = dict(
        session.exec(
            select(Project.tts_api_key_id, func.count(Project.id))
            .where(Project.user_id == current_user.id, Project.tts_api_key_id.is_not(None))
            .group_by(Project.tts_api_key_id)
        ).all()
    )
    usage = {
        key_id: llm_usage.get(key_id, 0) + tts_usage.get(key_id, 0)
        for key_id in set(llm_usage) | set(tts_usage)
    }
    # masked_key comes straight from the DB (computed from the plaintext when the key was
    # created), not recomputed from the ciphertext on every list.
    return [_to_out(k, usage.get(k.id, 0)) for k in keys]


@router.post("", response_model=ApiKeyOut, status_code=201)
def create_key(
    data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Store a new API key for the current user."""
    # A plain insert (previously an upsert per provider): multiple keys for the same provider
    # are explicitly allowed, e.g. an LLM and a TTS key at OpenAI.
    key = UserApiKey(
        user_id=current_user.id,
        provider=data.provider,
        key_type=data.key_type,
        label=(data.label or "").strip() or None,
        encrypted_api_key=store_api_key(data.api_key),
        masked_key=mask_key(data.api_key),
        api_base=data.api_base,
        model_id=data.model_id,
        arcana_id=data.arcana_id,
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return _to_out(key)


@router.put("/{key_id}", response_model=ApiKeyOut)
def update_key(
    key_id: str,
    data: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update a stored API key; re-syncs any projects that use it as their LLM source."""
    key = get_key_by_id(session, current_user.id, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API-Key nicht gefunden.")

    key.provider = data.provider
    key.key_type = data.key_type
    key.label = (data.label or "").strip() or None
    key.api_base = data.api_base
    key.model_id = data.model_id
    key.arcana_id = data.arcana_id
    # An empty key field means "leave unchanged" — the plaintext is never retrievable server-side,
    # so the user shouldn't have to retype it just to rename the key or change its model.
    if data.api_key:
        key.encrypted_api_key = store_api_key(data.api_key)
        key.masked_key = mask_key(data.api_key)
    # Any change to endpoint/model/key resets the entry back to "unverified".
    key.status = "unverified"
    session.add(key)

    # Projects keep a denormalized copy of the litellm model string — a model change on the key
    # must be propagated there too, or the analytics would filter on a model that no longer runs.
    session.flush()
    for project in session.exec(select(Project).where(Project.llm_api_key_id == key.id)).all():
        sync_llm_model(session, project)
        session.add(project)

    session.commit()
    session.refresh(key)
    return _to_out(key)


@router.delete("/{key_id}")
def delete_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete a stored API key; projects using it fall back to "no key configured"."""
    key = get_key_by_id(session, current_user.id, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API-Key nicht gefunden.")

    # Projects using this key as their model source lose that choice — they'll show the "no LLM
    # configured yet" hint in the configurator again, instead of pointing at a dead foreign key.
    referencing_llm = session.exec(select(Project).where(Project.llm_api_key_id == key.id)).all()
    for project in referencing_llm:
        project.llm_api_key_id = None
        project.llm_model = None
        session.add(project)

    # Same for TTS — no denormalized model string to clear there, just the reference.
    referencing_tts = session.exec(select(Project).where(Project.tts_api_key_id == key.id)).all()
    for project in referencing_tts:
        project.tts_api_key_id = None
        session.add(project)

    session.delete(key)
    session.commit()
    return None


@router.post("/{key_id}/test", response_model=ApiKeyTestResult)
def test_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Try the stored key against its provider and record whether it works."""
    # Tests the already-stored key (the frontend doesn't send the plaintext here, see
    # frontend/src/api/apiKeys.ts::test) — not a freshly-submitted one.
    key = get_key_by_id(session, current_user.id, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API-Key nicht gefunden.")

    message: str | None = None
    try:
        # Test TTS keys with a real speech-synthesis call, not a chat call — otherwise "Test"
        # would always incorrectly fail for a correctly configured TTS key.
        if key.key_type == KEY_TYPE_TTS:
            synthesize_speech("Test", None, key)
        else:
            test_api_key(key)
        key.status = "active"
    except VoiceRequiredError:
        # Some providers (Cartesia; also "openai_compatible" via litellm) require a voice for
        # EVERY speech-synthesis call — but the voice only comes from the project and is unknown
        # during a plain key test. That's not a sign of an invalid key, hence "unverified" and
        # not "error".
        key.status = "unverified"
        message = (
            "Dieser Anbieter braucht für die Sprachausgabe eine Stimme, die es beim Key-Test noch "
            "nicht gibt — probiere die Sprachausgabe direkt in einem Projekt aus."
        )
    except Exception as exc:  # noqa: BLE001 — any provider/network failure counts as a test failure here
        key.status = "error"
        message = str(exc)[:_MAX_ERROR_LENGTH] or exc.__class__.__name__

    session.add(key)
    session.commit()
    return ApiKeyTestResult(status=key.status, message=message)
