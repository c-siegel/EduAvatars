"""Tests for ArcanaReferenceGuard (app/services/llm_service.py) — filters GWDG Arcana's trailing
'---\\nReferences:' citation block out of a token stream so it never reaches (or gets spoken to)
a visitor. Importing app.services.llm_service pulls in app.core.config, which reads the shared
root .env for JWT_SECRET/API_KEY_ENCRYPTION_SECRET — already present there for local dev, so no
extra setup is needed to run these."""

from app.services.llm_service import ArcanaReferenceGuard


def _feed_all(guard: ArcanaReferenceGuard, text: str) -> str:
    """Feed `text` one character at a time; return everything the guard released, concatenated."""
    return "".join(guard.feed(ch) for ch in text)


def test_plain_text_without_a_marker_passes_through_unchanged():
    guard = ArcanaReferenceGuard()
    text = "Photosynthesis converts light energy into chemical energy in plants."
    out = guard.feed(text) + (guard.flush() or "")
    assert out == text
    assert guard.finished is False


def test_streamed_plain_text_passes_through_unchanged():
    guard = ArcanaReferenceGuard()
    text = "Photosynthesis converts light energy into chemical energy in plants."
    out = _feed_all(guard, text) + (guard.flush() or "")
    assert out == text
    assert guard.finished is False


def test_references_block_is_filtered_out_in_one_shot():
    guard = ArcanaReferenceGuard()
    text = "The answer is 42.\n---\nReferences:\n[RREF1] some_source.pdf p.1 (0.9)"
    released = guard.feed(text)
    assert released == "The answer is 42."
    assert guard.finished is True
    # Once finished, the guard must not release anything more (the caller is expected to stop
    # consuming the stream, but a stray extra feed() must still be inert).
    assert guard.feed("more text") == ""


def test_references_block_is_case_insensitive():
    guard = ArcanaReferenceGuard()
    text = "Done.\n---\nREFERENCES:\nsomething"
    released = guard.feed(text)
    assert released == "Done."
    assert guard.finished is True


def test_references_block_split_across_many_small_deltas():
    guard = ArcanaReferenceGuard()
    text = "The answer is 42.\n---\nReferences:\n[RREF1] some_source.pdf p.1 (0.9)"
    released = _feed_all(guard, text)
    assert released == "The answer is 42."
    assert guard.finished is True


def test_plain_markdown_rule_is_not_mistaken_for_a_references_block():
    # A "---" divider that ISN'T followed by "References:" is ordinary markdown, not the marker —
    # it must reach the caller untouched, not get eaten.
    guard = ArcanaReferenceGuard()
    text = "Section one.\n---\nSection two starts here, no references at all."
    out = guard.feed(text) + (guard.flush() or "")
    assert out == text
    assert guard.finished is False


def test_recovers_after_a_failed_marker_attempt_and_still_finds_a_later_real_one():
    # "-- " (two dashes) looks like the start of a marker but isn't (needs 3+) — that failed
    # attempt's text must still reach the caller, and a genuine marker later in the same stream
    # must still be found and filtered.
    guard = ArcanaReferenceGuard()
    text = "Start.\n-- not enough dashes.\n---\nReferences:\nSource"
    released = guard.feed(text)
    assert released == "Start.\n-- not enough dashes."
    assert guard.finished is True


def test_flush_falls_back_to_plain_text_when_a_hanging_attempt_never_resolves():
    # Stream ends exactly on "\n---", too early to tell whether "References:" would have
    # followed — flush() must not silently swallow it, since it was never actually confirmed.
    guard = ArcanaReferenceGuard()
    released = guard.feed("Hello.\n---")
    assert released == "Hello."
    assert guard.finished is False
    assert guard.flush() == "\n---"
