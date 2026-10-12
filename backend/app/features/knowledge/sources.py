"""
Source Metadata: Editing, Bibliography Import, Linking

The operations behind the metadata routes (features/knowledge/router.py); the fields and how the
layers combine are in metadata.py.

- update_metadata: the teacher's own entries for one document (the top layer).
- import_bibliography: replace a knowledge base's BibTeX entries and link documents to them.
- apply_header: take a document's header over from the knowledge service once it's indexed.

Documents are linked to bibliography entries automatically — only those without a link yet, so
a teacher's choice is never overwritten — by, in this order: the key in the file's own header;
a file attached to the entry (its `file` field, as Zotero and JabRef write it) with the
document's file name; the key being the file name without extension (Better BibTeX can name
attachments by key).

How to use:
    entries_by_key = sources.entry_fields(session, kb.id)
    meta = metadata.effective(document, entries_by_key.get(document.bibtex_key))
"""

import json

from sqlalchemy import delete
from sqlmodel import Session, select

from app.core.error_codes import ErrorCode
from app.features.knowledge import bibtex, metadata
from app.features.knowledge.models import KnowledgeBase, KnowledgeBibEntry, KnowledgeDocument
from app.features.knowledge.upload_checks import safe_display_name


class BibliographyInvalid(ValueError):
    """The upload isn't a readable BibTeX file; the message is an ErrorCode."""


def entry_fields(session: Session, kb_ids: list[str], keys: list[str]) -> dict[tuple[str, str], dict]:
    """{(knowledge_base_id, key): fields} for the given keys of the given knowledge bases — only
    the linked entries, not a whole bibliography (this runs on every chat turn)."""
    if not kb_ids or not keys:
        return {}
    rows = session.exec(
        select(KnowledgeBibEntry).where(
            KnowledgeBibEntry.knowledge_base_id.in_(kb_ids), KnowledgeBibEntry.key.in_(keys)
        )
    ).all()
    return {(row.knowledge_base_id, row.key): json.loads(row.fields_json or "{}") for row in rows}


def document_metadata(session: Session, documents: list[KnowledgeDocument]) -> dict[str, dict]:
    """{document_id: effective metadata} for documents of any of the user's knowledge bases."""
    linked = [d for d in documents if d.bibtex_key]
    entries = entry_fields(
        session, sorted({d.knowledge_base_id for d in linked}), sorted({d.bibtex_key for d in linked})
    )
    return {
        d.id: metadata.effective(d, entries.get((d.knowledge_base_id, d.bibtex_key)) if d.bibtex_key else None)
        for d in documents
    }


def update_metadata(session: Session, document: KnowledgeDocument, fields: dict) -> KnowledgeDocument:
    """Replace the teacher's own entries with `fields` (unset or empty fields fall back)."""
    cleaned = metadata.clean_fields(fields)
    document.bibtex_key = cleaned.pop("bibtex_key", None)
    document.meta_json = json.dumps(cleaned, ensure_ascii=False) if cleaned else None
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def apply_header(session: Session, document: KnowledgeDocument, raw_header: dict | None) -> None:
    """Store a freshly indexed document's header and, if it has none yet, link it to the
    bibliography. Doesn't commit — runs inside refresh_statuses' update."""
    header = metadata.from_header(raw_header)
    document.header_json = json.dumps(header, ensure_ascii=False) if header else None
    if not document.bibtex_key:
        if header.get("bibtex_key"):
            document.bibtex_key = header["bibtex_key"]
        else:
            entries = session.exec(
                select(KnowledgeBibEntry).where(KnowledgeBibEntry.knowledge_base_id == document.knowledge_base_id)
            ).all()
            document.bibtex_key = _match(document, *_link_maps(entries))


