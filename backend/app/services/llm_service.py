"""
LLM Chat Completion

Sends a chat message to a project's configured LLM (large language model) provider and returns
the reply. Most providers go through litellm; GWDG Arcana has its own direct HTTP integration
(see _send_chat_arcana) because litellm doesn't support its RAG (retrieval-augmented generation)
header/field.

How to use:
    from app.services.llm_service import send_chat_message

    reply = send_chat_message(preprompt, message, api_key, temperature, top_p, start_prompt, history)
"""

import json
import logging
import re
import time
from collections.abc import Iterator
from typing import Literal

import httpx
import litellm

from app.core.error_codes import ErrorCode
from app.core.providers import GWDG_ARCANA_PROVIDER, build_model_string, get_provider
from app.models.api_key import UserApiKey
from app.services.api_key_service import effective_api_base
from app.services.crypto_service import reveal_api_key

logger = logging.getLogger(__name__)

_GWDG_ARCANA_TIMEOUT = 60.0  # A RAG lookup + model reply noticeably takes longer than a plain chat call.
# GWDG's API occasionally responds with its own 5xx error (observed: 500 Internal Server Error,
# with no apparent connection to the request itself) — retrying tends to fix it in practice. 4xx
# is NOT retried (a wrong key, invalid request, etc. would just fail the same way again).
_GWDG_ARCANA_MAX_ATTEMPTS = 3
_GWDG_ARCANA_RETRY_DELAY = 1.5
# The same idea as the Arcana retry above, but for every other provider (they all go through
# litellm). Why this is worth the added latency: measured against GWDG chat-ai with
# backend/scripts/gwdg_diag.sh, 9 of 20 *identical* requests came back as an empty-bodied 500 in
# ~98ms — too fast for the model to have run at all — while the other 11 succeeded. At that
# failure rate a single attempt is a coin flip.
#
# A 5xx, a timeout, or a dropped connection is usually transient; a 4xx (wrong key, unknown model,
# malformed request) would fail identically on a second try, so it isn't retried. RateLimitError
# is deliberately left out too: a fixed short delay rarely clears a quota, and failing fast gets
# us to the non-streamed fallback in stream_chat_message sooner.
_TRANSIENT_LLM_ERRORS = (
    litellm.InternalServerError,
    litellm.ServiceUnavailableError,
    litellm.APIConnectionError,
    litellm.Timeout,
)
# Delay before each retry, in seconds; one entry per retry, so len() + 1 attempts in total. The
# first retry is deliberately immediate: the failure above arrives before any model ran, so there
# is no load to back off from, and waiting would only add to the time until the visitor hears the
# first word. The later retries do back off, in case the gateway genuinely is shedding load.
_LLM_RETRY_DELAYS = (0.0, 0.5, 1.5)
_LLM_MAX_ATTEMPTS = len(_LLM_RETRY_DELAYS) + 1
# Forces IPv4: some networks advertise IPv6 addresses for a host that are actually unreachable
# (routed nowhere, not even rejected) — httpx tries every resolved address in order and eats the
# full per-address timeout on each dead one before falling back to IPv4, which can turn a
# healthy timeout into several minutes. Binding the local address to the IPv4 wildcard makes
# httpx skip IPv6 candidates entirely instead of hanging on them one by one.
_IPV4_ONLY_TRANSPORT = httpx.HTTPTransport(local_address="0.0.0.0")
# One Client, created once and never closed, instead of a fresh "with httpx.Client(...)" per
# call: a Client passed an explicit transport= doesn't own a private copy of it, so closing the
# Client on a `with`-exit closes the connection pool for every concurrent caller sharing the same
# module-level transport too (confirmed against the installed httpx/httpcore source — .close()
# force-closes every connection currently on the pool, active or idle, not just this call's own).
# A single long-lived Client both avoids that and gives every call real keep-alive.
_client = httpx.Client(transport=_IPV4_ONLY_TRANSPORT)

