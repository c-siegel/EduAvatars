"""Quality evaluation (Ragas): test sets, drafted questions, runs through the real answer path,
and deletes that take runs along — with the knowledge and evaluation services faked at their HTTP
seams (tests/fake_rag.py, tests/fake_eval.py) and the LLM at litellm."""

import csv
import io
import json

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.features.chat.models import Conversation
from app.features.evaluation import eval_client, runner
from app.features.evaluation.models import EvalRun, EvalRunItem, EvalTestCase, EvalTestSet
from app.features.evaluation.service import mark_interrupted
from app.features.knowledge import rag_client
from app.features.site_settings.service import get_or_create_site_settings
from tests.conftest import LLM_REPLY, create_key, create_project, login_as, make_user
from tests.fake_eval import FakeEval
from tests.fake_rag import TOKEN, FakeRag

PDF = b"%PDF-1.7\nPhotosynthese wandelt Licht in chemische Energie um. Sie findet in den Chloroplasten statt."
ALL_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "factual_correctness"]


@pytest.fixture
def fake_rag(monkeypatch):
    fake = FakeRag()
    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_service_token", TOKEN)
    monkeypatch.setattr(rag_client, "_client", fake.client())
    monkeypatch.setattr(rag_client, "_capabilities_cache", None)
    return fake


@pytest.fixture
def fake_eval(monkeypatch, fake_rag):
    fake = FakeEval()
    monkeypatch.setattr(settings, "rag_evaluation_enabled", True)
    monkeypatch.setattr(eval_client, "_client", fake.client())
    # Runs execute right away, inside the request, instead of on the worker thread.
    monkeypatch.setattr(runner, "submit", runner.execute_run)
    return fake


@pytest.fixture
def setup(client, teacher, fake_ai, fake_eval):
    """A KB with one indexed document, a project answering from it, a judge key, a test set."""
    kb = client.post("/knowledge-bases", json={"name": "Biologie"}).json()
    response = client.post(
        f"/knowledge-bases/{kb['id']}/documents", files={"file": ("Skript.pdf", PDF)}, data={"consent": "true"}
    )
    assert response.status_code == 202, response.text
    llm_key = create_key(client)
    judge_key = create_key(client, modelId="gpt-4o", apiKey="sk-judge-secret-9876")
    project = create_project(
        client, llmApiKeyId=llm_key["id"], knowledgeMode="supplement", knowledgeBaseIds=[kb["id"]], saveConversations=True
    )
    test_set = client.post(f"/knowledge-bases/{kb['id']}/test-sets", json={"name": "Kapitel 1"}).json()
    return {"kb": kb, "project": project, "judge_key": judge_key, "test_set": test_set}


def _add(client, test_set_id, question="Was ist Photosynthese?", reference="Umwandlung von Licht in Energie."):
    response = client.post(f"/test-sets/{test_set_id}/cases", json={"question": question, "reference": reference})
    assert response.status_code == 201, response.text
    return response.json()


def _start(client, setup, **overrides):
    body = {
        "projectId": setup["project"]["id"],
        "testSetId": setup["test_set"]["id"],
        "judgeApiKeyId": setup["judge_key"]["id"],
        "metrics": ALL_METRICS,
        **overrides,
    }
    return client.post("/evaluation/runs", json=body)


def test_everything_is_off_without_evaluation_enabled(client, teacher, fake_rag):
    assert client.get("/providers/evaluation-status").json()["available"] is False
    response = client.get("/evaluation/runs")
    assert response.status_code == 404
    assert response.json() == {"detail": "EVALUATION_DISABLED"}


def test_status_reports_the_service_and_the_estimate_inputs(client, teacher, fake_eval):
    status = client.get("/providers/evaluation-status").json()
    assert status["available"] is True and status["reachable"] is True
    assert status["ragasVersion"] == "0.4.3"
    assert status["maxCasesPerRun"] == 50
    assert status["judgeCallsPerMetric"]["faithfulness"] == 2


