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
import json
import logging
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import get_or_set_visitor_id, get_published_project, get_session
from app.core.error_codes import ErrorCode
from app.core.rate_limit import (
    enforce_chat_unlock_rate_limit,
    enforce_public_chat_rate_limit,
    enforce_public_transcribe_rate_limit,
)
from app.db.session import engine
from app.models.api_key import UserApiKey
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
from app.services.api_key_service import resolve_llm_key, resolve_stt_key, resolve_tts_key
from app.services.chat_password_service import assert_unlocked, is_unlocked, issue_unlock_token, verify_chat_password
from app.services.llm_service import _strip_arcana_references, send_chat_message, stream_chat_message
from app.services.stt_service import transcribe_audio
from app.services.text_chunk_service import SentenceChunker
from app.services.tts_service import synthesize_speech
from app.services.visitor_name_service import assert_visitor_name_provided, clean_visitor_name
from app.services.visitor_service import log_access

router = APIRouter(prefix="/public", tags=["public-chat"])

# Visitors deliberately only get generic error messages (no technical detail) — so the actual
# error is still visible *somewhere* instead of being swallowed entirely, it goes into the
# server log here.
logger = logging.getLogger(__name__)

_MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_AUDIO_CONTENT_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}
# faster-whisper's initial_prompt only needs to carry recent context across a pause-segmented
# recording (see stt_service.py) — capped to the trailing text, both because that's what actually
# helps decoding and to bound how much a client can make one transcription request process.
_MAX_INITIAL_PROMPT_CHARS = 500

# Shared across every /message/stream request instead of one ThreadPoolExecutor(max_workers=1)
# per request: chunk *yield* order is already enforced per-request by the `futures` deque in
# event_stream() below (it only pops a chunk once the one before it is done), so which worker
# thread actually runs a given chunk's synthesis doesn't affect ordering — sharing one bounded
# pool just replaces "one thread per concurrent streaming reply, unbounded" with a fixed ceiling.
_tts_executor = ThreadPoolExecutor(max_workers=settings.tts_stream_worker_pool_size)


def _save_conversation_turn(
    session: Session,
    project_id: str,
    visitor_id: str,
    user_message: str,
    reply: str,
    user_timestamp: datetime,
    reply_timestamp: datetime,
    visitor_name: str | None = None,
) -> None:
    """Append one exchange to the visitor's saved conversation for this project, creating it on
    the first message. Commits on `session` — the caller decides which session (request-scoped
    or a fresh one) that is, see send_message_stream for why that matters there.

    user_timestamp/reply_timestamp are passed in (rather than read with datetime.now() here)
    because this runs after both the LLM call and any TTS synthesis — by then "now" would no
    longer be when the visitor actually sent the message or when the reply was actually ready,
    which matters for the per-message timestamps in the analytics CSV export.
    """
    existing = session.exec(
        select(Conversation).where(Conversation.project_id == project_id).where(Conversation.visitor_id == visitor_id)
    ).first()

    user_entry = {"role": "user", "content": user_message, "timestamp": user_timestamp.isoformat()}
    assistant_entry = {"role": "assistant", "content": reply, "timestamp": reply_timestamp.isoformat()}

    if existing:
        messages = json.loads(existing.messages_json)
        messages.append(user_entry)
        messages.append(assistant_entry)
        existing.messages_json = json.dumps(messages)
        existing.updated_at = datetime.now(timezone.utc)
        # Only overwrites if a name actually arrived on this turn — an already-stored name must
        # survive a stray request that (for whatever reason) didn't carry the header.
        if visitor_name:
            existing.visitor_name = visitor_name
    else:
        messages = [user_entry, assistant_entry]
        conversation = Conversation(
            project_id=project_id, visitor_id=visitor_id, messages_json=json.dumps(messages), visitor_name=visitor_name
        )
        session.add(conversation)

    session.commit()


