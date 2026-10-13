"""Tests for the conversation plan (app/features/chat/checklist.py): the steps a teacher sets up,
the "::done_N::" / "::undone_N::" markers the avatar ticks them off with, the progress replayed
from the visitor's history into the system prompt, and what students and teachers get to see."""

from conftest import create_project

from app.features.projects.export import parse_project_yaml

STEPS = [
    {"title": "Begrüßung"},
    {"title": "Fotosynthese erklären", "note": "Chlorophyll muss vorkommen"},
    {"title": "Quiz", "note": "Antwort: Licht, Wasser, CO2"},
]


# --- Configuration ---


def test_checklist_defaults_off_and_steps_get_stable_ids(client, teacher) -> None:
    project = create_project(client)
    assert project["checklistEnabled"] is False
    assert project["checklistVisible"] is False
    assert project["checklistOrdered"] is True
    assert project["checklistItems"] == []

    updated = client.put(f"/projects/{project['id']}", json={"checklistEnabled": True, "checklistItems": STEPS}).json()
    ids = [item["id"] for item in updated["checklistItems"]]
    assert len(set(ids)) == 3 and all(ids)
    assert updated["checklistItems"][0] == {"id": ids[0], "title": "Begrüßung", "note": None}

    # Reordering keeps each step's ID, and an existing ID is never replaced.
    reordered = [updated["checklistItems"][2], updated["checklistItems"][0]]
    again = client.put(f"/projects/{project['id']}", json={"checklistItems": reordered}).json()
    assert [item["id"] for item in again["checklistItems"]] == [ids[2], ids[0]]


def test_invalid_checklists_are_rejected(client, teacher) -> None:
    project = create_project(client)
    url = f"/projects/{project['id']}"
    assert client.put(url, json={"checklistItems": [{"title": "  "}]}).status_code == 422
    duplicate = [{"id": "abcdef12", "title": "A"}, {"id": "abcdef12", "title": "B"}]
    assert client.put(url, json={"checklistItems": duplicate}).status_code == 422
    assert client.put(url, json={"checklistItems": [{"id": "../x", "title": "A"}]}).status_code == 422
    assert client.put(url, json={"checklistItems": [{"title": str(i)} for i in range(21)]}).status_code == 422


def test_checklist_survives_export_and_import(client, teacher) -> None:
    project = create_project(client, checklistEnabled=True, checklistOrdered=False, checklistItems=STEPS)
    with_ids = project["checklistItems"]

    exported = client.get(f"/projects/{project['id']}/export")
    assert exported.status_code == 200, exported.text
    data = parse_project_yaml(exported.text)

    assert data.checklist_enabled is True and data.checklist_ordered is False
    assert [item.model_dump() for item in data.checklist_items] == with_ids
    # Exports written before the plan existed import without one.
    assert parse_project_yaml("eduavatars_export: 2\nproject:\n  title: x\n").checklist_items == []