def test_test_sets_and_questions(client, setup):
    test_set_id = setup["test_set"]["id"]
    case = _add(client, test_set_id)
    assert case["origin"] == "manual" and case["approved"] is True
    assert client.post(f"/test-sets/{test_set_id}/cases", json={"question": "  "}).json() == {
        "detail": "EVALUATION_QUESTION_REQUIRED"
    }

    updated = client.patch(f"/test-cases/{case['id']}", json={"reference": None, "question": "Wo findet sie statt?"})
    assert updated.json()["question"] == "Wo findet sie statt?" and updated.json()["reference"] is None

    listed = client.get(f"/knowledge-bases/{setup['kb']['id']}/test-sets").json()
    assert [(t["name"], t["caseCount"], t["approvedCount"]) for t in listed] == [("Kapitel 1", 1, 1)]
    renamed = client.patch(f"/test-sets/{test_set_id}", json={"name": "Kapitel 2", "language": "en"}).json()
    assert renamed["name"] == "Kapitel 2" and renamed["language"] == "en"

    assert client.delete(f"/test-cases/{case['id']}").status_code == 204
    assert client.get(f"/test-sets/{test_set_id}/cases").json() == []


def test_other_teachers_cant_see_or_touch_anything(client, setup, engine):
    case = _add(client, setup["test_set"]["id"])
    run = _start(client, setup).json()
    login_as(client, make_user(engine, email="other@example.com"))
    assert client.get(f"/test-sets/{setup['test_set']['id']}/cases").status_code == 404
    assert client.post(f"/knowledge-bases/{setup['kb']['id']}/test-sets", json={"name": "x"}).status_code == 404
    assert client.patch(f"/test-cases/{case['id']}", json={"approved": False}).status_code == 404
    assert client.get(f"/evaluation/runs/{run['id']}").status_code == 404
    assert client.delete(f"/evaluation/runs/{run['id']}").status_code == 404
    assert client.get("/evaluation/runs").json() == []
    assert client.get("/test-sets").json() == []
    # Their own key can't judge someone else's test set, and their project can't be someone else's.
    other_key = create_key(client)
    response = client.post(
        "/evaluation/runs",
        json={
            "projectId": setup["project"]["id"],
            "testSetId": setup["test_set"]["id"],
            "judgeApiKeyId": other_key["id"],
            "metrics": ["faithfulness"],
        },
    )
    assert response.status_code == 404


def test_csv_import_and_export_round_trip(client, setup):
    test_set_id = setup["test_set"]["id"]
    data = "﻿Frage;Referenz\nWas ist ATP?;Ein Energieträger.\n=HYPERLINK(1);-5 Grad\n;leer\n".encode("utf-8")
    response = client.post(f"/test-sets/{test_set_id}/cases/import", files={"file": ("fragen.csv", data)})
    assert response.json() == {"imported": 2, "skipped": 1}

    exported = client.get(f"/test-sets/{test_set_id}/cases/export")
    assert exported.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    # Formula-like cells are guarded for spreadsheet apps …
    assert rows == [
        ["question", "reference", "kind"],
        ["Was ist ATP?", "Ein Energieträger.", "topic"],
        ["'=HYPERLINK(1)", "'-5 Grad", "topic"],
    ]

    # … and the guard is undone on import, so the round trip is lossless.
    other = client.post(f"/knowledge-bases/{setup['kb']['id']}/test-sets", json={"name": "Kopie"}).json()
    client.post(f"/test-sets/{other['id']}/cases/import", files={"file": ("t.csv", exported.content)})
    questions = [c["question"] for c in client.get(f"/test-sets/{other['id']}/cases").json()]
    assert questions == ["Was ist ATP?", "=HYPERLINK(1)"]


def test_csv_without_a_question_column_is_refused(client, setup):
    response = client.post(
        f"/test-sets/{setup['test_set']['id']}/cases/import", files={"file": ("x.csv", b"name,value\na,b\n")}
    )
    assert response.json() == {"detail": "EVALUATION_CSV_INVALID"}


