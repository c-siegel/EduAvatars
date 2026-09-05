"""
Project Export/Import Shape

The portable subset of Project (app/models/project.py) used by the YAML export/import routes
(app/api/projects.py) — everything an educator would want to carry from one project to another,
or share with a colleague. Deliberately narrower than the full Project table: API key
references, the publish state/share link, the chat password hash, and the cached start-prompt
audio path are all either secret, instance-specific, or derived, so none of them round-trip.

How to use:
    from app.models.schemas.project_export import ProjectExportData

    data = ProjectExportData.model_validate(project, from_attributes=True)
"""

from pydantic import BaseModel, Field, field_validator

from app.core.error_codes import ErrorCode
from app.models.schemas.project import MAX_TEMPERATURE, MAX_TOP_P


class ProjectExportData(BaseModel):
    """One project's portable configuration — the same fields ProjectUpdate accepts, minus the
    API key references and chat_password (see project_export_service.py for why)."""

    title: str = Field(min_length=1)
    description: str | None = None
    preprompt: str | None = None
    start_prompt: str | None = None
    avatar_model_url: str | None = None
    avatar_background_url: str | None = None
    grade_level: str | None = None
    temperature: float = 0.5
    top_p: float = 1.0
    save_conversations: bool = False
    survey_before_url: str | None = None
    survey_before_enabled: bool = False
    survey_after_url: str | None = None
    survey_after_enabled: bool = False
    tts_enabled: bool = False
    tts_voice: str | None = None
    spoken_language: str = "de"
    stt_enabled: bool = True
    streaming_enabled: bool = True
    chat_default_open: bool = True
    require_visitor_name: bool = False

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if not 0.0 <= value <= MAX_TEMPERATURE:
            raise ValueError(ErrorCode.TEMPERATURE_OUT_OF_RANGE)
        return value

    @field_validator("top_p")
    @classmethod
    def validate_top_p(cls, value: float) -> float:
        if not 0.0 <= value <= MAX_TOP_P:
            raise ValueError(ErrorCode.TOP_P_OUT_OF_RANGE)
        return value
