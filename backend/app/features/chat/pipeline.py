"""
Chat Pipeline

The one place that combines the AI building blocks (app/features/ai) into a chat turn: resolve
the project's keys, ask the LLM, save the exchange, and synthesize speech — either as one reply
(reply_turn) or as sentence-sized chunks streamed while the LLM is still writing (stream_turn).
Used by both the public chat (public_router.py) and the configurator's preview chat
(preview_router.py); each maps failures to its own HTTP responses.

How to use:
    context = prepare_chat(session, project)  # None if no LLM key is configured
    session.close()                            # optional: don't hold a DB connection during the LLM call
    reply = reply_turn(context, ChatTurn(message, history))
"""

import base64
import logging
import time
from collections import deque
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.features.ai import llm
from app.features.ai.tts import synthesize_speech
from app.features.api_keys.models import UserApiKey
from app.features.api_keys.resolve import resolve_llm_key, resolve_tts_key
from app.features.chat.conversation_store import save_turn
from app.features.chat.streaming import SentenceChunker
from app.features.projects.models import Project

# Visitors deliberately only get generic error messages (no technical detail) — so the actual
# error is still visible *somewhere* instead of being swallowed entirely, it goes into the
# server log here.
logger = logging.getLogger(__name__)

# Shared across every streamed reply instead of one ThreadPoolExecutor(max_workers=1) per
# request: chunk *yield* order is already enforced per-request by the `futures` deque in
# stream_turn() below (it only pops a chunk once the one before it is done), so which worker
# thread actually runs a given chunk's synthesis doesn't affect ordering — sharing one bounded
# pool just replaces "one thread per concurrent streaming reply, unbounded" with a fixed ceiling.
_tts_executor = ThreadPoolExecutor(max_workers=settings.tts_stream_worker_pool_size)


@dataclass(frozen=True)
class ChatContext:
    """Everything a chat turn needs from the project and its keys, read up front.

    Plain values and detached key records only, so a turn can run for seconds (or, streamed, after
    the route has returned) without touching — or holding open — the request's DB session.
    """

    project_id: str
    llm_key: UserApiKey
    tts_key: UserApiKey | None
    preprompt: str
    temperature: float | None
    top_p: float | None
    start_prompt: str | None
    tts_voice: str | None
    spoken_language: str
    save_conversations: bool


@dataclass
class ChatTurn:
    """One visitor message, plus who sent it and when (for the saved conversation)."""

    message: str
    history: list[dict]
    visitor_id: str | None = None
    visitor_name: str | None = None
    # Captured before any LLM/TTS work — the closest we get to "when the visitor actually sent
    # this", used for the saved message's per-message timestamp.
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChatReply:
    text: str
    audio_base64: str | None
    content_type: str | None
    llm_ms: float
    # None (not ~0ms) when TTS didn't actually run (disabled/no key).
    tts_ms: float | None


class LLMFailed(Exception):
    """The LLM call itself failed; `__cause__` is the provider's original exception."""


def prepare_chat(session: Session, project: Project) -> ChatContext | None:
    """Resolve the project's LLM (and, if enabled, TTS) key and snapshot what a turn needs.

    None if the project has no usable LLM key. The key records are expunged from `session` so
    their already-loaded columns can never be invalidated by a later commit expiring them — the
    caller may close or keep using the session independently of the returned context.
    """
    api_key = resolve_llm_key(session, project)
    if api_key is None:
        return None
    tts_api_key = resolve_tts_key(session, project) if project.tts_enabled else None
    session.expunge(api_key)
    if tts_api_key is not None:
        session.expunge(tts_api_key)
    return ChatContext(
        project_id=project.id,
        llm_key=api_key,
        tts_key=tts_api_key,
        preprompt=project.preprompt or "",
        temperature=project.temperature,
        top_p=project.top_p,
        start_prompt=project.start_prompt,
        tts_voice=project.tts_voice,
        spoken_language=project.spoken_language,
        save_conversations=project.save_conversations,
    )


def _chat_request(context: ChatContext, turn: ChatTurn) -> llm.ChatRequest:
    return llm.ChatRequest(
        context.preprompt, turn.message, context.temperature, context.top_p, context.start_prompt, turn.history
    )


def _save(context: ChatContext, turn: ChatTurn, reply: str, reply_ready_at: datetime) -> None:
    save_turn(
        context.project_id, turn.visitor_id, turn.message, reply, turn.received_at, reply_ready_at, turn.visitor_name
    )


