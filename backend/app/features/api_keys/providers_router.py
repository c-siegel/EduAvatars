"""
Provider Registry Route

Exposes the provider registry (app/core/providers.py) so the frontend can build its API-key form
— provider dropdown, endpoint defaults, curated models — without duplicating that data.
"""

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.providers import PROVIDERS
from app.features.api_keys.schemas import ProviderModelOut, ProviderSpecOut
from app.features.users.models import User

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderSpecOut])
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
            stt_model_fixed=spec.stt_model is not None,
            requires_arcana_id=spec.requires_arcana_id,
        )
        for spec in PROVIDERS
    ]