# When its knowledge base (RAG) is enabled, Arcana appends a "References:" block with the raw
# source chunks (format "[RREF1] file.pdf p.X,y:Y (score)") directly onto the reply text — there's
# no separate API field for it, and no documented toggle to turn it off (checked the GWDG docs,
# see the docstring of _send_chat_arcana). That's just noise for students, so it's cut off here.
_ARCANA_REFERENCES_RE = re.compile(r"\n-{3,}\s*\n\s*References:", re.IGNORECASE)


def _strip_arcana_references(content: str) -> str:
    """Cut off Arcana's appended "References:" source-chunk block, if present."""
    match = _ARCANA_REFERENCES_RE.search(content)
    return content[: match.start()].rstrip() if match else content


def _scan_reference_marker(buf: str) -> Literal["confirmed", "diverged", "need_more"]:
    """Try to match `buf` against the marker shape from the start: "\\n-{3,}\\s*\\n\\s*References:"
    (case-insensitive on the literal). Re-examines `buf` from scratch every call instead of
    tracking a persistent phase — the held tail is always small (bounded by how long a divergence
    takes to appear), so this stays cheap and is far easier to reason about than an incremental
    parser with saved sub-state.
    """
    n = len(buf)
    if n == 0 or buf[0] != "\n":
        return "diverged"

    i = 1
    dash_count = 0
    while i < n and buf[i] == "-":
        dash_count += 1
        i += 1
    if i >= n:
        return "need_more"  # more dashes might still be coming
    if dash_count < 3:
        return "diverged"

    # \s*\n\s* is equivalent to "a whitespace run containing at least one \n" — either \s* can
    # itself absorb further newlines, so only the presence of one somewhere in the run matters.
    seen_newline = False
    while i < n and buf[i].isspace():
        seen_newline = seen_newline or buf[i] == "\n"
        i += 1
    if i >= n:
        return "need_more"  # still inside the whitespace run — more could still arrive
    if not seen_newline:
        return "diverged"

    literal = "references:"
    remaining = buf[i:].lower()
    match_len = min(len(remaining), len(literal))
    if remaining[:match_len] != literal[:match_len]:
        return "diverged"
    return "need_more" if len(remaining) < len(literal) else "confirmed"


class ArcanaReferenceGuard:
    """Filters Arcana's trailing '---\\nReferences:' block out of a token stream.

    feed() returns text that is safe to speak. Once the marker is confirmed, `finished` becomes
    True and the caller must stop consuming the stream.
    """

    def __init__(self) -> None:
        self._buf = ""
        # SCANNING: how far into _buf has already been confirmed to contain no trigger ("\n-").
        self._scan_pos = 0
        self._holding = False
        self.finished = False

    def feed(self, delta: str) -> str:
        if self.finished:
            return ""
        self._buf += delta
        released: list[str] = []
        while True:
            if not self._holding:
                trigger = self._find_trigger()
                if trigger is not None:
                    released.append(self._buf[:trigger])
                    self._buf = self._buf[trigger:]
                    self._holding = True
                    continue
                # Nothing pending except possibly a lone trailing "\n" still awaiting its
                # lookahead character — everything before that is definitely safe text.
                if self._scan_pos:
                    released.append(self._buf[: self._scan_pos])
                    self._buf = self._buf[self._scan_pos :]
                    self._scan_pos = 0
                break

            result = _scan_reference_marker(self._buf)
            if result == "need_more":
                break
            if result == "confirmed":
                self.finished = True
                self._buf = ""
                break
            # Diverged — a plain markdown "---" rule, not the marker. Go back to scanning, but
            # resume one character past the opening "\n" so the same failed attempt isn't found
            # again immediately (which would loop forever) — a later, genuine marker further
            # down the still-held text is still found this way.
            self._holding = False
            self._scan_pos = 1
        return "".join(released)

    def flush(self) -> str:
        """End of stream: resolve whatever is still held. If a marker attempt was left hanging
        (e.g. the reply ends exactly on "\\n---"), there is no more input to disambiguate it, so
        fall back to the same regex used post-hoc on a complete reply."""
        remainder = self._buf
        self._buf = ""
        if self._holding and _ARCANA_REFERENCES_RE.search(remainder):
            return ""
        return remainder

    def _find_trigger(self) -> int | None:
        """Index of the next "\n" immediately followed by "-" at/after _scan_pos, or None."""
        buf = self._buf
        n = len(buf)
        i = self._scan_pos
        while i < n:
            if buf[i] == "\n":
                if i + 1 >= n:
                    # Never decide on the final character of the buffer — the next token might
                    # still turn this into a real trigger.
                    self._scan_pos = i
                    return None
                if buf[i + 1] == "-":
                    return i
            i += 1
        self._scan_pos = i
        return None


