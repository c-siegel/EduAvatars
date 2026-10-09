"""
Knowledge Base Limits

The admin-editable upload limits (SiteSettings.rag_*) and the ceilings they must stay under. The
ceilings belong to whoever runs the containers (RAG_HARD_MAX_* in the knowledge service, see
rag/app/config.py) and are read from its /capabilities; the knowledge service clamps every
request to them again, so even a stale value here can't push it past them.

How to use:
    limits = current_limits(session)            # what a new upload is checked against
    check_against_ceilings(update_data)         # before an admin's change is saved
"""

from dataclasses import dataclass

from sqlmodel import Session

from app.core.error_codes import ErrorCode
from app.core.errors import DomainError
from app.features.knowledge import rag_client
from app.features.site_settings.service import get_or_create_site_settings

# Used while the knowledge service is unreachable — the same defaults as its RAG_HARD_MAX_*.
FALLBACK_CEILINGS = {"max_upload_mb": 100, "max_pages": 2000, "max_chars": 10_000_000}

# Site-settings column → the knowledge service's ceiling it's bounded by (None: backend-only).
_CEILING_FOR_COLUMN = {
    "rag_max_upload_mb": "max_upload_mb",
    "rag_max_pages": "max_pages",
    "rag_max_chars_per_document": "max_chars",
}


class LimitAboveCeiling(DomainError):
    status_code = 400
    detail = ErrorCode.KNOWLEDGE_LIMIT_ABOVE_CEILING


@dataclass(frozen=True)
class KnowledgeLimits:
    max_upload_mb: int
    max_pages: int
    max_chars: int
    max_documents_per_kb: int
    max_kb_per_user: int
    user_quota_mb: int
    upload_rate_per_10min: int

    def for_service(self) -> dict:
        """The part the knowledge service enforces itself (rag/app/schemas.py::DocumentLimits)."""
        return {"max_upload_mb": self.max_upload_mb, "max_pages": self.max_pages, "max_chars": self.max_chars}


def current_limits(session: Session) -> KnowledgeLimits:
    row = get_or_create_site_settings(session)
    return KnowledgeLimits(
        max_upload_mb=row.rag_max_upload_mb,
        max_pages=row.rag_max_pages,
        max_chars=row.rag_max_chars_per_document,
        max_documents_per_kb=row.rag_max_documents_per_kb,
        max_kb_per_user=row.rag_max_kb_per_user,
        user_quota_mb=row.rag_user_quota_mb,
        upload_rate_per_10min=row.rag_upload_rate_per_10min,
    )


def ceilings() -> dict:
    try:
        return dict(rag_client.capabilities()["hard_limits"])
    except (rag_client.RagUnavailable, rag_client.RagRejected, KeyError, TypeError):
        return dict(FALLBACK_CEILINGS)


def check_against_ceilings(update: dict) -> None:
    """Reject a site-settings update that would raise a limit above the operator's ceiling."""
    relevant = {column: value for column, value in update.items() if column in _CEILING_FOR_COLUMN and value}
    if not relevant:
        return
    hard = ceilings()
    for column, value in relevant.items():
        if value > hard[_CEILING_FOR_COLUMN[column]]:
            raise LimitAboveCeiling()
