import time

from app.parsing.header import MAX_HEADER_CHARS, split_header
from app.parsing.sandbox import parse_in_sandbox
from app.schemas import DocumentLimits

ARCANA = '''---
title: "Kannst DU den Klimawandel stoppen?"
citation: "Kurzgesagt (n.d.). Kannst DU den Klimawandel stoppen?."
creator: Kurzgesagt – In a Nutshell (deutschsprachiger Kanal "Dinge Erklärt – Kurzgesagt")
source-path: "Downloads/video-transcript.md"
ingested: 2026-10-06
project: climate-lab
rag-corpus: true
language: de
sha256-prefix: a68d4b1c5dd1
content_type: Video-Transkript
source_file: video-transcript.md
scope: optional-supplementary
related_missions: [8]
usage_priority: secondary
source-type: transcript
compiled: true
---
# Einleitung
Der Klimawandel ist menschengemacht.
'''


def test_the_arcana_header_is_split_off_and_read():
    fields, body = split_header(ARCANA)
    assert fields["title"] == "Kannst DU den Klimawandel stoppen?"
    assert fields["citation"] == "Kurzgesagt (n.d.). Kannst DU den Klimawandel stoppen?."
    assert fields["creator"].startswith("Kurzgesagt – In a Nutshell (deutschsprachiger Kanal")
    assert fields["usage_priority"] == "secondary"
    assert fields["related_missions"] == ["8"]
    assert fields["content_type"] == "Video-Transkript"
    assert body.startswith("# Einleitung")


def test_markdown_upload_indexes_without_the_header():
    result = parse_in_sandbox("md", ARCANA.encode(), DocumentLimits())
    assert result.metadata["title"] == "Kannst DU den Klimawandel stoppen?"
    text = " ".join(s.text for s in result.sections)
    assert "sha256-prefix" not in text and "usage_priority" not in text
    assert [(s.heading, s.text) for s in result.sections] == [("Einleitung", "Der Klimawandel ist menschengemacht.")]


def test_text_files_get_the_same_treatment_with_bom_and_crlf():
    data = "\ufeff---\r\ntitle: Arbeitsblatt 3\r\n---\r\nAufgabe 1: Beschreibe die Zelle.".encode()
    result = parse_in_sandbox("txt", data, DocumentLimits())
    assert result.metadata == {"title": "Arbeitsblatt 3"}
    assert result.sections[0].text == "Aufgabe 1: Beschreibe die Zelle."


def test_value_forms():
    fields, _ = split_header(
        "---\n"
        "a: 'it''s'\n"
        'b: "say \\"hi\\""\n'
        "c: plain # a comment\n"
        "d: [x, \"y, z\"]\n"
        "e:\n  - eins\n  - zwei\n"
        "f: |\n  zeile eins\n  zeile zwei\n"
        "# comment line\n"
        "nested:\n  inner: skipped\n"
        "g:\n"
        "---\nBody"
    )
    assert fields == {
        "a": "it's",
        "b": 'say "hi"',
        "c": "plain",
        "d": ["x", "y, z"],
        "e": ["eins", "zwei"],
        "f": "zeile eins zeile zwei",
    }


def test_not_a_header_stays_content():
    cases = [
        "---\nEin Absatz nach einer Linie.\n---\nMehr Text",  # horizontal rules around a paragraph
        "---\ntitle: offen, aber nie geschlossen\nText",  # no closing line
        "Text\n---\ntitle: x\n---\n",  # not at the very top
        "----\ntitle: x\n---\n",  # not exactly three dashes
        "---\nhttps://example.org\n---\n",  # a line that isn't metadata
        "---\n\n---\nText",  # empty
    ]
    for text in cases:
        assert split_header(text) == ({}, text), text


def test_an_oversized_header_stays_content():
    text = "---\n" + "".join(f"k{i}: {'x' * 50}\n" for i in range(MAX_HEADER_CHARS // 50)) + "---\nBody"
    assert split_header(text) == ({}, text)


def test_caps_and_invisible_characters():
    many = "".join(f"k{i}: v\n" for i in range(60))
    fields, _ = split_header(f"---\n{many}long: {'y' * 900}\nbidi: a\u202eb\u200bc\n---\n")
    assert len(fields) == 40
    fields, _ = split_header(f"---\nlong: {'y' * 900}\nbidi: a\u202eb\u200bc\n---\n")
    assert len(fields["long"]) == 500
    assert fields["bidi"] == "abc"


def test_pathological_headers_parse_quickly():
    start = time.perf_counter()
    split_header("---\n" + "a" * 8000 + "\n---\n")
    split_header("---\n" + ("k: " + " " * 7000 + "#") + "\n---\n")
    split_header("---\nk: [" + "\"," * 3000 + "]\n---\n")
    assert time.perf_counter() - start < 0.5