# Limits how many previous messages are sent per request, regardless of how much the client
# actually sends (the history only lives in the browser tab, see
# frontend/src/pages/PublicChat/index.tsx, so it's client-controlled). Without this cap, a long
# conversation would let the context window and cost per request grow without bound.
_MAX_HISTORY_MESSAGES = 20


def _sampling_params(temperature: float | None, top_p: float | None) -> dict:
    """The project's temperature/top_p as request kwargs, omitting whichever one is None.

    Both are standard OpenAI-compatible parameters that litellm passes on to every provider it
    supports (`litellm.get_supported_openai_params` lists them for openai, ollama, gemini, ...),
    and the GWDG Arcana endpoint accepts them in its request body too. Omitting rather than
    sending a default matters: a provider that doesn't know a parameter can reject the whole
    request, so "not configured" has to mean "not in the body at all".
    """
    params = {}
    if temperature is not None:
        params["temperature"] = temperature
    if top_p is not None:
        params["top_p"] = top_p
    return params


def _build_messages(preprompt: str, message: str, start_prompt: str | None, history: list[dict] | None = None) -> list[dict]:
    """Build the litellm-style message list from the project's prompt, optional start message, and history."""
    # start_prompt is inserted as an earlier assistant message (not as part of the system
    # prompt) — that way the model "remembers", on every request, that it actually said this
    # itself (e.g. a posed task), consistent with the bubble students see as the first message
    # (see api/public_chat.py::load_tutor). history is the actual, already-exchanged conversation
    # so far — without it, every request would be stateless.
    messages = [{"role": "system", "content": preprompt}]
    if start_prompt:
        messages.append({"role": "assistant", "content": start_prompt})
    if history:
        messages.extend(history[-_MAX_HISTORY_MESSAGES:])
    messages.append({"role": "user", "content": message})
    return messages


def _send_chat_arcana(
    preprompt: str,
    message: str,
    api_key_record: UserApiKey,
    temperature: float | None,
    top_p: float | None,
    start_prompt: str | None,
    history: list[dict] | None,
) -> str:
    """Direct HTTP call to the GWDG SAIA API — litellm knows neither the required
    "inference-service" header nor the "arcana" field used to address the knowledge base (RAG).

    "enable-tools": true is sent together with the Arcana ID because, per the GWDG docs ("How to
    use Arcana"), both are enabled together in the web interface too — there's no explicit
    statement in the GWDG docs that the knowledge lookup is skipped without "enable-tools"; this
    behavior has NOT been verified against a real account. See
    https://docs.hpc.gwdg.de/services/ai-services/saia/index.html.
    """
    if not api_key_record.model_id:
        raise ValueError(ErrorCode.ARCANA_KEY_MISSING_MODEL)
    if not api_key_record.arcana_id:
        raise ValueError(ErrorCode.ARCANA_KEY_MISSING_ID)

    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    default_api_base = get_provider(GWDG_ARCANA_PROVIDER).default_api_base
    api_base = (api_key_record.api_base or default_api_base).rstrip("/")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "inference-service": "saia-openai-gateway",
    }
    body = {
        "model": api_key_record.model_id,
        "messages": _build_messages(preprompt, message, start_prompt, history),
        "enable-tools": True,
        "arcana": {"id": api_key_record.arcana_id},
        **_sampling_params(temperature, top_p),
    }

    for attempt in range(1, _GWDG_ARCANA_MAX_ATTEMPTS + 1):
        try:
            response = _client.post(f"{api_base}/chat/completions", headers=headers, json=body, timeout=_GWDG_ARCANA_TIMEOUT)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Log the response body too, otherwise all you see at the end is "500 Internal Server
            # Error" with no clue what actually went wrong on GWDG's side.
            is_transient = exc.response.status_code >= 500
            logger.warning(
                "GWDG Arcana antwortete mit %s (Versuch %d/%d)%s: %s",
                exc.response.status_code,
                attempt,
                _GWDG_ARCANA_MAX_ATTEMPTS,
                ", erneuter Versuch folgt" if is_transient and attempt < _GWDG_ARCANA_MAX_ATTEMPTS else "",
                exc.response.text[:500],
            )
            if not is_transient or attempt == _GWDG_ARCANA_MAX_ATTEMPTS:
                raise
        except httpx.TransportError as exc:
            # Connection drop/timeout — also typically transient.
            logger.warning(
                "GWDG Arcana nicht erreichbar (Versuch %d/%d): %s", attempt, _GWDG_ARCANA_MAX_ATTEMPTS, exc
            )
            if attempt == _GWDG_ARCANA_MAX_ATTEMPTS:
                raise
        else:
            content = response.json()["choices"][0]["message"]["content"]
            return _strip_arcana_references(content)
        time.sleep(_GWDG_ARCANA_RETRY_DELAY)


