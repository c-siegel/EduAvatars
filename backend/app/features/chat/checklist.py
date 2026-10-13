"""
Conversation Plan (Checklist)

Projects with checklist_enabled give the conversation a plan: steps the avatar works through and
ticks off by writing "::done_N::" in its reply (N = the step's position), or takes back with
"::undone_N::". The markers are cut out like the gesture markers (see motion.py::extract_markers),
so they are never spoken or shown.

The server keeps no conversation state: every assistant message in the visitor's browser carries
the ticks made in it (ChatHistoryEntry.checks), and each turn replays them from the full history
the browser sends. Editing or regenerating a message cuts that history short, so the progress
rolls back with it. The model itself only sees the last messages (features/ai/llm/history.py),
without markers, so the current progress goes into the system prompt as a short status line.

Ticks refer to a step's stable ID, never its position, so a teacher reordering or deleting steps
doesn't make a running chat's ticks point at the wrong step; IDs that no longer exist are ignored.

How to use:
    checklist = checklist_for(project)                       # None when off or empty
    done = replay(entry.checks for entry in history)         # IDs of the steps done so far
    system_prompt += "\\n\\n" + checklist_prompt(checklist, done)
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.features.projects.models import Project


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    title: str
    note: str | None = None


@dataclass(frozen=True)
class Checklist:
    items: tuple[ChecklistItem, ...]
    # True: work through the steps in this order; False: any order.
    ordered: bool = True

    def id_for(self, number: int) -> str | None:
        """The ID of step `number` as the model counts (1-based), None if there is no such step."""
        return self.items[number - 1].id if 1 <= number <= len(self.items) else None


@dataclass(frozen=True)
class Check:
    """A step the model ticked off (done=True) or took back (done=False) in a reply, at a
    character position of the cleaned reply text — like motion.py::MotionMark."""

    id: str
    done: bool
    offset: int = 0

    def to_client(self) -> dict:
        return {"id": self.id, "done": self.done}

    def to_json(self) -> dict:
        return {"id": self.id, "done": self.done, "offset": self.offset}


def checklist_for(project: Project) -> Checklist | None:
    """The project's plan, or None when it is off or has no steps."""
    if not project.checklist_enabled:
        return None
    items = tuple(ChecklistItem(i["id"], i["title"], i.get("note") or None) for i in project.checklist_items)
    return Checklist(items, project.checklist_ordered) if items else None


def replay(checks_per_message: Iterable[Iterable]) -> set[str]:
    """The IDs of the steps done after applying every message's ticks in order. Accepts anything
    with `id`/`done` attributes (the request schema) or keys (a saved conversation)."""
    done: set[str] = set()
    for checks in checks_per_message:
        for check in checks or ():
            item_id, is_done = (check["id"], check["done"]) if isinstance(check, dict) else (check.id, check.done)
            if is_done:
                done.add(item_id)
            else:
                done.discard(item_id)
    return done


# English on purpose, like motion.py::MOTION_PROMPT: the model replies in the project's language
# either way. Kept short, since it is sent on every turn.
_ORDERED_INTRO = "This conversation follows a plan. Work through its steps in this order."
_ANY_ORDER_INTRO = "This conversation follows a plan. Its steps can be done in any order."
_MARKER_RULES = (
    "When a step is fully achieved, write ::done_N:: (N = its number) once in your reply, right "
    "where it is achieved. If a step marked ✓ turns out not to be achieved after all, write "
    "::undone_N::. These markers are neither spoken nor shown, so never mention them, the "
    "numbering or the plan's status. Notes are for you only: use them to judge the student's "
    "answers, never reveal or quote them."
)


def _one_line(text: str) -> str:
    return " ".join(text.split())


def checklist_prompt(checklist: Checklist, done_ids: set[str]) -> str:
    """The plan for the system prompt, with the current progress. A done step loses its note —
    the model no longer needs it, so a long plan gets cheaper as the conversation goes on."""
    lines = [_ORDERED_INTRO if checklist.ordered else _ANY_ORDER_INTRO, _MARKER_RULES]
    done_numbers, open_numbers = [], []
    for number, item in enumerate(checklist.items, start=1):
        if item.id in done_ids:
            done_numbers.append(number)
            lines.append(f"{number}. ✓ {_one_line(item.title)}")
        else:
            open_numbers.append(number)
            note = f" (note: {_one_line(item.note)})" if item.note else ""
            lines.append(f"{number}. {_one_line(item.title)}{note}")
    lines.append(_status_line(checklist.ordered, done_numbers, open_numbers))
    return "\n".join(lines)


def _status_line(ordered: bool, done_numbers: list[int], open_numbers: list[int]) -> str:
    if not open_numbers:
        return "Status: all steps done."
    done = ", ".join(map(str, done_numbers)) or "none"
    if ordered:
        return f"Status: done {done} · next {open_numbers[0]}"
    return f"Status: done {done} · open {', '.join(map(str, open_numbers))}"
