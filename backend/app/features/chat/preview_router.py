"""
Preview Chat Routes

The configurator's live preview chat and its voice-message transcription — the same chat
pipeline as the public chat (pipeline.py), but in the project owner's own context: errors carry
the concrete (key-scrubbed) provider message to help debugging, and nothing is saved.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import Session

from app.core.deps import get_owned_project, get_session
from app.core.error_codes import ErrorCode
from app.features.ai.stt import transcribe_audio
from app.features.api_keys.resolve import resolve_stt_key
from app.features.chat.audio_upload import read_audio_upload
from app.features.chat.pipeline import ChatTurn, LLMFailed, prepare_chat, reply_turn
from app.models.project import Project
from app.models.schemas.project import PreviewMessageRequest, PreviewMessageResponse
from app.models.schemas.speech import TranscriptionOut
from app.services.crypto_service import scrub_key_from_text

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/preview-message", response_model=PreviewMessageResponse)
def preview_message(
    data: PreviewMessageRequest,
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Send a message to the project's configured LLM and return the reply, for the in-app preview chat."""
    # Live preview chat in the configurator (Screen 1e) — uses the user's own API key.
    context = prepare_chat(session, project)
    if context is None:
        raise HTTPException(status_code=400, detail=ErrorCode.NO_LLM_MODEL_SELECTED)
    history = [{"role": h.role, "content": h.content} for h in data.history]
    try:
        reply = reply_turn(context, ChatTurn(data.message, history), save=False)
    except LLMFailed as exc:
        # This is the user's own context (the configurator) — the concrete error message helps
        # with debugging (wrong/expired key, wrong model, ...), unlike in the public chat. `code`
        # gets translated on the frontend (see errorMessage() in api/client.ts); `message` is the
        # raw provider exception, appended untranslated since it's already technical/English.
        # Scrubbed in case the provider embeds the key itself in the failing request (e.g. Gemini
        # puts it in the URL) — see services/crypto_service.py::scrub_key_from_text.
        raise HTTPException(
            status_code=502,
            detail={
                "code": ErrorCode.LLM_REQUEST_FAILED,
                "message": scrub_key_from_text(str(exc.__cause__), context.llm_key.encrypted_api_key),
            },
        ) from exc
    return PreviewMessageResponse(reply=reply.text, audio_base64=reply.audio_base64, content_type=reply.content_type)


@router.post("/{project_id}/transcribe", response_model=TranscriptionOut)
def transcribe(
    audio: UploadFile,
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Transcribe a voice message for the in-app preview chat.

    Plain `def`, not `async def` — see the matching public_router.py::transcribe for why: this
    runs the same synchronous, CPU-bound transcription and must not block the event loop.
    """
    if not project.stt_enabled:
        raise HTTPException(status_code=400, detail=ErrorCode.VOICE_INPUT_DISABLED)
    content = read_audio_upload(audio)

    stt_key = resolve_stt_key(session, project)
    try:
        text = transcribe_audio(content, project.spoken_language, api_key_record=stt_key)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail={"code": ErrorCode.STT_REQUEST_FAILED, "message": str(exc)}
        ) from exc
    return TranscriptionOut(text=text)