def test_drafted_questions_need_approval(client, setup, fake_eval):
    test_set_id = setup["test_set"]["id"]
    response = client.post(f"/test-sets/{test_set_id}/generate", json={"judgeApiKeyId": setup["judge_key"]["id"]})
    assert response.status_code == 201, response.text
    drafts = response.json()
    assert len(drafts) == 1 and drafts[0]["approved"] is False and drafts[0]["origin"] == "generated"

    sent = fake_eval.generate_calls[-1]
    assert sent["judge"] == {"model": "openai/gpt-4o", "api_key": "sk-judge-secret-9876"}
    assert sent["language"] == "de" and "Photosynthese" in sent["chunks"][0]["text"]

    # Unapproved drafts aren't used by runs.
    assert _start(client, setup).json() == {"detail": "EVALUATION_NO_CASES"}
    client.patch(f"/test-cases/{drafts[0]['id']}", json={"approved": True})
    assert _start(client, setup).status_code == 202

    client.post(f"/test-sets/{test_set_id}/generate", json={"judgeApiKeyId": setup["judge_key"]["id"]})
    assert client.delete(f"/test-sets/{test_set_id}/drafts").status_code == 204
    assert [c["approved"] for c in client.get(f"/test-sets/{test_set_id}/cases").json()] == [True]


def test_a_judge_that_fails_every_draft_is_reported(client, setup, fake_eval):
    fake_eval.fail_with = 502
    response = client.post(
        f"/test-sets/{setup['test_set']['id']}/generate", json={"judgeApiKeyId": setup["judge_key"]["id"]}
    )
    assert response.status_code == 502
    assert response.json() == {"detail": "EVALUATION_JUDGE_FAILED"}


def test_arcana_and_foreign_keys_cant_judge(client, setup):
    arcana = create_key(client, provider="gwdg_arcana", arcanaId="abc", modelId="meta-llama")
    tts = create_key(client, key_type="tts")
    for key_id in (arcana["id"], tts["id"], "no-such-key"):
        response = client.post(f"/test-sets/{setup['test_set']['id']}/generate", json={"judgeApiKeyId": key_id})
        assert response.json() == {"detail": "EVALUATION_JUDGE_KEY_INVALID"}, key_id


def test_a_run_answers_through_the_project_and_scores(client, setup, fake_ai, fake_eval, engine):
    _add(client, setup["test_set"]["id"])
    _add(client, setup["test_set"]["id"], question="Was ist Mitose?", reference=None)
    response = _start(client, setup)
    assert response.status_code == 202, response.text
    run = client.get(f"/evaluation/runs/{response.json()['id']}").json()

    assert run["status"] == "done", run
    assert (run["caseCount"], run["answeredCount"], run["scoredCount"]) == (2, 2, 2)
    assert run["config"]["projectTitle"] == "Mathe-Tutor"
    assert run["config"]["knowledgeMode"] == "supplement"
    assert run["config"]["judge"] == "OpenAI · gpt-4o"
    assert run["summary"]["metrics"]["faithfulness"] == {"mean": 0.8, "median": 0.8, "count": 2}
    # Context recall only applies to the question with a reference answer.
    assert run["summary"]["metrics"]["context_recall"]["count"] == 1

    first, second = run["items"]
    assert first["answer"] == LLM_REPLY
    assert first["contexts"][0]["filename"] == "Skript.pdf" and "Photosynthese" in first["contexts"][0]["text"]
    assert first["scores"]["faithfulness"] == {"value": 0.8, "error": None}
    assert second["scores"]["factual_correctness"] == {"value": None, "error": "NO_REFERENCE"}

    # The answer was given with the retrieved passages, like a student's turn …
    prompt = json.dumps(fake_ai.completion_calls[0]["messages"], ensure_ascii=False)
    assert "Photosynthese wandelt Licht" in prompt
    # … but without speech and without saving a conversation.
    assert fake_ai.speech_calls == []
    with Session(engine) as session:
        assert session.exec(select(Conversation)).all() == []

    sent = fake_eval.score_calls[0]
    assert sent["judge"]["api_key"] == "sk-judge-secret-9876"
    assert sent["embedding"]["mode"] == "local"
    assert sent["metrics"] == ALL_METRICS
    # The judge's key never comes back to the browser.
    assert "sk-judge-secret" not in json.dumps(run)
    assert "sk-judge-secret" not in client.get("/evaluation/runs").text


def test_runs_are_capped_and_one_at_a_time(client, setup, engine, monkeypatch):
    for i in range(3):
        _add(client, setup["test_set"]["id"], question=f"Frage {i}?")
    with Session(engine) as session:
        row = get_or_create_site_settings(session)
        row.rag_eval_max_cases_per_run = 2
        session.add(row)
        session.commit()
    assert _start(client, setup).json() == {"detail": "EVALUATION_TOO_MANY_CASES"}

    with Session(engine) as session:
        row = get_or_create_site_settings(session)
        row.rag_eval_max_cases_per_run = 50
        session.add(row)
        session.commit()
    monkeypatch.setattr(runner, "submit", lambda run_id: None)  # stays queued
    assert _start(client, setup).status_code == 202
    response = _start(client, setup)
    assert response.status_code == 409 and response.json() == {"detail": "EVALUATION_RUN_ACTIVE"}


