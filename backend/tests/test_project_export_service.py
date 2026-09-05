"""Tests for the project export/import round-trip (app/services/project_export_service.py) —
in particular that secrets (API keys, chat password hash) never leave in an export, that a
freshly imported project is always an unpublished draft, and that avatar/background library
references are dropped rather than carried over when they don't belong to the importing user."""

from sqlmodel import Session, SQLModel, create_engine

import app.db.base  # noqa: F401  (registers every model's table on SQLModel.metadata)
from app.models.avatar_model import AvatarModel
from app.models.project import Project
from app.services.project_export_service import (
    ProjectImportError,
    export_project_yaml,
    import_project,
    parse_project_yaml,
)


def _make_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _make_project(**overrides) -> Project:
    fields = dict(
        user_id="owner",
        title="My Project",
        preprompt="be nice",
        temperature=0.7,
        top_p=0.9,
        llm_api_key_id="secret-key-id",
        tts_api_key_id="secret-tts-key-id",
        chat_password_hash="bcrypt-hash",
        published=True,
        share_slug="abc123",
    )
    fields.update(overrides)
    return Project(**fields)


def test_export_omits_secrets_and_publishing_state() -> None:
    with _make_session() as session:
        project = _make_project()
        session.add(project)
        session.commit()
        session.refresh(project)

        yaml_text = export_project_yaml(project)

    assert "secret-key-id" not in yaml_text
    assert "secret-tts-key-id" not in yaml_text
    assert "bcrypt-hash" not in yaml_text
    assert "abc123" not in yaml_text
    assert "published" not in yaml_text
    assert "temperature: 0.7" in yaml_text


def test_import_creates_an_unpublished_draft_without_the_original_keys() -> None:
    with _make_session() as session:
        project = _make_project()
        session.add(project)
        session.commit()
        session.refresh(project)

        data = parse_project_yaml(export_project_yaml(project))
        imported = import_project(session, "other-user", data)

        assert imported.id != project.id
        assert imported.user_id == "other-user"
        assert imported.title == "My Project"
        assert imported.temperature == 0.7
        assert imported.published is False
        assert imported.share_slug is None
        assert imported.llm_api_key_id is None
        assert imported.chat_password_hash is None


def test_import_drops_avatar_reference_not_owned_by_the_importing_user() -> None:
    with _make_session() as session:
        avatar = AvatarModel(id="av1", user_id="owner", name="A", file_path="/tmp/a.glb")
        session.add(avatar)
        project = _make_project(avatar_model_url="/avatars/av1/file")
        session.add(project)
        session.commit()
        session.refresh(project)

        data = parse_project_yaml(export_project_yaml(project))

        imported_for_stranger = import_project(session, "stranger", data)
        assert imported_for_stranger.avatar_model_url is None

        imported_for_owner = import_project(session, "owner", data)
        assert imported_for_owner.avatar_model_url == "/avatars/av1/file"


def test_parse_rejects_malformed_or_incomplete_input() -> None:
    for bad_input in ("not: [valid", "no_project_key: true", "project: {temperature: 99}", "project: {}"):
        try:
            parse_project_yaml(bad_input)
            raise AssertionError(f"expected ProjectImportError for input: {bad_input!r}")
        except ProjectImportError:
            pass
