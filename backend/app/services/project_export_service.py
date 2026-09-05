"""
Project Export/Import

Turns a Project into a portable YAML document, and back — so an educator can back up a
project, move it to another eduavatars account, or share a configuration with a colleague
without also handing over their own API keys.

What is YAML? A human-readable text format for structured data (like JSON, but easier to
hand-edit) — see app/api/projects.py's export/import routes for where this is used.

How to use:
    from app.services.project_export_service import export_project_yaml, import_project

    yaml_text = export_project_yaml(project)
    new_project = import_project(session, current_user.id, parse_project_yaml(yaml_text))
"""

import re

import yaml
from pydantic import ValidationError
from sqlmodel import Session

from app.models.avatar_model import AvatarModel
from app.models.background_image import BackgroundImage
from app.models.project import Project
from app.models.schemas.project_export import ProjectExportData

# Bumped only if a future format change stops being readable by older versions of this parser.
FORMAT_VERSION = 1

_YAML_HEADER = (
    "# eduavatars project export\n"
    "# Re-import this file (Overview page) to recreate this project's configuration.\n"
    "# API keys, the publish state, and the chat password are never included here — set those\n"
    "# up again after importing.\n"
)

_AVATAR_URL_RE = re.compile(r"^/avatars/([^/]+)/file$")
_BACKGROUND_URL_RE = re.compile(r"^/backgrounds/([^/]+)/file$")

# Generous cap for a hand-edited YAML text file — real exports are a few hundred bytes.
MAX_IMPORT_UPLOAD_BYTES = 256 * 1024


class ProjectImportError(ValueError):
    """Raised when an uploaded file isn't a valid eduavatars project export."""


def export_project_yaml(project: Project) -> str:
    """Serialize `project`'s portable configuration (no API keys, publishing state, or IDs) as YAML."""
    data = ProjectExportData.model_validate(project, from_attributes=True)
    payload = {"eduavatars_export": FORMAT_VERSION, "project": data.model_dump()}
    return _YAML_HEADER + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def export_filename(project: Project) -> str:
    """Filesystem-safe .yml filename for `project`, e.g. "my-project.yml"."""
    slug = re.sub(r"[^a-z0-9]+", "-", project.title.strip().lower()).strip("-")
    return f"{slug or 'project'}.yml"


def parse_project_yaml(raw: bytes | str) -> ProjectExportData:
    """Parse and validate an uploaded file as an eduavatars project export.

    Raises ProjectImportError for anything that isn't a well-formed export — not the file's own
    fault vs. a bug distinction; every failure just means "can't import this file".
    """
    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ProjectImportError("not valid YAML") from exc
    if not isinstance(document, dict) or not isinstance(document.get("project"), dict):
        raise ProjectImportError("missing a 'project' section")
    try:
        return ProjectExportData.model_validate(document["project"])
    except ValidationError as exc:
        raise ProjectImportError(str(exc)) from exc


def _owned_avatar_url(session: Session, user_id: str, url: str | None) -> str | None:
    """Keep `url` only if it still points at one of this user's own avatar-library files —
    dropped instead of failing the import, e.g. when importing a colleague's export whose avatar
    isn't in this account's library, so the project just falls back to the default look."""
    match = _AVATAR_URL_RE.match(url) if url else None
    if match is None:
        return None
    avatar = session.get(AvatarModel, match.group(1))
    return url if avatar is not None and avatar.user_id == user_id else None


def _owned_background_url(session: Session, user_id: str, url: str | None) -> str | None:
    """Same as _owned_avatar_url, for the background-image library."""
    match = _BACKGROUND_URL_RE.match(url) if url else None
    if match is None:
        return None
    background = session.get(BackgroundImage, match.group(1))
    return url if background is not None and background.user_id == user_id else None


def import_project(session: Session, user_id: str, data: ProjectExportData) -> Project:
    """Create a new project for `user_id` from a parsed export.

    Always a new project (never overwrites an existing one) and always a draft — API keys are
    never part of an export (see ProjectExportData), so llm_model/publishing would otherwise be
    silently broken/misleading until the educator re-configures them anyway.
    """
    fields = data.model_dump()
    fields["avatar_model_url"] = _owned_avatar_url(session, user_id, fields["avatar_model_url"])
    fields["avatar_background_url"] = _owned_background_url(session, user_id, fields["avatar_background_url"])
    project = Project(user_id=user_id, **fields)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