def _link_maps(entries: list[KnowledgeBibEntry]) -> tuple[dict[str, str], dict[str, str]]:
    by_file: dict[str, str] = {}
    by_key: dict[str, str] = {}
    for entry in entries:
        by_key.setdefault(entry.key.lower(), entry.key)
        for name in json.loads(entry.fields_json or "{}").get("files", []):
            # Compared the way the document's own name was made: sanitised the same way.
            by_file.setdefault(safe_display_name(name).lower(), entry.key)
    return by_file, by_key


def _match(document: KnowledgeDocument, by_file: dict[str, str], by_key: dict[str, str]) -> str | None:
    name = document.filename.lower()
    if name in by_file:
        return by_file[name]
    return by_key.get(name.rsplit(".", 1)[0])


def import_bibliography(session: Session, kb: KnowledgeBase, data: bytes) -> dict:
    """Replace the knowledge base's entries with the file's and link unlinked documents.

    Returns {"entries", "skipped", "linked": documents now resolving to an entry, "unlinked":
    the file names of those that don't}.
    """
    if len(data) > bibtex.MAX_BIB_BYTES:
        raise BibliographyInvalid(ErrorCode.KNOWLEDGE_BIB_TOO_LARGE)
    if b"\x00" in data:
        raise BibliographyInvalid(ErrorCode.KNOWLEDGE_BIB_INVALID)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    parsed, skipped = bibtex.parse_bibtex(text)
    if not parsed:
        raise BibliographyInvalid(ErrorCode.KNOWLEDGE_BIB_INVALID)

    session.execute(delete(KnowledgeBibEntry).where(KnowledgeBibEntry.knowledge_base_id == kb.id))
    entries = []
    for entry in parsed:
        raw = bibtex.to_fields(entry)
        fields = metadata.clean_fields(raw)
        fields.pop("bibtex_key", None)
        if raw.get("files"):
            fields["files"] = raw["files"]
        row = KnowledgeBibEntry(
            knowledge_base_id=kb.id,
            user_id=kb.user_id,
            key=entry.key,
            fields_json=json.dumps(fields, ensure_ascii=False),
        )
        session.add(row)
        entries.append(row)

    by_file, by_key = _link_maps(entries)
    documents = session.exec(select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb.id)).all()
    linked = 0
    unlinked = []
    for document in documents:
        if not document.bibtex_key:
            header_key = json.loads(document.header_json or "{}").get("bibtex_key")
            document.bibtex_key = header_key or _match(document, by_file, by_key)
            if document.bibtex_key:
                session.add(document)
        if document.bibtex_key and document.bibtex_key.lower() in by_key:
            linked += 1
        else:
            unlinked.append(document.filename)
    session.commit()
    return {"entries": len(entries), "skipped": skipped, "linked": linked, "unlinked": unlinked}


def list_bibliography(session: Session, kb: KnowledgeBase) -> list[dict]:
    rows = session.exec(
        select(KnowledgeBibEntry).where(KnowledgeBibEntry.knowledge_base_id == kb.id).order_by(KnowledgeBibEntry.key)
    ).all()
    out = []
    for row in rows:
        fields = json.loads(row.fields_json or "{}")
        out.append({"key": row.key, "title": fields.get("title"), "author": fields.get("author"), "year": fields.get("year")})
    return out


def delete_bibliography(session: Session, kb: KnowledgeBase) -> None:
    """The entries go; documents keep their keys (they resolve again after a re-import)."""
    session.execute(delete(KnowledgeBibEntry).where(KnowledgeBibEntry.knowledge_base_id == kb.id))
    session.commit()


def titles_by_document(session: Session, kb_id: str) -> list[str]:
    """Each document's title if its metadata has one, else its file name without extension —
    what the evaluation's topic questions are told about the material."""
    documents = list(
        session.exec(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.knowledge_base_id == kb_id)
            .order_by(KnowledgeDocument.created_at)
            .limit(50)
        )
    )
    meta = document_metadata(session, documents)
    return [meta[d.id].get("title") or d.filename.rsplit(".", 1)[0] for d in documents]