def test_a_cancelled_run_stops(client, setup, fake_ai, monkeypatch):
    _add(client, setup["test_set"]["id"])
    monkeypatch.setattr(runner, "submit", lambda run_id: None)
    run = _start(client, setup).json()
    cancelled = client.post(f"/evaluation/runs/{run['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    runner.execute_run(run["id"])  # the worker picks it up late
    assert fake_ai.completion_calls == []
    assert client.post(f"/evaluation/runs/{run['id']}/cancel").json() == {"detail": "EVALUATION_RUN_NOT_ACTIVE"}


def test_judge_failures_fail_the_run_but_keep_the_answers(client, setup, fake_eval):
    _add(client, setup["test_set"]["id"])
    fake_eval.fail_with = 502
    run = client.get(f"/evaluation/runs/{_start(client, setup).json()['id']}").json()
    assert (run["status"], run["errorCode"]) == ("failed", "EVALUATION_JUDGE_FAILED")
    assert run["items"][0]["answer"] == LLM_REPLY


def test_an_unreachable_evaluation_service_fails_the_run(client, setup, fake_eval):
    _add(client, setup["test_set"]["id"])
    fake_eval.fail_with = 503
    run = client.get(f"/evaluation/runs/{_start(client, setup).json()['id']}").json()
    assert (run["status"], run["errorCode"]) == ("failed", "EVALUATION_SERVICE_UNAVAILABLE")


def test_llm_failures_are_per_question(client, setup, fake_ai):
    _add(client, setup["test_set"]["id"])
    fake_ai.llm_error = RuntimeError("provider down")
    run = client.get(f"/evaluation/runs/{_start(client, setup).json()['id']}").json()
    assert (run["status"], run["errorCode"]) == ("failed", "EVALUATION_LLM_FAILED")
    assert run["items"][0]["errorCode"] == "EVALUATION_LLM_FAILED"


def test_export_as_csv_and_json(client, setup):
    _add(client, setup["test_set"]["id"], question="=Photosynthese?")
    run_id = _start(client, setup).json()["id"]
    exported = client.get(f"/evaluation/runs/{run_id}/export").content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(exported)))
    assert rows[0][:5] == ["question", "kind", "reference", "answer", "faithfulness"]
    assert rows[1][0] == "'=Photosynthese?" and rows[1][1] == "topic" and rows[1][4] == "0.8"
    assert "Skript.pdf S. 1" in rows[1]

    as_json = client.get(f"/evaluation/runs/{run_id}/export?format=json").json()
    assert as_json["items"][0]["question"] == "=Photosynthese?"
    assert "sk-judge-secret" not in json.dumps(as_json)


def test_deleting_the_knowledge_base_takes_test_sets_and_runs_along(client, setup, engine):
    _add(client, setup["test_set"]["id"])
    _start(client, setup)
    assert client.delete(f"/knowledge-bases/{setup['kb']['id']}").status_code == 204
    with Session(engine) as session:
        for table in (EvalTestSet, EvalTestCase, EvalRun, EvalRunItem):
            assert session.exec(select(table)).all() == [], table


def test_deleting_the_project_deletes_its_runs(client, setup, engine):
    _add(client, setup["test_set"]["id"])
    _start(client, setup)
    assert client.delete(f"/projects/{setup['project']['id']}").status_code in (200, 204)
    with Session(engine) as session:
        assert session.exec(select(EvalRun)).all() == []
        assert session.exec(select(EvalRunItem)).all() == []
        assert len(session.exec(select(EvalTestCase)).all()) == 1


def test_deleting_the_judge_key_keeps_finished_runs_readable(client, setup):
    _add(client, setup["test_set"]["id"])
    run_id = _start(client, setup).json()["id"]
    assert client.delete(f"/api-keys/{setup['judge_key']['id']}").status_code in (200, 204)
    run = client.get(f"/evaluation/runs/{run_id}").json()
    assert run["status"] == "done" and run["config"]["judge"] == "OpenAI · gpt-4o"


