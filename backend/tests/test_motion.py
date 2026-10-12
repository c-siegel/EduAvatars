"""Tests for the avatar's gesture markers (app/features/chat/motion.py): parsing "::name::" out of
replies, keeping markers whole across streamed chunks, and that TTS, the visitor and the saved
transcript each get what they should — clean text, the gesture names, and the names with their
positions."""

import json
from pathlib import Path

import pytest
from conftest import create_project, parse_sse

from app.features.chat.motion import MOTION_PROMPT, MOTIONS, MotionMark, extract_motions
from app.features.chat.streaming import SentenceChunker, chunk_text
from app.features.projects.export import parse_project_yaml

FRONTEND_MOTIONS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "vendor" / "motion-engine" / "motions.json"

STREAMED_REPLY = (
    "::wave_right:: Hallo, schön dass du da bist! Das ist eine richtig gute Frage zu Brüchen, "
    "::thinking_face:: lass mich kurz überlegen. Genau so geht es. ::thumbup_right::"
)
CLEAN_REPLY = (
    "Hallo, schön dass du da bist! Das ist eine richtig gute Frage zu Brüchen, "
    "lass mich kurz überlegen. Genau so geht es."
)


# --- Parsing ---


def test_extract_motions_removes_markers_and_records_positions() -> None:
    text, marks = extract_motions("::wave_right:: Hallo! Ja ::nod_yes:: genau so. ::applause::")
    assert text == "Hallo! Ja genau so."
    assert marks == [MotionMark("wave_right", 0), MotionMark("nod_yes", 10), MotionMark("applause", len(text))]
    assert text[10:].startswith("genau")


def test_extract_motions_tolerates_spaces_and_case() -> None:
    assert extract_motions("Gut :: Nod_Yes :: gemacht") == ("Gut gemacht", [MotionMark("nod_yes", 4)])


def test_unknown_markers_and_code_stay_in_the_text() -> None:
    # An invented gesture stays visible (that's how a teacher spots it), and C++ scope operators
    # are not gestures at all.
    for text in ("Lass uns ::dance:: tanzen", "Nutze std::vector::size() dafür."):
        assert extract_motions(text) == (text, [])


def test_text_without_markers_is_unchanged() -> None:
    assert extract_motions("Einfach nur Text.") == ("Einfach nur Text.", [])


# --- Chunking ---


def test_chunker_keeps_markers_whole_and_does_not_split_at_them() -> None:
    chunker = SentenceChunker()
    chunks: list[str] = []
    # Character by character: the worst case for a marker arriving in pieces.
    for ch in STREAMED_REPLY:
        chunks.extend(chunker.feed(ch))
    tail = chunker.flush()
    if tail:
        chunks.append(tail)
    assert chunks == chunk_text(STREAMED_REPLY)
    for chunk in chunks:
        assert chunk.count("::") % 2 == 0, chunk
    # The closing "::" followed by a space is no sentence end.
    sentence = "Schau dir diesen Abschnitt genau an ::point:: das ist der wichtigste Teil."
    assert chunk_text(sentence) == [sentence]


def test_backend_and_frontend_offer_the_same_gestures() -> None:
    if not FRONTEND_MOTIONS.exists():
        pytest.skip("frontend not checked out next to the backend")
    assert set(json.loads(FRONTEND_MOTIONS.read_text(encoding="utf-8"))) == set(MOTIONS)


# --- Chat routes ---


def test_stream_strips_markers_sends_motions_and_saves_their_positions(client, anon, chat_project, fake_ai):
    fake_ai.llm_reply = STREAMED_REPLY
    slug = chat_project["shareSlug"]
    anon.get(f"/public/{slug}")

    events = parse_sse(anon.post(f"/public/{slug}/messages/stream", json={"message": "Wie geht das?"}).text)

    assert fake_ai.completion_calls[-1]["messages"][0]["content"].endswith(MOTION_PROMPT)
    chunks = [data for name, data in events if name == "chunk"]
    assert [c["motions"] for c in chunks] == [["wave_right"], ["thinking_face"], ["thumbup_right"]]
    assert all("::" not in c["text"] for c in chunks)
    assert all("::" not in call["input"] for call in fake_ai.speech_calls)
    assert events[-1][1]["reply"] == CLEAN_REPLY

    conversation_id = client.get("/conversations/ids").json()[0]
    reply = client.get(f"/conversations/{conversation_id}").json()["messages"][1]
    assert reply["content"] == CLEAN_REPLY
    assert reply["motions"] == [
        {"name": "wave_right", "offset": 0},
        {"name": "thinking_face", "offset": CLEAN_REPLY.index("lass")},
        {"name": "thumbup_right", "offset": len(CLEAN_REPLY)},
    ]
    csv = client.post("/conversations/export", json={"conversationIds": [conversation_id]}).text
    assert "Zeitpunkt,Avatar,Schüler:in,Gesten" in csv
    assert f"wave_right@0; thinking_face@{CLEAN_REPLY.index('lass')}; thumbup_right@{len(CLEAN_REPLY)}" in csv


def test_plain_reply_returns_motions_and_speaks_clean_text(anon, chat_project, fake_ai):
    fake_ai.llm_reply = "::nod_yes:: Richtig, das Ergebnis ist vier."
    slug = chat_project["shareSlug"]
    anon.get(f"/public/{slug}")

    body = anon.post(f"/public/{slug}/messages", json={"message": "2+2?"}).json()

    assert body["reply"] == "Richtig, das Ergebnis ist vier."
    assert body["motions"] == ["nod_yes"]
    assert fake_ai.speech_calls[-1]["input"] == "Richtig, das Ergebnis ist vier."


def test_motion_off_or_chat_only_sends_no_instructions_and_keeps_text(client, anon, chat_project, fake_ai):
    fake_ai.llm_reply = "::nod_yes:: Richtig."
    slug = chat_project["shareSlug"]
    anon.get(f"/public/{slug}")
    for change in ({"motionEnabled": False}, {"motionEnabled": True, "chatLayout": "chat_only"}):
        client.put(f"/projects/{chat_project['id']}", json=change)

        body = anon.post(f"/public/{slug}/messages", json={"message": "2+2?"}).json()

        assert MOTION_PROMPT not in fake_ai.completion_calls[-1]["messages"][0]["content"]
        assert body["motions"] == []
        assert body["reply"] == "::nod_yes:: Richtig."


def test_motion_setting_defaults_on_and_reaches_the_public_page(client, anon, teacher):
    project = create_project(client)
    assert project["motionEnabled"] is True
    updated = client.put(f"/projects/{project['id']}", json={"motionEnabled": False}).json()
    assert updated["motionEnabled"] is False

    client.put(f"/projects/{project['id']}", json={"motionEnabled": True})
    slug = client.put(f"/projects/{project['id']}/publication").json()["shareSlug"]
    assert anon.get(f"/public/{slug}").json()["motionEnabled"] is True


def test_exports_without_the_setting_import_with_motion_on() -> None:
    assert parse_project_yaml("eduavatars_export: 2\nproject:\n  title: x\n").motion_enabled is True
    assert parse_project_yaml("eduavatars_export: 2\nproject:\n  title: x\n  motion_enabled: false\n").motion_enabled is False