def _synthesize(context: ChatContext, text: str) -> tuple[str | None, str | None, float]:
    """Speech for `text` as (audioBase64, contentType, ms); never raises — speech output is an
    addition to the text reply, so a TTS failure is logged and the text still goes out."""
    if context.tts_key is None:
        return None, None, 0.0
    synth_start = time.perf_counter()
    try:
        audio_bytes, content_type = synthesize_speech(text, context.tts_voice, context.tts_key, context.spoken_language)
    except Exception:
        logger.exception("TTS fehlgeschlagen (project_id=%s)", context.project_id)
        return None, None, (time.perf_counter() - synth_start) * 1000
    return base64.b64encode(audio_bytes).decode(), content_type, (time.perf_counter() - synth_start) * 1000


def reply_turn(context: ChatContext, turn: ChatTurn, *, save: bool = True) -> ChatReply:
    """Ask the LLM, save the exchange (if the project saves conversations and `save`), then
    synthesize the whole reply. Raises LLMFailed if the LLM call fails."""
    # Timed for the client-side latency-test log (see pages/PublicChat/index.tsx) — not used by
    # the default UI, just extra fields riding along in the response.
    llm_start = time.perf_counter()
    try:
        reply = llm.complete(context.llm_key, _chat_request(context, turn))
    except Exception as exc:
        raise LLMFailed() from exc
    llm_ms = (time.perf_counter() - llm_start) * 1000
    reply_ready_at = datetime.now(timezone.utc)

    if save and context.save_conversations:
        _save(context, turn, reply, reply_ready_at)

    tts_start = time.perf_counter()
    audio_base64, content_type, _ = _synthesize(context, reply)
    tts_ms = (time.perf_counter() - tts_start) * 1000 if audio_base64 is not None else None
    return ChatReply(reply, audio_base64, content_type, llm_ms, tts_ms)


def stream_turn(context: ChatContext, turn: ChatTurn) -> Iterator[tuple[str, dict]]:
    """Yield (event, data) pairs for a streamed reply: one "chunk" per sentence-sized piece (see
    streaming.py), each synthesized as soon as it's ready — so the avatar can start speaking well
    before the full reply exists — then "done" (or "error" if the LLM failed).

    Never raises for an LLM or save failure: by the time either happens, part of the reply may
    already have reached the client.
    """
    start_time = time.perf_counter()
    first_chunk_ms: float | None = None
    # Time until the first chunk is handed to TTS, distinct from first_chunk_ms (time until
    # that chunk's synthesis *finishes*) — isolates LLM/chunking speed from TTS speed. Captured
    # in submit() itself since that's the one place both the per-delta loop and the
    # chunker.flush() tail path funnel through.
    first_chunk_ready_ms: float | None = None
    total_tts_ms: float | None = 0.0 if context.tts_key is not None else None
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
        futures.append((next_index, _tts_executor.submit(_synthesize, context, text), text))
        next_index += 1

    def chunk_event(idx: int, future: Future, text: str) -> tuple[str, dict]:
        nonlocal first_chunk_ms, total_tts_ms
        audio_b64, content_type, synth_ms = future.result()
        if total_tts_ms is not None:
            total_tts_ms += synth_ms
        if first_chunk_ms is None:
            first_chunk_ms = (time.perf_counter() - start_time) * 1000
        return "chunk", {"index": idx, "text": text, "audioBase64": audio_b64, "contentType": content_type}

    def pop_ready():
        while futures and futures[0][1].done():
            yield chunk_event(*futures.popleft())

    llm_error: Exception | None = None
    try:
        for delta in llm.stream(context.llm_key, _chat_request(context, turn)):
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
        yield chunk_event(*futures.popleft())

    if llm_error is not None:
        logger.error("LLM-Streaming fehlgeschlagen (project_id=%s): %s", context.project_id, llm_error)
        yield "error", {"detail": ErrorCode.CHAT_UNAVAILABLE}
        return

    # Belt and braces: if ArcanaReferenceGuard ever leaked, the saved transcript and the
    # final text sent to the client still come out clean.
    full_reply = llm.strip_arcana_references("".join(full_text_parts).strip())

    if context.save_conversations:
        try:
            _save(context, turn, full_reply, reply_ready_at)
        except Exception:
            # The reply itself already reached the visitor via the chunk events above —
            # only the save failed, so log it instead of turning it into an error event
            # this late (that would incorrectly tell the client the whole reply failed).
            logger.exception("Konversation konnte nicht gespeichert werden (project_id=%s)", context.project_id)

    yield "done", {
        "reply": full_reply,
        "llmMs": llm_ms,
        "firstChunkMs": first_chunk_ms,
        "firstChunkTextReadyMs": first_chunk_ready_ms,
        "ttsMs": total_tts_ms,
    }