def test_account_deletion_removes_all_evaluation_data(client, setup, engine):
    _add(client, setup["test_set"]["id"])
    _start(client, setup)
    response = client.request("DELETE", "/me", json={"password": "correct-horse-1"})
    assert response.status_code in (200, 204), response.text
    with Session(engine) as session:
        for table in (EvalTestSet, EvalTestCase, EvalRun, EvalRunItem):
            assert session.exec(select(table)).all() == [], table


def test_runs_in_progress_at_startup_are_marked_interrupted(client, setup, engine, monkeypatch):
    _add(client, setup["test_set"]["id"])
    monkeypatch.setattr(runner, "submit", lambda run_id: None)
    run_id = _start(client, setup).json()["id"]
    with Session(engine) as session:
        assert mark_interrupted(session) == 1
    run = client.get(f"/evaluation/runs/{run_id}").json()
    assert (run["status"], run["errorCode"]) == ("interrupted", "EVALUATION_INTERRUPTED")
    assert run["summary"] is not None


def test_admin_sets_the_question_cap_within_bounds(client, engine, fake_eval):
    login_as(client, make_user(engine, email="admin@example.com", is_admin=True))
    assert client.get("/admin/settings").json()["ragEvalMaxCasesPerRun"] == 50
    assert client.put("/admin/settings", json={"ragEvalMaxCasesPerRun": 501}).status_code == 422
    updated = client.put("/admin/settings", json={"ragEvalMaxCasesPerRun": 100}).json()
    assert updated["ragEvalMaxCasesPerRun"] == 100
    assert client.get("/providers/evaluation-status").json()["maxCasesPerRun"] == 100


def test_runs_with_passages_from_a_deleted_knowledge_base_are_deleted_too(client, setup, engine):
    # The project also uses a second KB; the test set belongs to the first.
    other = client.post("/knowledge-bases", json={"name": "Chemie"}).json()
    client.put(f"/projects/{setup['project']['id']}", json={"knowledgeBaseIds": [setup["kb"]["id"], other["id"]]})
    _add(client, setup["test_set"]["id"])
    _start(client, setup)
    assert client.delete(f"/knowledge-bases/{other['id']}").status_code == 204
    with Session(engine) as session:
        assert session.exec(select(EvalRun)).all() == []
        assert session.exec(select(EvalRunItem)).all() == []
        assert len(session.exec(select(EvalTestSet)).all()) == 1


def test_a_key_deleted_mid_run_isnt_charged_further(client, setup, fake_ai, monkeypatch):
    _add(client, setup["test_set"]["id"])
    monkeypatch.setattr(runner, "submit", lambda run_id: None)
    run_id = _start(client, setup).json()["id"]
    assert client.delete(f"/api-keys/{setup['judge_key']['id']}").status_code in (200, 204)
    runner.execute_run(run_id)
    run = client.get(f"/evaluation/runs/{run_id}").json()
    assert (run["status"], run["errorCode"]) == ("failed", "EVALUATION_KEY_DELETED")
    assert fake_ai.completion_calls == []


def test_one_draft_request_at_a_time(client, teacher, setup, monkeypatch):
    from app.features.evaluation import service

    # As if a draft request of this teacher were still running.
    monkeypatch.setattr(service, "_drafting_users", {teacher.id})
    response = client.post(
        f"/test-sets/{setup['test_set']['id']}/generate", json={"judgeApiKeyId": setup["judge_key"]["id"]}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "EVALUATION_GENERATION_ACTIVE"}


def _draft(client, setup, **body):
    return client.post(
        f"/test-sets/{setup['test_set']['id']}/generate", json={"judgeApiKeyId": setup["judge_key"]["id"], **body}
    )


def test_manual_and_csv_questions_default_to_topic_and_the_kind_can_change(client, setup):
    case = _add(client, setup["test_set"]["id"])
    assert case["kind"] == "topic"
    off = client.post(
        f"/test-sets/{setup['test_set']['id']}/cases", json={"question": "Wer gewinnt die WM?", "kind": "offtopic"}
    ).json()
    assert off["kind"] == "offtopic"
    assert client.patch(f"/test-cases/{case['id']}", json={"kind": "grounded"}).json()["kind"] == "grounded"
    assert client.patch(f"/test-cases/{case['id']}", json={"kind": "nonsense"}).status_code == 422


