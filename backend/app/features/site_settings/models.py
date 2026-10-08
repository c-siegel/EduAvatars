"""
Site Settings Table

Instance-wide settings an admin can change from the dashboard without a redeploy: the imprint
("Impressum") details shown on the legal-notice page, whether self-registration is open, how long
student chat data is kept, and the knowledge-base (RAG) upload limits.

What is a singleton row?
This table only ever holds one row, with id fixed to 1 — there's exactly one instance-wide
settings record, not one per user. See features/site_settings/service.py for how it's read/
created/updated; nothing else should query or write this table directly.

How to use:
    from app.features.site_settings.models import SiteSettings

    settings_row = session.get(SiteSettings, 1)
"""

from sqlmodel import Field, SQLModel


class SiteSettings(SQLModel, table=True):
    """Instance-wide settings, stored as a single row with id=1."""

    id: int = Field(default=1, primary_key=True)
    # Imprint fields (§5 DDG). All optional: an instance that hasn't filled them in yet shows the
    # "[noch ändern]" placeholder instead, rather than a blank or broken line.
    contact_email: str | None = None
    contact_phone: str | None = None
    provider_name: str | None = None
    provider_street: str | None = None
    provider_city: str | None = None
    provider_country: str | None = None
    # Mirrors Settings.registration_enabled (core/config.py) as the initial value the first time
    # this row is created — after that, this DB value is authoritative and the env var only
    # matters for a fresh install (see features/site_settings/service.py).
    registration_enabled: bool = True
    # How long saved student conversations and page-view logs are kept, in days. 0 = keep forever
    # (the previous behaviour). Enforced by tasks/retention.py, re-checked
    # periodically for as long as the process runs (see main.py's _retention_loop).
    conversation_retention_days: int = 0

    # Knowledge base (RAG) limits — only relevant when Settings.rag_enabled. Editable by an admin
    # within the knowledge service's hard ceilings (see features/knowledge/limits.py); the
    # defaults below are the ones docs/rag-plan.md §5.5 settled on. Lowering one never touches
    # documents that are already indexed, it only applies to new uploads.
    rag_max_upload_mb: int = 20
    rag_max_pages: int = 500
    rag_max_chars_per_document: int = 2_000_000
    rag_max_documents_per_kb: int = 50
    rag_max_kb_per_user: int = 20
    rag_user_quota_mb: int = 200
    rag_upload_rate_per_10min: int = 30
    # Quality evaluation (Settings.rag_evaluation_enabled): the most test questions one run may
    # answer and score. Each costs the teacher several judge LLM calls per metric.
    rag_eval_max_cases_per_run: int = 50
