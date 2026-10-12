"""
Admin Site Settings Routes

Read and update the instance-wide site settings (imprint details, self-registration toggle,
conversation retention period). Admin only — see public_router.py for the unauthenticated subset.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.config import settings
from app.core.deps import get_current_admin, get_session
from app.features.knowledge.limits import ceilings, check_against_ceilings
from app.features.site_settings.schemas import KnowledgeCeilingsOut, SiteSettingsOut, SiteSettingsUpdate
from app.features.site_settings.service import get_or_create_site_settings, update_site_settings
from app.features.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings", response_model=SiteSettingsOut)
def get_settings(admin: User = Depends(get_current_admin), session: Session = Depends(get_session)):
    """The instance-wide site settings (contact email, self-registration toggle)."""
    return get_or_create_site_settings(session)


@router.put("/settings", response_model=SiteSettingsOut)
def put_settings(
    data: SiteSettingsUpdate,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Update the instance-wide site settings."""
    update = data.model_dump(exclude_unset=True)
    # The limits are NOT NULL; an explicit null means "no change" rather than a broken row.
    update = {k: v for k, v in update.items() if not (k.startswith("rag_") and v is None)}
    check_against_ceilings(update)
    return update_site_settings(session, update)


@router.get("/settings/knowledge-ceilings", response_model=KnowledgeCeilingsOut)
def get_knowledge_ceilings(admin: User = Depends(get_current_admin)):
    """The highest values the knowledge limits may be set to (the operator's RAG_HARD_MAX_*)."""
    return KnowledgeCeilingsOut(enabled=settings.rag_enabled, **ceilings())
