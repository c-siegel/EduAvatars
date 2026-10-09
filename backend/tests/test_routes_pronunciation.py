"""Route tests for the pronunciation word list (/pronunciation): entries stay private to their owner,
validation and limits hold, and the text import/export round-trips."""

from sqlmodel import Session, select

from app.features.pronunciation import service
from app.features.pronunciation.models import PronunciationEntry
from conftest import LLM_REPLY, login_as, make_user, new_client


def add(client, term: str, spoken: str = "x", **extra):
    return client.post("/pronunciation/entries", json={"language": "de", "term": term, "spoken": spoken, **extra})


def test_create_list_update_delete(client, teacher):
    created = add(client, "pH", "p H", caseSensitive=True)
    assert created.status_code == 201, created.text
    entry = created.json()
    assert entry["term"] == "pH" and entry["caseSensitive"] is True and entry["wholeWord"] is True

    assert [e["term"] for e in client.get("/pronunciation/entries", params={"language": "de"}).json()] == ["pH"]
    assert client.get("/pronunciation/entries", params={"language": "en"}).json() == []

    updated = client.put(f"/pronunciation/entries/{entry['id']}", json={"term": "pH", "spoken": "p H Wert"})
    assert updated.status_code == 200
    assert updated.json()["spoken"] == "p H Wert"

    assert client.delete(f"/pronunciation/entries/{entry['id']}").status_code == 204
    assert client.get("/pronunciation/entries").json() == []


def test_requires_login(client):
    assert client.get("/pronunciation/entries").status_code == 401


def test_entries_are_private_to_their_owner(client, teacher, engine):
    entry = add(client, "pH", "p H").json()
    other = login_as(new_client(), make_user(engine, email="other@example.com"))

    assert other.get("/pronunciation/entries").json() == []
    assert other.put(f"/pronunciation/entries/{entry['id']}", json={"term": "x", "spoken": "y"}).status_code == 404
    assert other.delete(f"/pronunciation/entries/{entry['id']}").status_code == 404
    assert "pH" not in other.get("/pronunciation/export", params={"language": "de"}).text
    # The other teacher may still use the same term for themselves.
    assert add(other, "pH", "Pe Ha").status_code == 201


def test_duplicate_term_is_a_409(client, teacher):
    add(client, "pH")
    response = add(client, "pH")
    assert response.status_code == 409
    assert response.json()["detail"] == "PRONUNCIATION_ENTRY_DUPLICATE"
    # Same term in the other language is a different list.
    assert client.post("/pronunciation/entries", json={"language": "en", "term": "pH", "spoken": "p h"}).status_code == 201


def test_renaming_onto_an_existing_term_is_a_409(client, teacher):
    add(client, "pH")
    second = add(client, "GPT").json()
    assert client.put(f"/pronunciation/entries/{second['id']}", json={"term": "pH", "spoken": "x"}).status_code == 409


def test_spell_out_generates_the_spoken_form(client, teacher):
    response = add(client, "GPT-4", "", spellOut=True)
    assert response.status_code == 201
    assert response.json()["spoken"] == "G P T 4"


def test_validation_errors_come_back_as_codes(client, teacher):
    assert "PRONUNCIATION_TERM_INVALID" in add(client, "   ").text
    assert "PRONUNCIATION_TERM_INVALID" in add(client, "{number}", "{number} Meter").text
    assert "PRONUNCIATION_SPOKEN_INVALID" in add(client, "pH", "  ").text
    assert "PRONUNCIATION_SPOKEN_NUMBER_MISMATCH" in add(client, "m", "{number} Meter").text
    assert "PRONUNCIATION_SPELL_OUT_WITH_NUMBER" in add(client, "{number} GB", "", spellOut=True).text


def test_whitespace_in_a_term_is_collapsed(client, teacher):
    assert add(client, "  z.   B. ", "zum Beispiel").json()["term"] == "z. B."


def test_entry_limit(client, teacher, monkeypatch):
    monkeypatch.setattr(service, "MAX_ENTRIES_PER_LANGUAGE", 1)
    add(client, "a")
    response = add(client, "b")
    assert response.status_code == 400
    assert response.json()["detail"] == "PRONUNCIATION_LIMIT_REACHED"


