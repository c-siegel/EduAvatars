"""
LLM Chat Completion

Sends a chat message to a project's configured LLM (large language model) provider and returns
the reply. Most providers go through litellm; GWDG Arcana has its own direct HTTP integration
(see _send_chat_arcana) because litellm doesn't support its RAG (retrieval-augmented generation)
header/field.

How to use:
    from app.services.llm_service import send_chat_message

    reply = send_chat_message(preprompt, message, api_key, temperature, start_prompt, history)
"""

import logging
import re
import time

import httpx
import litellm

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

# When its knowledge base (RAG) is enabled, Arcana appends a "References:" block with the raw
# source chunks (format "[RREF1] file.pdf p.X,y:Y (score)") directly onto the reply text — there's
# no separate API field for it, and no documented toggle to turn it off (checked the GWDG docs,
# see the docstring of _send_chat_arcana). That's just noise for students, so it's cut off here.
_ARCANA_REFERENCES_RE = re.compile(r"\n-{3,}\s*\n\s*References:", re.IGNORECASE)


def _strip_arcana_references(content: str) -> str:
    """Cut off Arcana's appended "References:" source-chunk block, if present."""
    match = _ARCANA_REFERENCES_RE.search(content)
    return content[: match.start()].rstrip() if match else content


# Limits how many previous messages are sent per request, regardless of how much the client
# actually sends (the history only lives in the browser tab, see
# frontend/src/pages/PublicChat/index.tsx, so it's client-controlled). Without this cap, a long
# conversation would let the context window and cost per request grow without bound.
_MAX_HISTORY_MESSAGES = 20


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
        raise ValueError("Für diesen Arcana-Key ist kein Modell hinterlegt.")
    if not api_key_record.arcana_id:
        raise ValueError("Für diesen Arcana-Key ist keine Arcana-ID hinterlegt.")

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
        **({"temperature": temperature} if temperature is not None else {}),
    }

    for attempt in range(1, _GWDG_ARCANA_MAX_ATTEMPTS + 1):
        try:
            response = httpx.post(f"{api_base}/chat/completions", headers=headers, json=body, timeout=_GWDG_ARCANA_TIMEOUT)
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


def _resolve_call(api_key_record: UserApiKey, model_id: str) -> tuple[str, dict]:
    """Work out the litellm model string and endpoint override for a stored key."""
    # The provider prefix and endpoint come from the registry and the stored key — litellm
    # doesn't care which actual provider sits behind an OpenAI-compatible endpoint, as long as
    # the prefix ("openai/") and api_base are correct.
    model = build_model_string(api_key_record.provider, model_id)
    api_base = effective_api_base(api_key_record)
    return model, ({"api_base": api_base} if api_base else {})


def send_chat_message(
    preprompt: str,
    message: str,
    api_key_record: UserApiKey,
    temperature: float | None = None,
    start_prompt: str | None = None,
    history: list[dict] | None = None,
) -> str:
    """Send a chat message to the project's configured LLM and return the reply text."""
    if api_key_record.provider == GWDG_ARCANA_PROVIDER:
        return _send_chat_arcana(preprompt, message, api_key_record, temperature, start_prompt, history)

    # Bring-your-own-key: model, endpoint, and secret all come from the key record the project
    # references (Project.llm_api_key_id) — that's why the model choice in the configurator is
    # limited to keys the user has actually set up.
    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    model, extra = _resolve_call(api_key_record, api_key_record.model_id or "")
    response = litellm.completion(
        model=model,
        # Ollama servers usually don't require authentication — an empty stored key is passed as
        # None instead of an empty string, otherwise litellm would set an empty Bearer header.
        api_key=api_key or None,
        messages=_build_messages(preprompt, message, start_prompt, history),
        # The creativity slider from the configurator (Project.creativity) used to be stored but
        # never actually passed to the model.
        **({"temperature": temperature} if temperature is not None else {}),
        **extra,
    )
    return response.choices[0].message.content


def test_api_key(api_key_record: UserApiKey) -> None:
    """Try a stored key with a minimal real call; raises on an invalid key or provider error."""
    # Raises an exception on an invalid key/provider error — the caller (api/api_keys.py) catches
    # it, sets the status, and passes the message on to the UI.
    if api_key_record.provider == GWDG_ARCANA_PROVIDER:
        # No cheap test model available (this call doesn't go through litellm) — the test costs
        # the same RAG lookup as a real chat call.
        _send_chat_arcana("Du bist ein hilfreicher Assistent.", "ping", api_key_record, None, None, None)
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
        raise ValueError("Für diesen Eintrag ist kein Modell hinterlegt, das sich testen ließe.")

    litellm.completion(
        model=model,
        api_key=plaintext or None,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
        **extra,
    )
