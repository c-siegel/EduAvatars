"""Tests for SentenceChunker/chunk_text (app/services/text_chunk_service.py) — a pure, dependency-
free module, so these need no app settings or DB and are safe/cheap to run anywhere."""

from app.services.text_chunk_service import SentenceChunker, chunk_text


def test_splits_on_sentence_boundary_once_both_sides_are_long_enough():
    first = "This is the first sentence right here."  # 39 chars, clears the 25-char first-chunk minimum
    second = (
        "This is a considerably longer second sentence that definitely exceeds the "
        "eighty character minimum threshold for chunk emission."
    )
    assert len(second) >= 80

    assert chunk_text(f"{first} {second}") == [first, second]


def test_short_sentence_merges_with_the_next_one_instead_of_splitting():
    # Each fragment alone is well under the (first-chunk) 25-char minimum, so the boundary after
    # "Hi." must be skipped and merged into one chunk together with what follows.
    text = "Hi. Ok."
    assert chunk_text(text) == ["Hi. Ok."]


def test_known_abbreviation_does_not_end_a_sentence():
    # "usw." (et cetera) is in the fixed abbreviation list — the "." right after it must not be
    # treated as a sentence boundary, even though a real sentence-ending "." follows later.
    text = (
        "Wir kauften Brot, Milch, Butter usw. dann gingen wir nach Hause und redeten "
        "noch eine ganze Weile über vergangene Zeiten."
    )
    assert chunk_text(text) == [text]


def test_short_token_before_a_dot_is_treated_as_an_abbreviation():
    # Any token of <= 2 chars right before "." counts as an abbreviation regardless of the fixed
    # list (e.g. "ca." for "circa") — same rule, different code path than the named-list case above.
    text = "Er kam ca. um acht Uhr abends nach Hause und aß noch etwas bevor er schlafen ging total müde."
    assert chunk_text(text) == [text]


def test_forced_flush_on_a_very_long_run_with_no_sentence_marks():
    text = "word " * 80  # 400 chars, no '.', '?', '!', ':' or '…' anywhere
    chunks = chunk_text(text)

    assert len(chunks) >= 2
    assert all(len(c) <= 300 for c in chunks)
    # No content lost or duplicated across the forced cut, modulo whitespace placement.
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_newline_is_a_boundary_without_abbreviation_checking():
    # Unlike '.', '?', '!', ':', '…', a newline is never subject to the abbreviation check — but
    # it's still a "boundary candidate" subject to the same first-chunk minimum-length merge as
    # any other mark, so the first line here has to clear 25 chars on its own to split at all.
    first = "This first line is intentionally long enough to stand alone."
    chunks = chunk_text(f"{first}\nShort second line")
    assert chunks == [first, "Short second line"]


def test_short_first_line_merges_across_a_newline_too():
    chunks = chunk_text("Hi\nthere, this continues right onto the next line without a real break.")
    assert chunks == ["Hi\nthere, this continues right onto the next line without a real break."]


def test_flush_returns_none_for_whitespace_only_remainder():
    chunker = SentenceChunker()
    chunker.feed("   \n  ")
    assert chunker.flush() is None


def test_flush_returns_stripped_remainder():
    chunker = SentenceChunker()
    chunker.feed("no sentence mark here")
    assert chunker.flush() == "no sentence mark here"


def test_streaming_one_character_at_a_time_matches_single_shot_result():
    first = "This is the first sentence right here."
    second = (
        "This is a considerably longer second sentence that definitely exceeds the "
        "eighty character minimum threshold for chunk emission."
    )
    text = f"{first} {second}"

    chunker = SentenceChunker()
    streamed: list[str] = []
    for ch in text:
        streamed.extend(chunker.feed(ch))
    tail = chunker.flush()
    if tail:
        streamed.append(tail)

    assert streamed == chunk_text(text)
