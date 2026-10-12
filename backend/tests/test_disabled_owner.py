"""Disabling an account (admin dashboard) takes its published chats offline: the public page, its
messages and every file it would load anonymously. Re-enabling brings them back unchanged."""

from conftest import browser_url, create_key, create_project, login_as, make_user, new_client, publish

GLB = b"glTF" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_a_disabled_teachers_chat_and_its_files_go_offline(client, anon, engine, teacher, fake_ai):
    avatar = client.post("/avatars", files={"file": ("Julia.glb", GLB, "model/gltf-binary")}).json()
    background = client.post("/backgrounds", files={"file": ("bg.png", PNG, "image/png")}).json()
    project = create_project(
        client,
        llmApiKeyId=create_key(client)["id"],
        ttsApiKeyId=create_key(client, key_type="tts")["id"],
        ttsEnabled=True,
        startPrompt="Willkommen",
        avatarModelId=avatar["id"],
        avatarBackgroundId=background["id"],
    )
    start_audio_url = client.post(f"/projects/{project['id']}/start-audio").json()["startAudioUrl"]
    slug = publish(client, project["id"])
    public_urls = [
        f"/public/{slug}",
        browser_url(avatar["fileUrl"]),
        browser_url(background["fileUrl"]),
        browser_url(start_audio_url),
    ]
    assert [anon.get(url).status_code for url in public_urls] == [200, 200, 200, 200]

    admin = login_as(new_client(), make_user(engine, email="admin@example.com", name="Admin", is_admin=True))
    assert admin.put(f"/admin/users/{teacher.id}", json={"enabled": False}).status_code == 200

    assert [anon.get(url).status_code for url in public_urls] == [404, 404, 404, 404]
    assert anon.post(f"/public/{slug}/messages", json={"message": "Hallo"}).status_code == 404
    assert anon.post(f"/public/{slug}/messages/stream", json={"message": "Hallo"}).status_code == 404
    assert fake_ai.completion_calls == []  # the teacher's key isn't used either

    assert admin.put(f"/admin/users/{teacher.id}", json={"enabled": True}).status_code == 200
    assert [anon.get(url).status_code for url in public_urls] == [200, 200, 200, 200]
