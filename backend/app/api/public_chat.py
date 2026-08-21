"""
Public Chat Routes

The unauthenticated endpoints a published project's visitors actually use: load the project's
public info, send a chat message, and transcribe a voice message. There's no login here —
visitors are tracked by an anonymous cookie (visitor_id) instead — and every route is
rate-limited (see app/core/rate_limit.py) since anyone can call them.

How to use:
    from app.api import public_chat

    app.include_router(public_chat.router)
"""

import base64
import logging
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, UploadFile
from sqlmodel import Session, select
import json
from datetime import datetime, timezone

from app.core.deps import get_or_set_visitor_id, get_published_project, get_session
from app.core.error_codes import ErrorCode
from app.core.rate_limit import (
    enforce_chat_unlock_rate_limit,
    enforce_public_chat_rate_limit,
    enforce_public_transcribe_rate_limit,
)
from app.models.conversation import Conversation
from app.models.project import Project
from app.models.schemas.chat import (
    ChatMessageIn,
    ChatMessageOut,
    ChatUnlockOut,
    ChatUnlockRequest,
    PublicProjectOut,
)
from app.models.schemas.speech import TranscriptionOut
from app.models.user import User
from app.services.api_key_service import resolve_llm_key, resolve_tts_key
from app.services.chat_password_service import assert_unlocked, is_unlocked, issue_unlock_token, verify_chat_password
from app.services.llm_service import send_chat_message
from app.services.stt_service import transcribe_audio
from app.services.tts_service import synthesize_speech
from app.services.visitor_service import log_access

router = APIRouter(prefix="/public", tags=["public-chat"])

# Visitors deliberately only get generic error messages (no technical detail) — so the actual
# error is still visible *somewhere* instead of being swallowed entirely, it goes into the
# server log here.
logger = logging.getLogger(__name__)

_MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_AUDIO_CONTENT_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}


def _synthesize_if_enabled(session: Session, project: Project, text: str) -> tuple[str | None, str | None]:
    """Generate speech for `text` if the project has TTS enabled and a usable key; logs failures instead of raising."""
    if not project.tts_enabled:
        return None, None
    api_key = resolve_tts_key(session, project)
    if api_key is None:
        return None, None
    try:
        audio_bytes, content_type = synthesize_speech(text, project.tts_voice, api_key)
    except Exception:
        logger.exception("TTS fehlgeschlagen (project_id=%s)", project.id)
        return None, None
    return base64.b64encode(audio_bytes).decode(), content_type


@router.get("/{slug}", response_model=PublicProjectOut)
def load_tutor(
    request: Request,
    response: Response,
    project: Project = Depends(get_published_project),
    session: Session = Depends(get_session),
    x_chat_unlock_token: str | None = Header(default=None),
):
    """Load a published project's public info (for the public chat page) and record the visit."""
    visitor_id = get_or_set_visitor_id(request, response)
    log_access(session, project.id, visitor_id)

    unlocked = is_unlocked(project, visitor_id, x_chat_unlock_token)
    if project.password_protected and not unlocked:
        # Nothing persona/prompt-related leaks before the password is entered — just enough to
        # show a non-blank lock screen (title, who set it up).
        user = session.get(User, project.user_id)
        return PublicProjectOut(
            title=project.title,
            teacher_name=user.name if user else "",
            password_protected=True,
            unlocked=False,
        )

    user = session.get(User, project.user_id)
    teacher_name = user.name if user else ""

    return PublicProjectOut(
        title=project.title,
        teacher_name=teacher_name,
        start_prompt=project.start_prompt,
        avatar_model_url=project.avatar_model_url,
        avatar_background_url=project.avatar_background_url,
        spoken_language=project.spoken_language,
        tts_enabled=project.tts_enabled,
        stt_enabled=project.stt_enabled,
        chat_default_open=project.chat_default_open,
        # The checkbox and URL are combined here, before anything goes out to the anonymous page —
        # both "not enabled" and "enabled but URL empty" end up as None.
        survey_before_url=project.survey_before_url if project.survey_before_enabled and project.survey_before_url else None,
        survey_after_url=project.survey_after_url if project.survey_after_enabled and project.survey_after_url else None,
        password_protected=project.password_protected,
        unlocked=unlocked,
    )


@router.post("/{slug}/unlock", response_model=ChatUnlockOut)
def unlock(
    data: ChatUnlockRequest,
    request: Request,
    response: Response,
    project: Project = Depends(get_published_project),
):
    """Verify a visitor-entered chat password and issue an unlock token for this project+visitor."""
    visitor_id = get_or_set_visitor_id(request, response)
    enforce_chat_unlock_rate_limit(request, visitor_id)
    if not project.password_protected:
        raise HTTPException(status_code=400, detail=ErrorCode.PROJECT_NOT_PASSWORD_PROTECTED)
    if not verify_chat_password(project, data.password):
        raise HTTPException(status_code=401, detail=ErrorCode.CHAT_PASSWORD_INCORRECT)
    return ChatUnlockOut(unlock_token=issue_unlock_token(project, visitor_id))


