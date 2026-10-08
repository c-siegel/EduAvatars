import os
import types

import pytest

from app import embedding, errors
from app.config import settings
from tests.conftest import AUTH, LOCAL_MODEL, fake_vector, local_config, upload, wait_and_status
from tests.fixtures import docx_xml, make_docx, make_pdf


def _query(client, text, kb_ids=("kb-1",), config=None, top_k=4):
    response = client.post(
        "/query",
        headers=AUTH,
        json={"knowledge_base_ids": list(kb_ids), "query": text, "top_k": top_k, "embedding": config or local_config()},
    )
    assert response.status_code == 200, response.text
    return response.json()["passages"]


def test_health_needs_no_token_but_everything_else_does(client):
    assert client.get("/health").status_code == 200
    assert client.get("/capabilities").status_code == 401
    assert client.get("/capabilities", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/query", json={}).status_code == 401


def test_capabilities(client):
    body = client.get("/capabilities", headers=AUTH).json()
    assert body["local_model"] == LOCAL_MODEL
    assert body["file_types"] == ["pdf", "docx", "txt", "md"]
    assert body["hard_limits"]["max_upload_mb"] == settings.rag_hard_max_upload_mb
    assert body["docling_available"] is False


def test_upload_index_search_delete(client):
    pdf = make_pdf(["Die Photosynthese wandelt Lichtenergie in chemische Energie um.", "Die Zellatmung setzt Energie frei."])
    response = upload(client, "Biologie.pdf", pdf)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"

    status = wait_and_status(client)
    assert status["status"] == "ready", status
    assert status["page_count"] == 2
    assert status["chunk_count"] == 2

    passages = _query(client, "Was macht die Photosynthese?")
    assert passages[0]["page"] == 1
    assert "Photosynthese" in passages[0]["text"]
    assert passages[0]["document_id"] == "doc-1"

    # The original file is gone once parsed — only derived text is kept.
    assert not os.listdir(os.path.join(settings.rag_data_dir, "incoming"))

    assert client.delete("/documents/doc-1", headers=AUTH).status_code == 204
    assert _query(client, "Photosynthese") == []
    # Idempotent.
    assert client.delete("/documents/doc-1", headers=AUTH).status_code == 204


def test_search_is_limited_to_the_requested_knowledge_bases(client):
    upload(client, "a.txt", "Vulkane spucken Lava.".encode(), document_id="a", kb_id="kb-a")
    upload(client, "b.txt", "Vulkane auf dem Mars.".encode(), document_id="b", kb_id="kb-b")
    client.app.state.ingestor.wait_idle()
    assert {p["document_id"] for p in _query(client, "Vulkane", kb_ids=["kb-a"])} == {"a"}
    assert {p["document_id"] for p in _query(client, "Vulkane", kb_ids=["kb-a", "kb-b"])} == {"a", "b"}


def test_delete_knowledge_base_removes_its_documents(client):
    upload(client, "a.txt", b"Erdbeben und Plattentektonik", document_id="a", kb_id="kb-a")
    client.app.state.ingestor.wait_idle()
    assert client.delete("/knowledge-bases/kb-a", headers=AUTH).status_code == 204
    status = client.post("/documents/status", headers=AUTH, json={"document_ids": ["a"]}).json()
    assert status == []


def test_rejected_upload_is_not_stored(client):
    response = upload(client, "virus.pdf", b"MZ not a pdf")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == errors.FILE_TYPE_MISMATCH
    assert client.post("/documents/status", headers=AUTH, json={"document_ids": ["doc-1"]}).json() == []


def test_size_limit_from_request_is_enforced_and_clamped(client, monkeypatch):
    big = b"a " * (1024 * 1024)  # 2 MB
    response = upload(client, "big.txt", big, limits={"max_upload_mb": 1})
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == errors.FILE_TOO_LARGE
    # An admin value above the operator's ceiling is clamped to the ceiling.
    monkeypatch.setattr(settings, "rag_hard_max_upload_mb", 1)
    response = upload(client, "big.txt", big, document_id="doc-2", limits={"max_upload_mb": 50})
    assert response.status_code == 413


def test_hostile_docx_fails_in_the_background(client):
    from tests.fixtures import XXE_DOCUMENT

    assert upload(client, "evil.docx", make_docx(XXE_DOCUMENT)).status_code == 202
    status = wait_and_status(client)
    assert (status["status"], status["error_code"]) == ("failed", errors.DOCX_INVALID)


def test_scanned_pdf_without_text_fails_with_a_hint(client):
    upload(client, "scan.pdf", make_pdf([""]))
    status = wait_and_status(client)
    assert (status["status"], status["error_code"]) == ("failed", errors.NO_EXTRACTABLE_TEXT)


def test_duplicate_document_id_is_refused(client):
    assert upload(client, "a.txt", b"Text").status_code == 202
    response = upload(client, "a.txt", b"Text")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == errors.DOCUMENT_EXISTS


def test_knowledge_base_keeps_its_embedding_model(client):
    upload(client, "a.txt", b"Text")
    other = {"mode": "api", "model": "openai/text-embedding-3-small", "api_key": "sk-test"}
    response = upload(client, "b.txt", b"Text", document_id="doc-2", embedding=other)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == errors.EMBEDDING_MISMATCH


def test_local_model_must_be_the_configured_one(client):
    response = upload(client, "a.txt", b"Text", embedding={"mode": "local", "model": "jinaai/jina-embeddings-v3"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == errors.EMBEDDING_MODEL_NOT_ALLOWED


def test_docx_end_to_end_keeps_headings(client):
    xml = docx_xml([("h", "Mitose"), ("p", "Die Mitose ist die Kernteilung."), ("h", "Meiose"), ("p", "Die Meiose halbiert.")])
    upload(client, "Zellteilung.docx", make_docx(xml))
    assert wait_and_status(client)["status"] == "ready"
    passages = _query(client, "Kernteilung Mitose")
    assert passages[0]["heading"] == "Mitose"
    assert passages[0]["page"] is None


@pytest.fixture
def fake_litellm(monkeypatch):
    calls = []

    def embedding_call(**kwargs):
        calls.append(kwargs)
        data = [{"index": i, "embedding": fake_vector(t, 32)} for i, t in enumerate(kwargs["input"])]
        return types.SimpleNamespace(data=list(reversed(data)))

    import litellm

    monkeypatch.setattr(litellm, "embedding", embedding_call)
    return calls


def test_api_embeddings_use_the_given_key(client, fake_litellm):
    config = {"mode": "api", "model": "openai/text-embedding-3-small", "api_key": "sk-test"}
    upload(client, "a.txt", "Gravitation zieht Massen an.".encode(), embedding=config)
    assert wait_and_status(client)["status"] == "ready"
    passages = _query(client, "Gravitation", config=config)
    assert passages and passages[0]["document_id"] == "doc-1"
    assert all(call["api_key"] == "sk-test" for call in fake_litellm)
    assert fake_litellm[0]["model"] == "openai/text-embedding-3-small"


def test_embedding_test_route(client, fake_litellm):
    config = {"mode": "api", "model": "openai/text-embedding-3-small", "api_key": "sk-test"}
    response = client.post("/embedding-test", headers=AUTH, json={"embedding": config})
    assert response.json() == {"dimensions": 32}


def test_api_embedding_failure_is_reported_without_details(client, monkeypatch):
    import litellm

    def failing(**kwargs):
        raise RuntimeError("401 invalid key sk-test")

    monkeypatch.setattr(litellm, "embedding", failing)
    config = {"mode": "api", "model": "openai/x", "api_key": "sk-test"}
    response = client.post("/embedding-test", headers=AUTH, json={"embedding": config})
    assert response.status_code == 502
    assert response.json() == {"detail": {"code": errors.EMBEDDING_FAILED}}


def test_restart_recovers_local_jobs_and_fails_api_jobs(tmp_path):
    from app.ingest import Ingestor
    from app.schemas import EmbeddingConfig
    from app.store import Store

    store = Store(str(tmp_path / "r.db"))
    store.register_knowledge_base("kb-l", EmbeddingConfig(**local_config()))
    store.register_knowledge_base("kb-a", EmbeddingConfig(mode="api", model="openai/x"))
    store.create_document("local-doc", "kb-l", "txt", "light")
    store.create_document("api-doc", "kb-a", "txt", "light")
    ingestor = Ingestor(store, str(tmp_path))
    ingestor.incoming_path("local-doc").write_bytes(b"Text nach dem Neustart")
    ingestor.incoming_path("api-doc").write_bytes(b"Text")
    ingestor.incoming_path("orphan").write_bytes(b"x")
    ingestor.start()
    ingestor.wait_idle()
    ingestor.stop()
    statuses = {s.document_id: (s.status, s.error_code) for s in store.statuses(["local-doc", "api-doc"])}
    assert statuses == {"local-doc": ("ready", None), "api-doc": ("failed", errors.INTERRUPTED)}
    # The interrupted API document keeps its original for a retry; everything else is gone.
    assert [p.name for p in (tmp_path / "incoming").iterdir()] == ["api-doc"]
    assert ingestor.retryable("api-doc")


def test_unknown_local_model_setting_fails_fast(monkeypatch):
    monkeypatch.setattr(settings, "rag_local_embedding_model", "jinaai/jina-embeddings-v3")
    with pytest.raises(RuntimeError, match="allowlist"):
        embedding.local_model_spec()


def test_failed_document_can_be_retried_and_original_is_kept_until_then(client, monkeypatch):
    from app.ingest import Ingestor
    from app.parsing.types import ParseResult, Section

    upload(client, "scan.pdf", make_pdf([""]))
    status = wait_and_status(client)
    assert (status["status"], status["retryable"]) == ("failed", True)
    incoming = os.path.join(settings.rag_data_dir, "incoming", "doc-1")
    assert os.path.exists(incoming)

    # Retrying the same scan fails the same way, and stays retryable.
    body = {"parser": "light", "embedding": local_config()}
    assert client.post("/documents/doc-1/retry", headers=AUTH, json=body).status_code == 202
    assert wait_and_status(client)["error_code"] == errors.NO_EXTRACTABLE_TEXT

    # Docling isn't configured here.
    response = client.post("/documents/doc-1/retry", headers=AUTH, json={**body, "parser": "docling"})
    assert response.json()["detail"]["code"] == errors.DOCLING_UNAVAILABLE

    # A retry that succeeds (here: the parser now finds text) indexes it and drops the original.
    def parse_with_ocr(self, job, data):
        return ParseResult([Section("Nach OCR lesbarer Text", page=1)], page_count=1)

    monkeypatch.setattr(Ingestor, "_parse", parse_with_ocr)
    assert client.post("/documents/doc-1/retry", headers=AUTH, json=body).status_code == 202
    status = wait_and_status(client)
    assert (status["status"], status["retryable"]) == ("ready", False)
    assert not os.path.exists(incoming)
    response = client.post("/documents/doc-1/retry", headers=AUTH, json=body)
    assert (response.status_code, response.json()["detail"]["code"]) == (409, errors.RETRY_NOT_POSSIBLE)


def test_kept_originals_expire(client, monkeypatch):
    upload(client, "scan.pdf", make_pdf([""]))
    wait_and_status(client)
    incoming = os.path.join(settings.rag_data_dir, "incoming", "doc-1")
    old = os.path.getmtime(incoming) - 25 * 3600
    os.utime(incoming, (old, old))
    client.app.state.ingestor.sweep()
    assert not os.path.exists(incoming)
    assert wait_and_status(client)["retryable"] is False


def test_deleting_a_failed_document_removes_its_original(client):
    upload(client, "scan.pdf", make_pdf([""]))
    wait_and_status(client)
    client.delete("/documents/doc-1", headers=AUTH)
    assert not os.listdir(os.path.join(settings.rag_data_dir, "incoming"))
