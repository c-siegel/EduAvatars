# Handoff: backend bug fixes (branch `fix/known-bugs`)

Continuation notes for an in-progress Claude Code task. Delete this file once the work is done.

## Where things stand

- **Branch:** `fix/known-bugs`. It contains everything: the backend restructuring (feature packages
  under `backend/app/features/`), the `/api/v1` URL changes, the merge with `working-branch`
  (local TTS, browser STT), and the bug fixes so far.
- **Restructuring PR:** `refactor/api-v1` (commit `a319d34`) was meant as a separate PR into
  `working-branch`; its description draft lived outside the repo. `fix/known-bugs` sits on top of it.
- **Done (one commit each, with a regression test in `backend/tests/test_bugfixes.py`):**
  - Bug 3: disabled accounts get 403 `ACCOUNT_DISABLED` on login (`73a9d77`)
  - Bug 4: email addresses are case-insensitive (`8811bb2`)
  - Bug 5: the in-memory rate limiter is thread-safe (`ee359b7`)
- Bug 1 was fixed as part of the `/api/v1` work; bug 2 turned out not to be a bug.

## How to work

- One commit per bug, each with a regression test appended to `backend/tests/test_bugfixes.py`
  under its own `# ==== <title> ====` section.
- Run the full backend suite before every commit; it must stay green.
- If a fix changes the API contract (e.g. new parameter constraints), regenerate the snapshot
  deliberately and check its diff:
  `UPDATE_OPENAPI_SNAPSHOT=1 python -m pytest tests/test_openapi_contract.py`
- A new error code needs `de` and `en` entries in `frontend/src/i18n/locales/*.json`
  (under `errors`).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Setup

```
cd backend
python -m venv .venv            # or: uv venv .venv
.venv/Scripts/pip install -e ".[dev]"     # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest -q         # 186 tests should pass
```

`tests/conftest.py` sets throwaway `JWT_SECRET`/`API_KEY_ENCRYPTION_SECRET` if they're unset. The
route tests fake the AI providers at `litellm.completion`/`litellm.speech` and the local Whisper
loader. Frontend: `cd frontend && npm ci && npx tsc -b --noEmit && npm run build`.

## Remaining bugs (one commit each, in this order)

| # | Problem | Where | Planned fix |
|---|---|---|---|
| 6 | The streaming chat endpoint never sets the visitor cookie: it returns its own `StreamingResponse`, so the cookie `get_or_set_visitor_id` set on the injected `Response` is dropped. If the 4-hour cookie expires mid-lesson, each message gets a new visitor ID (split conversations, per-visitor rate limit bypassed, 401 on password-protected chats). | `backend/app/features/chat/public_router.py::send_message_stream` | Copy the `set-cookie` headers from the injected `response` onto the `StreamingResponse` (e.g. extend its `raw_headers`). Test: a cookie-less client posting to `/public/{slug}/messages/stream` gets `ah_visitor_id` in `set-cookie`. |
| 7 | Avatars/backgrounds are served anonymously if *any* published project references their ID, and projects accept any avatar/background ID without an ownership check. | `backend/app/features/media/service.py::is_used_by_published_project`; `backend/app/features/projects/service.py::_check_key_references` | (a) On project create/update, reject an `avatar_model_id`/`avatar_background_id` that isn't the user's own (400, reuse `AVATAR_NOT_FOUND`/`BACKGROUND_NOT_FOUND` or add new codes plus translations). (b) The public check should only count published projects owned by the asset's owner (`Project.user_id == asset.user_id`). Test: user B referencing A's avatar ID gets 400, and an anonymous fetch stays 404. |
| 8 | `stt_api_key_id` isn't checked on project create/update (LLM/TTS key IDs are), so foreign or wrong-type STT key IDs are stored silently. | `backend/app/features/projects/service.py::_check_key_references` | Add the same check with `KEY_TYPE_STT` (400 `UNKNOWN_API_KEY`). |
| 9 | An LLM reply with `content=None` (content filter / tool call) makes `ChatMessageOut(reply=None)` fail validation with a 500 instead of 503 `CHAT_UNAVAILABLE`; the preview chat has the same problem. | `backend/app/features/ai/llm/litellm_provider.py::LiteLLMClient.complete` | Raise an exception (e.g. `ValueError("LLM returned an empty reply")`) when `content is None`, so the pipeline's `LLMFailed` mapping returns 503 (public) / 502 (preview). Test via `fake_ai.llm_reply = None`. |
| 10 | Preview transcription errors return `str(exc)` without scrubbing the API key, unlike the other preview errors. | `backend/app/features/chat/preview_router.py::transcribe` | `scrub_key_from_text(str(exc), stt_key.encrypted_api_key) if stt_key else str(exc)`. |
| 11 | Account deletion leaves its projects' start-audio files on disk. | `backend/app/features/users/account.py::delete_user_account` | `unlink_quietly(project.start_audio_path)` for each project before the bulk delete. |
| 12 | The `page` and `period_days` query parameters aren't validated (0 or negative values accepted, negative `OFFSET`). | `backend/app/features/analytics/conversations_router.py`, `stats_router.py` | `Query(..., ge=1)` on `page` and `period_days` → 422. Changes the OpenAPI contract: regenerate the snapshot. |
| 13 | Older password-reset links stay valid after a newer one is requested or one is used. | `backend/app/features/auth/password_reset.py` | When issuing a token, mark the user's unused tokens as used; on a successful reset, mark all of the user's tokens as used. |
| 14 | A password reset doesn't clear `must_change_password`, so after an admin-forced reset the user is asked to change it again. | `backend/app/features/auth/password_reset.py::reset_password` | Set `user.must_change_password = False`. |
| 15 | The `stt_api_key_id` migration never added the foreign key the model declares; `alembic check` fails. | `backend/alembic/versions/a1b2c3d4e5f7_add_stt_api_key_id_to_project.py` | New migration after `f6a7b8c9d0e1` adding the FK with `op.batch_alter_table` (SQLite). Verify with `alembic upgrade head` and `alembic check` on a temp DB (`DATABASE_URL=sqlite:///...`). |
| 16 | A streamed reply holds a pooled DB connection for the whole stream (the plain endpoint closes its session before the LLM call). | `backend/app/features/chat/public_router.py::send_message_stream` | Call `session.close()` after `prepare_chat(...)` — everything the stream needs is already in the detached `ChatContext`. Test: `engine.pool.checkedout()` is 0 while `stream_turn` runs, with a file-based SQLite engine (see the probe described below). |

### Probe for bug 16

The connection count can only be observed with a real connection pool (`StaticPool` in the
in-memory test DB hides it). Create a file-based SQLite engine in `tmp_path`, copy the fixture's
rows into it, override `get_session` and `app.features.chat.conversation_store.engine` to use it,
and wrap `app.features.chat.public_router.stream_turn` to record `engine.pool.checkedout()` when
it starts. Before the fix that records 1; after it, 0.

## After all bugs are fixed

1. Run the full backend suite, `alembic check` on a fresh DB, and the frontend type-check and build.
2. Delete this file in a final commit.
3. Push `fix/known-bugs` and open a PR (into `working-branch`, or into `refactor/api-v1` if that
   PR is still open).