@router.post("/{slug}/message", response_model=ChatMessageOut)
def send_message(
    data: ChatMessageIn,
    request: Request,
    response: Response,
    project: Project = Depends(get_published_project),
    session: Session = Depends(get_session),
    x_chat_unlock_token: str | None = Header(default=None),
):
    """Send a visitor's chat message to the project's LLM and return the reply, saving history if enabled."""
    visitor_id = get_or_set_visitor_id(request, response)
    # Checked before the rate limit — an unauthenticated caller shouldn't be able to spend a
    # protected project's chat budget just by guessing at the endpoint.
    assert_unlocked(project, visitor_id, x_chat_unlock_token)
    enforce_public_chat_rate_limit(request, visitor_id)

    # No technical detail (provider/model) is passed to anonymous visitors — that's the project
    # owner's configuration problem, not something visitors are affected by or can fix.
    api_key = resolve_llm_key(session, project)
    if api_key is None:
        raise HTTPException(status_code=503, detail=ErrorCode.CHAT_UNAVAILABLE)
    # Timed for the client-side latency-test log (see pages/PublicChat/index.tsx) — not used by
    # the default UI, just extra fields riding along in the response.
    llm_start = time.perf_counter()
    try:
        history = [{"role": h.role, "content": h.content} for h in data.history]
        reply = send_chat_message(
            project.preprompt or "", data.message, api_key, project.creativity, project.start_prompt, history
        )
    except Exception as exc:
        logger.exception("LLM-Anfrage fehlgeschlagen (project_id=%s)", project.id)
        raise HTTPException(status_code=503, detail=ErrorCode.CHAT_UNAVAILABLE) from exc
    llm_ms = (time.perf_counter() - llm_start) * 1000

    if project.save_conversations:
        existing = session.exec(
            select(Conversation)
            .where(Conversation.project_id == project.id)
            .where(Conversation.visitor_id == visitor_id)
        ).first()

        if existing:
            messages = json.loads(existing.messages_json)
            messages.append({"role": "user", "content": data.message})
            messages.append({"role": "assistant", "content": reply})
            existing.messages_json = json.dumps(messages)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            messages = [
                {"role": "user", "content": data.message},
                {"role": "assistant", "content": reply}
            ]
            conversation = Conversation(
                project_id=project.id,
                visitor_id=visitor_id,
                messages_json=json.dumps(messages)
            )
            session.add(conversation)

        session.commit()

    # None (not ~0ms) when TTS didn't actually run (disabled/no key) — see _synthesize_if_enabled.
    tts_start = time.perf_counter()
    audio_base64, content_type = _synthesize_if_enabled(session, project, reply)
    tts_ms = (time.perf_counter() - tts_start) * 1000 if audio_base64 is not None else None
    return ChatMessageOut(
        reply=reply, audio_base64=audio_base64, content_type=content_type, llm_ms=llm_ms, tts_ms=tts_ms
    )


@router.post("/{slug}/transcribe", response_model=TranscriptionOut)
async def transcribe(
    audio: UploadFile,
    request: Request,
    response: Response,
    project: Project = Depends(get_published_project),
    x_chat_unlock_token: str | None = Header(default=None),
):
    """Transcribe a visitor's voice message for the public chat."""
    visitor_id = get_or_set_visitor_id(request, response)
    assert_unlocked(project, visitor_id, x_chat_unlock_token)
    enforce_public_transcribe_rate_limit(request, visitor_id)

    if not project.stt_enabled:
        raise HTTPException(status_code=503, detail=ErrorCode.VOICE_INPUT_UNAVAILABLE)
    if audio.content_type not in _ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=ErrorCode.UNSUPPORTED_AUDIO_FORMAT)
    content = await audio.read(_MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(content) > _MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.AUDIO_FILE_TOO_LARGE)

    stt_start = time.perf_counter()
    try:
        text = transcribe_audio(content)
    except Exception as exc:
        # Generic message for visitors (no technical detail), consistent with send_message.
        logger.exception("Transkription fehlgeschlagen (project_id=%s)", project.id)
        raise HTTPException(status_code=503, detail=ErrorCode.VOICE_INPUT_UNAVAILABLE) from exc
    stt_ms = (time.perf_counter() - stt_start) * 1000
    return TranscriptionOut(text=text, stt_ms=stt_ms)