def import_text(client, text: str, **extra):
    response = client.post("/pronunciation/import", json={"language": "de", "text": text, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_import_accepts_all_line_formats(client, teacher):
    result = import_text(
        client,
        "\n".join(
            [
                "# Kommentar",
                "pH = p H",
                "E = mc² = E gleich m c Quadrat",
                "km/h;Kilometer pro Stunde;1;1",
                "kg\tKilogramm",
                "GPT = !spell",
                "",
            ]
        ),
    )
    assert result == {"added": 5, "updated": 0, "skipped": 0, "errors": []}
    entries = {e["term"]: e for e in client.get("/pronunciation/entries").json()}
    assert entries["E = mc²"]["spoken"] == "E gleich m c Quadrat"
    assert entries["km/h"]["caseSensitive"] is True
    assert entries["GPT"]["spoken"] == "G P T"


def test_import_reports_bad_lines_and_imports_the_rest(client, teacher):
    result = import_text(client, "pH = p H\nnur ein Wort\nkg;Kilogramm;vielleicht")
    assert result["added"] == 1
    assert [(e["line"], e["error"]) for e in result["errors"]] == [
        (2, "PRONUNCIATION_IMPORT_LINE_INVALID"),
        (3, "PRONUNCIATION_IMPORT_FLAG_INVALID"),
    ]


def test_import_skips_or_overwrites_existing_terms(client, teacher):
    add(client, "pH", "alt")
    assert import_text(client, "pH = neu")["skipped"] == 1
    assert client.get("/pronunciation/entries").json()[0]["spoken"] == "alt"
    assert import_text(client, "pH = neu", overwrite=True)["updated"] == 1
    assert client.get("/pronunciation/entries").json()[0]["spoken"] == "neu"


def test_import_dry_run_saves_nothing(client, teacher):
    add(client, "pH", "alt")
    result = import_text(client, "pH = neu\nkg = Kilogramm", overwrite=True, dryRun=True)
    assert (result["added"], result["updated"]) == (1, 1)
    entries = client.get("/pronunciation/entries").json()
    assert [(e["term"], e["spoken"]) for e in entries] == [("pH", "alt")]


def test_import_over_the_limit_imports_nothing(client, teacher, monkeypatch):
    monkeypatch.setattr(service, "MAX_ENTRIES_PER_LANGUAGE", 1)
    response = client.post("/pronunciation/import", json={"language": "de", "text": "a = b\nc = d"})
    assert response.status_code == 400
    assert client.get("/pronunciation/entries").json() == []


def test_export_round_trips_and_guards_against_formulas(client, teacher):
    add(client, "=mc²", "gleich m c Quadrat", wholeWord=False)
    add(client, "pH", "p H", caseSensitive=True)
    response = client.get("/pronunciation/export", params={"language": "de"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    text = response.content.decode("utf-8")
    assert "'=mc²" in text  # opened in a spreadsheet, the term stays plain text

    for entry in client.get("/pronunciation/entries").json():
        client.delete(f"/pronunciation/entries/{entry['id']}")
    assert import_text(client, text)["added"] == 2
    entries = {e["term"]: e for e in client.get("/pronunciation/entries").json()}
    assert entries["=mc²"]["wholeWord"] is False
    assert entries["pH"]["caseSensitive"] is True


def test_deleting_the_account_deletes_the_word_list(client, teacher, engine):
    add(client, "pH")
    response = client.request("DELETE", "/me", json={"password": "correct-horse-1"})
    assert response.status_code in (200, 204), response.text
    with Session(engine) as session:
        assert session.exec(select(PronunciationEntry)).all() == []


def test_public_chat_speaks_with_the_owners_word_list(client, anon, chat_project, fake_ai, engine):
    add(client, "Tutor", "Lehrer")
    # Neither another teacher's list nor the owner's English list may apply to this German project.
    other = login_as(new_client(), make_user(engine, email="other@example.com"))
    add(other, "Antwort", "FALSCH")
    client.post("/pronunciation/entries", json={"language": "en", "term": "Sätze", "spoken": "FALSCH"})
    slug = chat_project["shareSlug"]
    anon.get(f"/public/{slug}")

    response = anon.post(f"/public/{slug}/messages", json={"message": "Hallo"})

    assert response.json()["reply"] == LLM_REPLY  # the displayed reply keeps the original text
    spoken = fake_ai.speech_calls[-1]["input"]
    assert "Lehrer" in spoken and "Tutor" not in spoken
    assert "FALSCH" not in spoken


def test_streamed_chat_speaks_with_the_owners_word_list(client, anon, chat_project, fake_ai):
    add(client, "Tutor", "Lehrer")
    slug = chat_project["shareSlug"]
    anon.get(f"/public/{slug}")

    anon.post(f"/public/{slug}/messages/stream", json={"message": "Hallo"})

    spoken = " ".join(call["input"] for call in fake_ai.speech_calls)
    assert "Lehrer" in spoken and "Tutor" not in spoken


def test_an_edit_applies_to_the_next_reply(client, anon, chat_project, fake_ai):
    entry = add(client, "Tutor", "Lehrer").json()
    slug = chat_project["shareSlug"]
    anon.get(f"/public/{slug}")
    anon.post(f"/public/{slug}/messages", json={"message": "Hallo"})

    client.put(f"/pronunciation/entries/{entry['id']}", json={"term": "Tutor", "spoken": "Lehrerin"})
    anon.post(f"/public/{slug}/messages", json={"message": "Hallo"})

    assert "Lehrerin" in fake_ai.speech_calls[-1]["input"]