def test_csv_kind_column_is_read(client, setup):
    data = "question;kind\nA?;Material\nB?;außerhalb\nC?;\nD?;unbekannt\n".encode()
    client.post(f"/test-sets/{setup['test_set']['id']}/cases/import", files={"file": ("k.csv", data)})
    kinds = [c["kind"] for c in client.get(f"/test-sets/{setup['test_set']['id']}/cases").json()]
    assert kinds == ["grounded", "offtopic", "topic", "topic"]


def test_topic_questions_are_drafted_without_the_material(client, setup, fake_eval):
    _add(client, setup["test_set"]["id"], question="Was ist Photosynthese?")
    response = _draft(client, setup, kind="topic", projectId=setup["project"]["id"], objectives="  Zellatmung  ", size=3)
    assert response.status_code == 201, response.text
    drafts = response.json()
    assert [(d["kind"], d["approved"], d["origin"], d["reference"]) for d in drafts] == [("topic", False, "generated", None)] * 3

    sent = fake_eval.generate_calls[-1]
    assert sent["kind"] == "topic"
    assert "chunks" not in sent
    topic = sent["topic"]
    assert topic["project_title"] == "Mathe-Tutor"
    assert topic["document_titles"] == ["Skript"]
    assert topic["objectives"] == "Zellatmung"
    assert topic["existing_questions"] == ["Was ist Photosynthese?"]  # to avoid repeating it
    # The judge never sees the content, only titles and the teacher's own descriptions.
    assert "Photosynthese wandelt" not in json.dumps(sent)

    _draft(client, setup, kind="topic", projectId=setup["project"]["id"], size=1)
    assert len(fake_eval.generate_calls[-1]["topic"]["existing_questions"]) == 4


def test_offtopic_drafts_and_the_project_requirements(client, setup, fake_eval, engine):
    response = _draft(client, setup, kind="offtopic", projectId=setup["project"]["id"], size=2)
    assert [d["kind"] for d in response.json()] == ["offtopic", "offtopic"]
    assert _draft(client, setup, kind="topic").json() == {"detail": "EVALUATION_PROJECT_REQUIRED"}

    login_as(client, make_user(engine, email="other@example.com"))
    other_key = create_key(client)
    response = client.post(
        f"/test-sets/{setup['test_set']['id']}/generate",
        json={"judgeApiKeyId": other_key["id"], "kind": "topic", "projectId": setup["project"]["id"]},
    )
    assert response.status_code == 404


def test_a_run_scores_each_kind_and_summarizes_by_kind(client, setup, fake_eval):
    test_set_id = setup["test_set"]["id"]
    client.post(f"/test-sets/{test_set_id}/cases", json={"question": "Was ist Photosynthese?", "reference": "Licht zu Energie.", "kind": "grounded"})
    client.post(f"/test-sets/{test_set_id}/cases", json={"question": "Wie atmen Pflanzen?", "kind": "topic"})
    client.post(f"/test-sets/{test_set_id}/cases", json={"question": "Wer gewinnt die WM?", "kind": "offtopic"})
    run = client.get(f"/evaluation/runs/{_start(client, setup, metrics=['faithfulness', 'coverage', 'restraint']).json()['id']}").json()
    assert run["status"] == "done", run

    sent = fake_eval.score_calls[0]["items"]
    assert [i["kind"] for i in sent] == ["grounded", "topic", "offtopic"]
    items = {i["kind"]: i for i in run["items"]}
    assert items["topic"]["scores"]["coverage"] == {"value": 0.8, "error": None}
    assert items["grounded"]["scores"]["coverage"] == {"value": None, "error": "NOT_APPLICABLE"}
    assert items["offtopic"]["scores"]["restraint"]["value"] == 0.8
    assert items["topic"]["scores"]["restraint"]["error"] == "NOT_APPLICABLE"

    summary = run["summary"]
    assert summary["metrics"]["coverage"]["count"] == 1
    assert {k: v["count"] for k, v in summary["byKind"].items()} == {"grounded": 1, "topic": 1, "offtopic": 1}
    assert summary["byKind"]["topic"]["metrics"]["coverage"]["mean"] == 0.8
    assert summary["byKind"]["grounded"]["metrics"]["coverage"]["mean"] is None