def _synthesize_if_enabled(
    api_key: UserApiKey | None, tts_voice: str | None, project_id: str, text: str, spoken_language: str
) -> tuple[str | None, str | None]:
    """Generate speech for `text` if a TTS key was resolved for the project; logs failures instead of raising.

    Takes the already-resolved key (not `session`/`project`) so the caller can resolve it up
    front and close its DB session before this runs — see send_message, which must not hold a
    pooled connection open for the whole TTS call.
    """
    if api_key is None:
        return None, None
    try:
        audio_bytes, content_type = synthesize_speech(text, tts_voice, api_key, spoken_language)
    except Exception:
        logger.exception("TTS fehlgeschlagen (project_id=%s)", project_id)
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
            require_visitor_name=project.require_visitor_name,
        )

    user = session.get(User, project.user_id)
    teacher_name = user.name if user else ""

    return PublicProjectOut(
        title=project.title,
        teacher_name=teacher_name,
        start_prompt=project.start_prompt,
        start_audio_url=project.start_audio_url,
        avatar_model_url=project.avatar_model_url,
        avatar_background_url=project.avatar_background_url,
        spoken_language=project.spoken_language,
        tts_enabled=project.tts_enabled,
        stt_enabled=project.stt_enabled,
        streaming_enabled=project.streaming_enabled,
        chat_default_open=project.chat_default_open,
        # The checkbox and URL are combined here, before anything goes out to the anonymous page —
        # both "not enabled" and "enabled but URL empty" end up as None.
        survey_before_url=project.survey_before_url if project.survey_before_enabled and project.survey_before_url else None,
        survey_after_url=project.survey_after_url if project.survey_after_enabled and project.survey_after_url else None,
        password_protected=project.password_protected,
        unlocked=unlocked,
        require_visitor_name=project.require_visitor_name,
        save_conversations=project.save_conversations,
        llm_model=project.llm_model,
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
    x_visitor_name: str | None = Header(default=None),
):
    """Send a visitor's chat message to the project's LLM and return the reply, saving history if enabled."""
    # Captured before any LLM/TTS work — the closest we get to "when the visitor actually sent
    # this", used for the per-message timestamp in _save_conversation_turn.
    message_received_at = datetime.now(timezone.utc)
    visitor_id = get_or_set_visitor_id(request, response)
    # Checked before the rate limit — an unauthenticated caller shouldn't be able to spend a
    # protected project's chat budget just by guessing at the endpoint.
    assert_unlocked(project, visitor_id, x_chat_unlock_token)
    visitor_name = clean_visitor_name(x_visitor_name)
    assert_visitor_name_provided(project, visitor_name)
    enforce_public_chat_rate_limit(request, visitor_id)

    # No technical detail (provider/model) is passed to anonymous visitors — that's the project
    # owner's configuration problem, not something visitors are affected by or can fix.
    api_key = resolve_llm_key(session, project)
    if api_key is None:
        raise HTTPException(status_code=503, detail=ErrorCode.CHAT_UNAVAILABLE)
    tts_api_key = resolve_tts_key(session, project) if project.tts_enabled else None

    # Everything the rest of this function needs is read into locals, and the key records are
    # expunged (same reason as send_message_stream), BEFORE the session closes: the LLM and TTS
    # calls below take seconds, and holding a pooled DB connection for that whole time is what
    # let a class-sized burst of concurrent chats exhaust the connection pool.
    session.expunge(api_key)
    if tts_api_key is not None:
        session.expunge(tts_api_key)
    preprompt = project.preprompt or ""
    temperature = project.temperature
    top_p = project.top_p
    start_prompt = project.start_prompt
    tts_voice = project.tts_voice
    spoken_language = project.spoken_language
    project_id = project.id
    save_conversations = project.save_conversations
    history = [{"role": h.role, "content": h.content} for h in data.history]
    session.close()

    # Timed for the client-side latency-test log (see pages/PublicChat/index.tsx) — not used by
    # the default UI, just extra fields riding along in the response.
    llm_start = time.perf_counter()
    try:
        reply = send_chat_message(preprompt, data.message, api_key, temperature, top_p, start_prompt, history)
    except Exception as exc:
        logger.exception("LLM-Anfrage fehlgeschlagen (project_id=%s)", project_id)
        raise HTTPException(status_code=503, detail=ErrorCode.CHAT_UNAVAILABLE) from exc
    llm_ms = (time.perf_counter() - llm_start) * 1000
    reply_ready_at = datetime.now(timezone.utc)

    if save_conversations:
        with Session(engine) as fresh_session:
            _save_conversation_turn(
                fresh_session,
                project_id,
                visitor_id,
                data.message,
                reply,
                message_received_at,
                reply_ready_at,
                visitor_name,
            )

    # None (not ~0ms) when TTS didn't actually run (disabled/no key) — see _synthesize_if_enabled.
    tts_start = time.perf_counter()
    audio_base64, content_type = _synthesize_if_enabled(tts_api_key, tts_voice, project_id, reply, spoken_language)
    tts_ms = (time.perf_counter() - tts_start) * 1000 if audio_base64 is not None else None
    return ChatMessageOut(
        reply=reply, audio_base64=audio_base64, content_type=content_type, llm_ms=llm_ms, tts_ms=tts_ms
    )


