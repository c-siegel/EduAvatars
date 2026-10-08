import json

from tests.conftest import AUTH, JUDGE

PASSAGE = "Photosynthese findet in den Chloroplasten statt. Dabei entsteht aus Licht, Wasser und CO2 Zucker."


def score_body(**overrides) -> dict:
    body = {
        "items": [
            {
                "id": "case-1",
                "question": "Wo findet Photosynthese statt?",
                "answer": "In den Chloroplasten.",
                "contexts": [PASSAGE],
                "reference": "In den Chloroplasten der Pflanzenzellen.",
            }
        ],
        "metrics": ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "factual_correctness"],
        "judge": JUDGE,
        "embedding": {"provider": "local"},
        "language": "en",
    }
    body.update(overrides)
    return body


def test_health_needs_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ragas_version"].startswith("0.4")


def test_ragas_telemetry_is_off():
    import os

    import app  # noqa: F401

    assert os.environ["RAGAS_DO_NOT_TRACK"] == "true"


def test_routes_require_the_token(client, judge):
    assert client.post("/score", json=score_body()).status_code == 401
    assert client.post("/score", json=score_body(), headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert judge.calls == []


def test_scores_every_metric(client, judge, embed_calls):
    response = client.post("/score", json=score_body(), headers=AUTH)
    assert response.status_code == 200, response.text
    scores = response.json()["items"][0]["scores"]
    assert set(scores) == {"faithfulness", "answer_relevancy", "context_precision", "context_recall", "factual_correctness"}
    for name, score in scores.items():
        assert score["error"] is None, name
        assert 0.0 <= score["value"] <= 1.0, name
    # The fake judge supports every statement and recalls every reference sentence.
    assert scores["faithfulness"]["value"] == 1.0
    assert scores["context_recall"]["value"] == 1.0
    assert embed_calls, "answer relevancy embeds through the knowledge service"


def test_the_judge_gets_the_teachers_key_and_model(client, judge, embed_calls):
    client.post("/score", json=score_body(metrics=["faithfulness"]), headers=AUTH)
    assert judge.calls
    assert all(call["api_key"] == JUDGE["api_key"] and call["model"] == JUDGE["model"] for call in judge.calls)
    assert all(call["temperature"] == 0 for call in judge.calls)


def test_unsupported_statements_lower_faithfulness(client, judge):
    judge.overrides["verdict"] = 0
    response = client.post("/score", json=score_body(metrics=["faithfulness"]), headers=AUTH)
    assert response.json()["items"][0]["scores"]["faithfulness"] == {"value": 0.0, "error": None}


def test_metrics_that_dont_apply_are_skipped_with_a_reason(client, judge):
    item = {"id": "no-ctx", "question": "Wer bist du?", "answer": "Ein Avatar.", "contexts": []}
    response = client.post("/score", json=score_body(items=[item], embedding=None), headers=AUTH)
    scores = response.json()["items"][0]["scores"]
    assert scores["faithfulness"] == {"value": None, "error": "NO_CONTEXTS"}
    assert scores["context_precision"] == {"value": None, "error": "NO_CONTEXTS"}
    assert scores["context_recall"] == {"value": None, "error": "NO_REFERENCE"}
    assert scores["factual_correctness"] == {"value": None, "error": "NO_REFERENCE"}
    assert scores["answer_relevancy"] == {"value": None, "error": "NO_EMBEDDING"}
    assert judge.calls == []


def test_nothing_retrieved_means_zero_recall(client, judge):
    item = {"id": "x", "question": "Q?", "answer": "A.", "contexts": [], "reference": "R."}
    response = client.post("/score", json=score_body(items=[item], metrics=["context_recall"]), headers=AUTH)
    assert response.json()["items"][0]["scores"]["context_recall"] == {"value": 0.0, "error": None}


def test_a_failing_judge_costs_cells_not_the_request(client, judge, caplog):
    judge.fail = True
    response = client.post("/score", json=score_body(metrics=["faithfulness", "context_recall"]), headers=AUTH)
    assert response.status_code == 200
    scores = response.json()["items"][0]["scores"]
    assert scores["faithfulness"] == {"value": None, "error": "JUDGE_FAILED"}
    assert scores["context_recall"] == {"value": None, "error": "JUDGE_FAILED"}
    # Neither the key nor the material ends up in the logs.
    assert JUDGE["api_key"] not in caplog.text
    assert "Chloroplasten" not in caplog.text


def test_an_unparsable_reply_is_retried_once(client, judge):
    judge.garbage = True
    response = client.post("/score", json=score_body(metrics=["context_recall"]), headers=AUTH)
    assert response.json()["items"][0]["scores"]["context_recall"]["error"] == "JUDGE_FAILED"
    # One retry, not instructor's default of three: each one is a paid call.
    assert len(judge.calls) == 2


def test_validation_errors_dont_echo_the_key(client):
    body = score_body(metrics=["not-a-metric"])
    response = client.post("/score", json=body, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_REQUEST"
    assert JUDGE["api_key"] not in response.text


def test_german_prompts_are_translated_once_and_cached(client, judge, tmp_path):
    from app.config import settings

    body = score_body(metrics=["faithfulness"], language="de")
    client.post("/score", json=body, headers=AUTH)
    translations = [c for c in judge.calls if "Statements to translate:" in c["messages"][-1]["content"]]
    assert translations
    cache = list((tmp_path / "data" / "prompt-cache").glob("Faithfulness.*.de.json"))
    assert cache and settings.rag_eval_data_dir == str(tmp_path / "data")
    assert any("[de]" in json.dumps(json.loads(p.read_text(encoding="utf-8"))) for p in cache)

    judge.calls.clear()
    client.post("/score", json=body, headers=AUTH)
    assert not [c for c in judge.calls if "Statements to translate:" in c["messages"][-1]["content"]]


def chunk(chunk_id: int, text: str = PASSAGE) -> dict:
    return {"chunk_id": chunk_id, "text": text, "heading": "Biologie", "page": 3}


def test_generates_one_draft_per_passage(client, judge):
    body = {"chunks": [chunk(i) for i in range(5)], "size": 3, "judge": JUDGE, "language": "de"}
    response = client.post("/generate-testset", json=body, headers=AUTH)
    assert response.status_code == 200, response.text
    cases = response.json()["cases"]
    assert len(cases) == 3
    assert all(case["question"] and case["reference"] for case in cases)
    assert {case["chunk_id"] for case in cases} <= set(range(5))
    prompt = judge.calls[0]["messages"][-1]["content"]
    assert "German" in prompt and "Biologie" in prompt and PASSAGE in prompt


def test_short_passages_and_empty_drafts_are_skipped(client, judge):
    judge.overrides["question"] = ""
    body = {"chunks": [chunk(1), chunk(2, "Seite 4")], "size": 2, "judge": JUDGE}
    response = client.post("/generate-testset", json=body, headers=AUTH)
    assert response.json()["cases"] == []
    assert len(judge.calls) == 1


def test_generation_reports_a_judge_that_always_fails(client, judge):
    judge.fail = True
    body = {"chunks": [chunk(1), chunk(2)], "size": 2, "judge": JUDGE}
    response = client.post("/generate-testset", json=body, headers=AUTH)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "JUDGE_FAILED"
