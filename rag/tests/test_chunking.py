from app.chunking import chunk_sections
from app.parsing.types import Section
from app.search import fts_query


def test_short_sections_stay_whole_and_keep_page_and_heading():
    chunks = chunk_sections([Section("Eins.", page=1, heading="A"), Section("Zwei.", page=2)])
    assert [(c.text, c.page, c.heading, c.ordinal) for c in chunks] == [("Eins.", 1, "A", 0), ("Zwei.", 2, None, 1)]
    assert chunks[0].embedding_text() == "A\nEins."


def test_long_text_is_packed_with_overlap_and_size_bound():
    paragraphs = [f"Absatz {i} " + "wort " * 40 for i in range(20)]
    chunks = chunk_sections([Section("\n\n".join(paragraphs), page=4)], size=600, overlap=100)
    assert len(chunks) > 3
    assert all(c.page == 4 for c in chunks)
    # Generous bound: a chunk is at most size plus the carried-over overlap.
    assert all(len(c.text) <= 600 + 100 for c in chunks)
    # The overlap repeats the end of one chunk at the start of the next.
    assert chunks[0].text[-50:].split()[-1] in chunks[1].text[:150]


def test_overlong_paragraph_is_split_at_sentences():
    paragraph = " ".join(f"Satz Nummer {i} endet hier." for i in range(100))
    chunks = chunk_sections([Section(paragraph)], size=300, overlap=0)
    assert all(len(c.text) <= 300 for c in chunks)
    assert "".join(c.text.replace(" ", "") for c in chunks) == paragraph.replace(" ", "")


def test_fts_query_quotes_words_and_drops_stopwords():
    assert fts_query('Was ist "Photosynthese" OR NEAR(x)?') == '"photosynthese" OR "near"'
    assert fts_query("Hallo, wie geht es dir?") == '"geht"'
    assert fts_query("?!") is None
