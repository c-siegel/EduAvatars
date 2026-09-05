"""
Sentence Chunker For Streamed Replies

Splits an incrementally-arriving LLM (large language model) reply into speakable chunks at
sentence boundaries, so each chunk can be sent to TTS (text-to-speech) as soon as it is ready
instead of waiting for the whole reply. Used by the streaming public chat endpoint (see
app/api/public_chat.py).

How to use:
    from app.services.text_chunk_service import SentenceChunker, chunk_text

    chunker = SentenceChunker()
    for delta in llm_token_stream:
        for chunk in chunker.feed(delta):
            synthesize_speech(chunk, ...)
    tail = chunker.flush()
    if tail:
        synthesize_speech(tail, ...)

    # Or, for an already-complete string:
    chunks = chunk_text(full_reply)
"""

_SENTENCE_MARKS = ".?!:…"
_MIN_CHUNK_CHARS = 80  # below this, keep accumulating past the boundary
_FIRST_CHUNK_MIN_CHARS = 25  # first chunk starts audio — let it be short
_MAX_CHUNK_CHARS = 300  # forced flush; a rambling sentence must not stall audio
# Words that end in "." without ending a sentence. Any token of <= 2 chars before the dot is also
# treated as an abbreviation ("z.", "B.", "u.", "S.").
_ABBREVIATIONS = {"bzw", "ca", "dr", "prof", "usw", "etc", "ggf", "vgl", "abb", "bspw", "inkl", "evtl"}


def _is_abbreviation(buf: str, dot_index: int) -> bool:
    """Whether the alphanumeric token right before buf[dot_index] ('.') is an abbreviation."""
    start = dot_index
    while start > 0 and buf[start - 1].isalnum():
        start -= 1
    word = buf[start:dot_index]
    if not word:
        return False
    return len(word) <= 2 or word.lower() in _ABBREVIATIONS


def _last_whitespace_before(buf: str, limit: int) -> int:
    """Index of the last whitespace character in buf[:limit], or -1 if there is none."""
    idx = -1
    for i in range(limit):
        if buf[i].isspace():
            idx = i
    return idx


class SentenceChunker:
    """Accumulates streamed text and yields speakable chunks at sentence boundaries."""

    def __init__(self) -> None:
        self._buf = ""
        # How far into _buf scanning has already progressed with no usable boundary found — avoids
        # re-scanning the same prefix on every feed() call.
        self._scan_pos = 0
        self._chunks_emitted = 0

    def feed(self, delta: str) -> list[str]:
        """Append a token delta; return any chunks that are now ready for TTS."""
        self._buf += delta
        chunks: list[str] = []
        while True:
            boundary = self._scan_for_boundary()
            if boundary is None:
                break
            end = boundary + 1
            candidate = self._buf[:end]
            min_required = _FIRST_CHUNK_MIN_CHARS if self._chunks_emitted == 0 else _MIN_CHUNK_CHARS
            if len(candidate.strip()) >= min_required:
                self._emit(chunks, candidate)
                self._buf = self._buf[end:]
                self._scan_pos = 0
            else:
                # Too short to stand alone — keep the boundary and merge it with whatever sentence
                # comes next, rather than flushing a choppy one-word chunk.
                self._scan_pos = end
        self._force_flush_if_too_long(chunks)
        return chunks

    def flush(self) -> str | None:
        """End of stream: return whatever is left, or None if only whitespace."""
        remainder = self._buf.strip()
        self._buf = ""
        self._scan_pos = 0
        return remainder or None

    def _emit(self, chunks: list[str], candidate: str) -> None:
        stripped = candidate.strip()
        if stripped:
            chunks.append(stripped)
            self._chunks_emitted += 1

    def _force_flush_if_too_long(self, chunks: list[str]) -> None:
        while len(self._buf) >= _MAX_CHUNK_CHARS:
            cut = _last_whitespace_before(self._buf, _MAX_CHUNK_CHARS)
            if cut <= 0:
                cut = _MAX_CHUNK_CHARS
            self._emit(chunks, self._buf[:cut])
            self._buf = self._buf[cut:]
            self._scan_pos = 0

    def _scan_for_boundary(self) -> int | None:
        """Find the next confirmed sentence boundary at or after _scan_pos, or None if the
        buffer needs more input before a decision can be made (see the lookahead check below)."""
        buf = self._buf
        n = len(buf)
        i = self._scan_pos
        while i < n:
            ch = buf[i]
            if ch == "\n":
                self._scan_pos = i
                return i
            if ch in _SENTENCE_MARKS:
                if i + 1 >= n:
                    # The scanner never decides on the final character of the buffer — a lone
                    # trailing mark might still turn out to be "3." with more digits coming.
                    self._scan_pos = i
                    return None
                if not buf[i + 1].isspace():
                    i += 1
                    continue
                if ch == "." and _is_abbreviation(buf, i):
                    i += 1
                    continue
                self._scan_pos = i
                return i
            i += 1
        self._scan_pos = i
        return None


def chunk_text(text: str) -> list[str]:
    """Split an already-complete reply — convenience wrapper over feed() + flush()."""
    chunker = SentenceChunker()
    chunks = chunker.feed(text)
    tail = chunker.flush()
    if tail:
        chunks.append(tail)
    return chunks