def _stream_chat_arcana(
    preprompt: str,
    message: str,
    api_key_record: UserApiKey,
    temperature: float | None,
    top_p: float | None,
    start_prompt: str | None,
    history: list[dict] | None,
) -> Iterator[str]:
    """Streamed variant of _send_chat_arcana — same endpoint, headers, and body, plus
    "stream": True, parsed as OpenAI-style SSE (server-sent events). Each delta is passed through
    an ArcanaReferenceGuard so the citation block never reaches the caller (see its docstring).
    """
    if not api_key_record.model_id:
        raise ValueError(ErrorCode.ARCANA_KEY_MISSING_MODEL)
    if not api_key_record.arcana_id:
        raise ValueError(ErrorCode.ARCANA_KEY_MISSING_ID)

    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    default_api_base = get_provider(GWDG_ARCANA_PROVIDER).default_api_base
    api_base = (api_key_record.api_base or default_api_base).rstrip("/")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "inference-service": "saia-openai-gateway",
    }
    body = {
        "model": api_key_record.model_id,
        "messages": _build_messages(preprompt, message, start_prompt, history),
        "enable-tools": True,
        "arcana": {"id": api_key_record.arcana_id},
        "stream": True,
        **_sampling_params(temperature, top_p),
    }

    # A read timeout (time between chunks), not a whole-call timeout — a long streamed reply must
    # not trip this just because the total stream duration exceeds _GWDG_ARCANA_TIMEOUT. Connect
    # still fails fast so a dead handshake doesn't hang the retry loop.
    timeout = httpx.Timeout(10.0, read=_GWDG_ARCANA_TIMEOUT)

    for attempt in range(1, _GWDG_ARCANA_MAX_ATTEMPTS + 1):
        past_handshake = False
        try:
            with _client.stream("POST", f"{api_base}/chat/completions", headers=headers, json=body, timeout=timeout) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    response.read()  # buffers the body so .text is readable below
                    is_transient = exc.response.status_code >= 500
                    logger.warning(
                        "GWDG Arcana antwortete mit %s (Versuch %d/%d)%s: %s",
                        exc.response.status_code,
                        attempt,
                        _GWDG_ARCANA_MAX_ATTEMPTS,
                        ", erneuter Versuch folgt" if is_transient and attempt < _GWDG_ARCANA_MAX_ATTEMPTS else "",
                        exc.response.text[:500],
                    )
                    if not is_transient or attempt == _GWDG_ARCANA_MAX_ATTEMPTS:
                        raise
                    time.sleep(_GWDG_ARCANA_RETRY_DELAY)
                    continue

                # Past this point a failure must NOT retry — the visitor may already have
                # heard part of the reply, and replaying it would duplicate speech.
                past_handshake = True
                guard = ArcanaReferenceGuard()
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                    if delta is None:
                        continue
                    safe_text = guard.feed(delta)
                    if safe_text:
                        yield safe_text
                    if guard.finished:
                        return
                tail = guard.flush()
                if tail:
                    yield tail
                return
        except httpx.TransportError as exc:
            if past_handshake:
                raise
            # Connection drop/timeout before any content arrived — also typically transient.
            logger.warning(
                "GWDG Arcana nicht erreichbar (Versuch %d/%d): %s", attempt, _GWDG_ARCANA_MAX_ATTEMPTS, exc
            )
            if attempt == _GWDG_ARCANA_MAX_ATTEMPTS:
                raise
            time.sleep(_GWDG_ARCANA_RETRY_DELAY)