def _sse_event(event: str, data: dict) -> str:
    """Format one server-sent-event (SSE) frame — an "event: <name>\\ndata: <json>\\n\\n" block."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{slug}/message/stream")
def send_message_stream(
    data: ChatMessageIn,
    request: Request,
    response: Response,
    project: Project = Depends(get_published_project),
    session: Session = Depends(get_session),
    x_chat_unlock_token: str | None = Header(default=None),
    x_visitor_name: str | None = Header(default=None),
):
    """Streamed variant of send_message: the LLM reply is split into sentence-sized chunks (see
    services/text_chunk_service.py), each synthesized and sent to the client as soon as it's
    ready — so the avatar can start speaking well before the full reply exists. Falls back to
    the plain /message endpoint on the frontend if this fails; see pages/PublicChat/index.tsx.
    """
    # Same reasoning as send_message: captured before any LLM/TTS work, for the saved message's
    # per-message timestamp.
    message_received_at = datetime.now(timezone.utc)
    visitor_id = get_or_set_visitor_id(request, response)
    assert_unlocked(project, visitor_id, x_chat_unlock_token)
    visitor_name = clean_visitor_name(x_visitor_name)
    assert_visitor_name_provided(project, visitor_name)
    enforce_public_chat_rate_limit(request, visitor_id)

    api_key = resolve_llm_key(session, project)
    if api_key is None:
        raise HTTPException(status_code=503, detail=ErrorCode.CHAT_UNAVAILABLE)
    tts_api_key = resolve_tts_key(session, project) if project.tts_enabled else None
    # Detaches the key records from `session` so their already-loaded columns (read later, from
    # the generator and the background TTS thread) can never be invalidated by a future
    # session.commit() expiring them — belt and braces alongside reading project's fields into
    # plain locals below, since nothing here should depend on `session` staying alive or unchanged.
    session.expunge(api_key)
    if tts_api_key is not None:
        session.expunge(tts_api_key)

    # Everything the generator needs is read up front, and it opens its own session for the final
    # write — the request-scoped `session` above must not be touched once we return the streaming
    # response, since its teardown relative to a streamed body is fragile.
    preprompt = project.preprompt or ""
    temperature = project.temperature
    top_p = project.top_p
    start_prompt = project.start_prompt
    tts_voice = project.tts_voice
    spoken_language = project.spoken_language
    project_id = project.id
    save_conversations = project.save_conversations
    history = [{"role": h.role, "content": h.content} for h in data.history]
    user_message = data.message

    def synthesize_chunk(text: str) -> tuple[str | None, str | None, float]:
        """Runs in the background TTS worker thread; never raises. Returns (audioBase64, contentType, ms)."""
        if tts_api_key is None:
            return None, None, 0.0
        synth_start = time.perf_counter()
        try:
            audio_bytes, content_type = synthesize_speech(text, tts_voice, tts_api_key, spoken_language)
        except Exception:
            logger.exception("TTS fehlgeschlagen (project_id=%s)", project_id)
            return None, None, (time.perf_counter() - synth_start) * 1000
        return base64.b64encode(audio_bytes).decode(), content_type, (time.perf_counter() - synth_start) * 1000

    def event_stream():
        start_time = time.perf_counter()
        first_chunk_ms: float | None = None
        # Time until the first chunk is handed to TTS, distinct from first_chunk_ms (time until
        # that chunk's synthesis *finishes*) — isolates LLM/chunking speed from TTS speed. Captured
        # in submit() itself since that's the one place both the per-delta loop and the
        # chunker.flush() tail path funnel through.
        first_chunk_ready_ms: float | None = None
        total_tts_ms: float | None = 0.0 if tts_api_key is not None else None
        full_text_parts: list[str] = []
        chunker = SentenceChunker()
        # Chunks are submitted to the shared _tts_executor (module-level, see its definition
        # above) in order, but output order is enforced independently by pop_ready() only ever
        # popping the deque's front once it's done — so it doesn't matter whether the shared
        # pool's worker threads finish chunk N+1 before chunk N, synthesis for chunk N still
        # overlaps with the LLM producing chunk N+1 rather than a fully sequential "wait for
        # TTS, then ask for more".
        futures: deque[tuple[int, "Future[tuple[str | None, str | None, float]]", str]] = deque()
        next_index = 0

        def submit(text: str) -> None:
            nonlocal next_index, first_chunk_ready_ms
            if first_chunk_ready_ms is None:
                first_chunk_ready_ms = (time.perf_counter() - start_time) * 1000
            futures.append((next_index, _tts_executor.submit(synthesize_chunk, text), text))
            next_index += 1

        def pop_ready():
            nonlocal first_chunk_ms, total_tts_ms
            while futures and futures[0][1].done():
                idx, future, text = futures.popleft()
                audio_b64, content_type, synth_ms = future.result()
                if total_tts_ms is not None:
                    total_tts_ms += synth_ms
                if first_chunk_ms is None:
                    first_chunk_ms = (time.perf_counter() - start_time) * 1000
                yield _sse_event(
                    "chunk", {"index": idx, "text": text, "audioBase64": audio_b64, "contentType": content_type}
                )

        llm_error: Exception | None = None
        try:
            for delta in stream_chat_message(
                preprompt, user_message, api_key, temperature, top_p, start_prompt, history
            ):
                full_text_parts.append(delta)
                for chunk in chunker.feed(delta):
                    submit(chunk)
                yield from pop_ready()
        except Exception as exc:  # LLM failure mid-stream — no retry, whatever was already sent stays.
            llm_error = exc
        llm_ms = (time.perf_counter() - start_time) * 1000
        reply_ready_at = datetime.now(timezone.utc)

        if llm_error is None:
            tail = chunker.flush()
            if tail:
                submit(tail)

        # Drain whatever's left, waiting for each in turn — most of this already finished while
        # later LLM tokens were still streaming in.
        while futures:
            idx, future, text = futures.popleft()
            audio_b64, content_type, synth_ms = future.result()
            if total_tts_ms is not None:
                total_tts_ms += synth_ms
            if first_chunk_ms is None:
                first_chunk_ms = (time.perf_counter() - start_time) * 1000
            yield _sse_event(
                "chunk", {"index": idx, "text": text, "audioBase64": audio_b64, "contentType": content_type}
            )

        if llm_error is not None:
            logger.error("LLM-Streaming fehlgeschlagen (project_id=%s): %s", project_id, llm_error)
            yield _sse_event("error", {"detail": ErrorCode.CHAT_UNAVAILABLE})
            return

        # Belt and braces: if ArcanaReferenceGuard ever leaked, the saved transcript and the
        # final text sent to the client still come out clean.
        full_reply = _strip_arcana_references("".join(full_text_parts).strip())

        if save_conversations:
            try:
                with Session(engine) as fresh_session:
                    _save_conversation_turn(
                        fresh_session,
                        project_id,
                        visitor_id,
                        user_message,
                        full_reply,
                        message_received_at,
                        reply_ready_at,
                        visitor_name,
                    )
            except Exception:
                # The reply itself already reached the visitor via the chunk events above —
                # only the save failed, so log it instead of turning it into an error event
                # this late (that would incorrectly tell the client the whole reply failed).
                logger.exception("Konversation konnte nicht gespeichert werden (project_id=%s)", project_id)

        yield _sse_event(
            "done",
            {
                "reply": full_reply,
                "llmMs": llm_ms,
                "firstChunkMs": first_chunk_ms,
                "firstChunkTextReadyMs": first_chunk_ready_ms,
                "ttsMs": total_tts_ms,
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{slug}/transcribe", response_model=TranscriptionOut)
def transcribe(
    audio: UploadFile,
    request: Request,
    response: Response,
    project: Project = Depends(get_published_project),
    session: Session = Depends(get_session),
    x_chat_unlock_token: str | None = Header(default=None),
    x_visitor_name: str | None = Header(default=None),
    # Text already transcribed earlier in the same recording (see the frontend's pause-triggered
    # segmentation) — optional and unused by a plain single-shot recording, which sends nothing.
    initial_prompt: str | None = Form(default=None),
):
    """Transcribe a visitor's voice message for the public chat.

    Deliberately a plain `def`, not `async def`: transcription is synchronous and CPU-bound
    (see services/stt_service.py), and FastAPI runs a sync `def` route in its worker thread
    pool instead of on the event loop. An `async def` here would block every other request in
    the process — page loads, other visitors' chats, SSE streams — for the whole transcription.
    """
    visitor_id = get_or_set_visitor_id(request, response)
    assert_unlocked(project, visitor_id, x_chat_unlock_token)
    assert_visitor_name_provided(project, clean_visitor_name(x_visitor_name))
    enforce_public_transcribe_rate_limit(request, visitor_id)

    if not project.stt_enabled:
        raise HTTPException(status_code=503, detail=ErrorCode.VOICE_INPUT_UNAVAILABLE)
    if audio.content_type not in _ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=ErrorCode.UNSUPPORTED_AUDIO_FORMAT)
    content = audio.file.read(_MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(content) > _MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.AUDIO_FILE_TOO_LARGE)
    if initial_prompt:
        initial_prompt = initial_prompt[-_MAX_INITIAL_PROMPT_CHARS:]

    stt_key = resolve_stt_key(session, project)
    stt_start = time.perf_counter()
    try:
        text = transcribe_audio(content, project.spoken_language, initial_prompt, api_key_record=stt_key)
    except Exception as exc:
        # Generic message for visitors (no technical detail), consistent with send_message.
        logger.exception("Transkription fehlgeschlagen (project_id=%s)", project.id)
        raise HTTPException(status_code=503, detail=ErrorCode.VOICE_INPUT_UNAVAILABLE) from exc
    stt_ms = (time.perf_counter() - stt_start) * 1000
    return TranscriptionOut(text=text, stt_ms=stt_ms)
