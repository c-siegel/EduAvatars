"""
Conversation Export (CSV/ZIP)

Renders saved conversations for download from the analytics table: one conversation as a plain
.csv, several bundled into a .zip with one .csv each.
"""

import csv
import io
import json
import re
import zipfile

from app.features.chat.models import Conversation
from app.features.projects.models import Project


def _slugify(value: str) -> str:
    """ASCII-only filename fragment — German umlauts spelled out instead of stripped, everything
    else collapsed to hyphens so the result is always safe as a filename and an HTTP header."""
    for umlaut, replacement in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        value = value.replace(umlaut, replacement).replace(umlaut.upper(), replacement.capitalize())
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return value or "gespraech"


def conversation_export_filename(conversation: Conversation, project: Project) -> str:
    """Filename for one conversation's exported CSV, used both for a standalone download and as
    a ZIP entry name when several conversations are exported at once."""
    date_part = conversation.started_at.strftime("%Y%m%d-%H%M")
    who = conversation.visitor_name or conversation.id[:8]
    return f"{_slugify(project.title)}_{date_part}_{_slugify(who)}.csv"


# Cell-leading characters a spreadsheet app (Excel, Google Sheets) reads as "this cell is a
# formula" rather than plain text — the classic CSV/formula-injection set (OWASP), plus a
# leading tab/CR which some parsers treat the same way.
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Neutralize CSV/formula injection in an exported cell.

    visitor_name and message content in build_conversation_csv below come straight from an
    anonymous chat visitor with no format restriction — a name or message starting with e.g.
    '=HYPERLINK("http://evil","x")' becomes a live, clickable formula the moment a teacher opens
    the exported CSV/ZIP in Excel or Sheets. Prefixing with a single quote is the standard fix:
    spreadsheet apps then show the cell as plain text and drop the leading quote themselves.
    """
    if value and value[0] in _CSV_FORMULA_TRIGGERS:
        return "'" + value
    return value


def build_conversation_csv(conversation: Conversation, project: Project) -> str:
    """Render one saved conversation as a CSV: a short metadata header (project, LLM model,
    visitor, start time), then one row per message with a timestamp column plus one column per
    speaker (Avatar/Schüler:in) — each row fills only the column of whichever side sent that
    message, so the two columns read top-to-bottom as each side's messages in order.

    Messages saved before per-message timestamps existed (see
    app/models/schemas/chat.py::ChatHistoryEntry) leave the "Zeitpunkt" cell blank for that row.
    """
    messages = json.loads(conversation.messages_json)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Projekt", _csv_safe(project.title)])
    writer.writerow(["LLM-Modell", _csv_safe(project.llm_model or "")])
    writer.writerow(["Name/ID", _csv_safe(conversation.visitor_name or "")])
    writer.writerow(["Gestartet", conversation.started_at.isoformat()])
    writer.writerow([])
    writer.writerow(["Zeitpunkt", "Avatar", "Schüler:in"])
    for message in messages:
        timestamp = message.get("timestamp") or ""
        content = _csv_safe(message.get("content", ""))
        if message.get("role") == "assistant":
            writer.writerow([timestamp, content, ""])
        else:
            writer.writerow([timestamp, "", content])
    return buffer.getvalue()


def build_export(rows: list[tuple[Conversation, Project]]) -> tuple[bytes | str, str, str]:
    """The download for one or more conversations: (content, media type, filename).

    A single conversation comes back as a plain .csv; more than one is bundled into a .zip (one
    .csv per conversation) — browsers don't let a page trigger several file downloads at once
    without extra prompts, so a bulk export has to be one file.
    """
    if len(rows) == 1:
        conversation, project = rows[0]
        return build_conversation_csv(conversation, project), "text/csv", conversation_export_filename(conversation, project)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        # Two different conversations can otherwise land on the same "<project>_<time>_<name>.csv"
        # name (e.g. two anonymous visitors starting in the same minute) — de-duplicated with a
        # numeric suffix so neither entry silently overwrites the other inside the archive.
        used_names: dict[str, int] = {}
        for conversation, project in rows:
            name = conversation_export_filename(conversation, project)
            if name in used_names:
                used_names[name] += 1
                stem, _, ext = name.rpartition(".")
                name = f"{stem}-{used_names[name]}.{ext}"
            else:
                used_names[name] = 0
            archive.writestr(name, build_conversation_csv(conversation, project))
    return buffer.getvalue(), "application/zip", "eduavatars-gespraeche.zip"