def _resolve_call(api_key_record: UserApiKey, model_id: str) -> tuple[str, dict]:
    """Work out the litellm model string and endpoint override for a stored key."""
    # The provider prefix and endpoint come from the registry and the stored key — litellm
    # doesn't care which actual provider sits behind an OpenAI-compatible endpoint, as long as
    # the prefix ("openai/") and api_base are correct.
    model = build_model_string(api_key_record.provider, model_id)
    api_base = effective_api_base(api_key_record)
    return model, ({"api_base": api_base} if api_base else {})


def _retry_transient(call):
    """Call `call`, retrying a transient provider failure up to _LLM_MAX_ATTEMPTS times.

    Only safe for calls that produce nothing until they return — a streamed reply hands out text
    as it goes and needs the finer-grained rule in _stream_chat_litellm instead.
    """
    for attempt in range(1, _LLM_MAX_ATTEMPTS + 1):
        try:
            return call()
        except _TRANSIENT_LLM_ERRORS as exc:
            if attempt == _LLM_MAX_ATTEMPTS:
                raise
            logger.warning(
                "LLM-Anfrage fehlgeschlagen (Versuch %d/%d), erneuter Versuch folgt: %s",
                attempt,
                _LLM_MAX_ATTEMPTS,
                exc,
            )
            time.sleep(_LLM_RETRY_DELAYS[attempt - 1])


def send_chat_message(
    preprompt: str,
    message: str,
    api_key_record: UserApiKey,
    temperature: float | None = None,
    top_p: float | None = None,
    start_prompt: str | None = None,
    history: list[dict] | None = None,
) -> str:
    """Send a chat message to the project's configured LLM and return the reply text."""
    if api_key_record.provider == GWDG_ARCANA_PROVIDER:
        return _send_chat_arcana(preprompt, message, api_key_record, temperature, top_p, start_prompt, history)

    # Bring-your-own-key: model, endpoint, and secret all come from the key record the project
    # references (Project.llm_api_key_id) — that's why the model choice in the configurator is
    # limited to keys the user has actually set up.
    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    model, extra = _resolve_call(api_key_record, api_key_record.model_id or "")
    response = _retry_transient(
        lambda: litellm.completion(
            model=model,
            # Ollama servers usually don't require authentication — an empty stored key is passed
            # as None instead of an empty string, otherwise litellm would set an empty Bearer
            # header.
            api_key=api_key or None,
            messages=_build_messages(preprompt, message, start_prompt, history),
            **_sampling_params(temperature, top_p),
            **extra,
        )
    )
    return response.choices[0].message.content


def _stream_chat_litellm(
    preprompt: str,
    message: str,
    api_key_record: UserApiKey,
    temperature: float | None,
    top_p: float | None,
    start_prompt: str | None,
    history: list[dict] | None,
) -> Iterator[str]:
    """Streamed chat for every provider except Arcana, retrying transient provider failures.

    Retrying is only safe while nothing has been yielded yet: once the caller holds a delta it may
    already have been synthesized and spoken (see api/public_chat.py::send_message_stream), and
    starting over would make the avatar say the beginning of the reply a second time. This mirrors
    the `past_handshake` rule in _stream_chat_arcana.
    """
    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    model, extra = _resolve_call(api_key_record, api_key_record.model_id or "")

    for attempt in range(1, _LLM_MAX_ATTEMPTS + 1):
        yielded = False
        try:
            response = litellm.completion(
                model=model,
                api_key=api_key or None,
                messages=_build_messages(preprompt, message, start_prompt, history),
                stream=True,
                **_sampling_params(temperature, top_p),
                **extra,
            )
            for chunk in response:
                # litellm emits role-only and finish chunks with delta.content == None.
                delta = chunk.choices[0].delta.content
                if delta is not None:
                    yielded = True
                    yield delta
            return
        except _TRANSIENT_LLM_ERRORS as exc:
            if yielded or attempt == _LLM_MAX_ATTEMPTS:
                raise
            logger.warning(
                "LLM-Stream fehlgeschlagen (Versuch %d/%d), erneuter Versuch folgt: %s",
                attempt,
                _LLM_MAX_ATTEMPTS,
                exc,
            )
            time.sleep(_LLM_RETRY_DELAYS[attempt - 1])


def stream_chat_message(
    preprompt: str,
    message: str,
    api_key_record: UserApiKey,
    temperature: float | None = None,
    top_p: float | None = None,
    start_prompt: str | None = None,
    history: list[dict] | None = None,
) -> Iterator[str]:
    """Yield reply text deltas. Arcana's citation block is filtered out mid-stream.

    If streaming fails before the very first delta, this falls back to the plain non-streamed call
    and yields the whole reply as one delta. The visitor then still gets an answer out of this one
    request — without it the frontend has to notice the failure and ask the LLM all over again
    (see pages/PublicChat/index.tsx), which costs a second full round trip for a reply the server
    could have fetched itself. The caller needs no special case: a single large delta just chunks
    into more sentences at once.
    """
    if api_key_record.provider == GWDG_ARCANA_PROVIDER:
        streamer = _stream_chat_arcana(preprompt, message, api_key_record, temperature, top_p, start_prompt, history)
    else:
        streamer = _stream_chat_litellm(preprompt, message, api_key_record, temperature, top_p, start_prompt, history)

    yielded = False
    try:
        for delta in streamer:
            yielded = True
            yield delta
    except Exception as exc:
        # Same rule as the retry in _stream_chat_litellm: once part of the reply has left this
        # function it may already have been spoken, so a mid-stream failure has to stay a failure.
        if yielded:
            raise
        logger.warning("Streaming fehlgeschlagen, fällt auf eine normale Anfrage zurück: %s", exc)
        reply = send_chat_message(preprompt, message, api_key_record, temperature, top_p, start_prompt, history)
        if reply:
            yield reply


def test_api_key(api_key_record: UserApiKey) -> None:
    """Try a stored key with a minimal real call; raises on an invalid key or provider error."""
    # Raises an exception on an invalid key/provider error — the caller (api/api_keys.py) catches
    # it, sets the status, and passes the message on to the UI.
    if api_key_record.provider == GWDG_ARCANA_PROVIDER:
        # No cheap test model available (this call doesn't go through litellm) — the test costs
        # the same RAG lookup as a real chat call.
        _send_chat_arcana("Du bist ein hilfreicher Assistent.", "ping", api_key_record, None, None, None, None)
        return

    plaintext = reveal_api_key(api_key_record.encrypted_api_key)
    spec = get_provider(api_key_record.provider)

    # Prefers testing the model actually configured — that checks the key, endpoint, and model
    # name in one go. Only falls back to the provider's cheap ping model if none is set (RAG keys).
    if api_key_record.model_id:
        model, extra = _resolve_call(api_key_record, api_key_record.model_id)
    elif spec is not None and spec.test_model:
        api_base = effective_api_base(api_key_record)
        model, extra = spec.test_model, ({"api_base": api_base} if api_base else {})
    else:
        raise ValueError(ErrorCode.API_KEY_NO_TESTABLE_MODEL)

    litellm.completion(
        model=model,
        api_key=plaintext or None,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
        **extra,
    )
