import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.api import routes
from app.main import app
from app.storage import db
from fastapi import UploadFile
from fastapi.testclient import TestClient
from PIL import Image

client = TestClient(app)


def png():
    stream = io.BytesIO()
    Image.new("L", (16, 16), 127).save(stream, format="PNG")
    return stream.getvalue()


def uploaded_case():
    return client.post("/api/upload", files={"file": ("synthetic.png", png(), "image/png")}).json()["case"]


def test_case_revision_increments_and_stale_editor_cannot_overwrite():
    original = uploaded_case()
    assert original["revision"] == 1
    saved = client.post("/api/cases", json={**original, "title": "First reviewer"}, headers={"If-Match": '"1"'})
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2
    stale = client.post("/api/cases", json={**original, "title": "Stale reviewer"}, headers={"If-Match": '"1"'})
    assert stale.status_code == 409
    assert client.get(f"/api/cases/{original['case_id']}").json()["title"] == "First reviewer"


def test_precondition_cannot_recreate_deleted_case():
    case = uploaded_case()
    client.delete(f"/api/cases/{case['case_id']}")
    result = client.post("/api/cases", json=case, headers={"If-Match": "1"})
    assert result.status_code == 404
    assert db.get_case(case["case_id"]) is None


def test_invalid_precondition_is_rejected_before_write():
    case = uploaded_case()
    result = client.post("/api/cases", json={**case, "title": "Must not save"}, headers={"If-Match": "not-a-revision"})
    assert result.status_code == 400
    assert db.get_case(case["case_id"])["title"] == case["title"]


def test_concurrent_chat_replies_do_not_lose_either_message_pair(monkeypatch):
    case = uploaded_case()
    provider_barrier = threading.Barrier(2)
    read_barrier = threading.Barrier(2)
    counts = threading.local()
    original_get = routes.get_case
    def get_at_same_time(case_id):
        result = original_get(case_id)
        counts.reads = getattr(counts, "reads", 0) + 1
        if counts.reads == 2:
            read_barrier.wait(timeout=5)
        return result
    def reply(message, *args, **kwargs):
        provider_barrier.wait(timeout=5)
        return {"content": f"reply-{message}", "backend": "demo", "fallback": False}
    monkeypatch.setattr(routes, "get_case", get_at_same_time)
    monkeypatch.setattr(routes, "chat_response", reply)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(routes.chat, case["case_id"], {"message": message}) for message in ("one", "two")]
        for future in futures:
            future.result(timeout=10)
    history = db.get_case(case["case_id"])["chat_history"]
    assert len(history) == 4
    assert {entry["content"] for entry in history} == {"one", "two", "reply-one", "reply-two"}
    assert all(history[index + 1]["content"] == f"reply-{history[index]['content']}" for index in (0, 2))


def test_concurrent_uploads_keep_both_images_and_unique_indices(monkeypatch):
    case = uploaded_case()
    barrier = threading.Barrier(2)
    ingest = routes.ingest_upload
    def synchronized_ingest(*args, **kwargs):
        result = ingest(*args, **kwargs)
        barrier.wait(timeout=5)
        return result
    monkeypatch.setattr(routes, "ingest_upload", synchronized_ingest)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(routes.add_case_image, case["case_id"], UploadFile(file=io.BytesIO(png()), filename=name)) for name in ("second.png", "third.png")]
        for future in futures:
            future.result(timeout=10)
    saved = client.get(f"/api/cases/{case['case_id']}").json()
    assert len(saved["images"]) == 3
    assert [image["index"] for image in saved["images"]] == [0, 1, 2]
    assert len({image["image_id"] for image in saved["images"]}) == 3


def test_simultaneous_editors_only_one_can_commit_same_revision():
    case = uploaded_case()
    barrier = threading.Barrier(2)
    def save(title):
        barrier.wait(timeout=5)
        with TestClient(app) as editor:
            return editor.post("/api/cases", json={**case, "title": title}, headers={"If-Match": "1"}).status_code
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(save, ("First", "Second")))
    assert sorted(results) == [200, 409]


def test_transaction_failure_rolls_back_payload_and_revision():
    case = uploaded_case()
    def fail(current):
        current["title"] = "Must roll back"
        raise ValueError("synthetic transform failure")
    with pytest.raises(ValueError):
        db.update_case(case["case_id"], fail)
    assert db.get_case(case["case_id"]) == case


def test_transaction_cannot_change_case_identity():
    case = uploaded_case()
    with pytest.raises(ValueError, match="identity"):
        db.update_case(case["case_id"], lambda current: {**current, "case_id": "other"})
    assert db.get_case("other") is None
    assert db.get_case(case["case_id"]) == case


def test_legacy_case_can_be_updated_from_revision_zero_without_schema_migration():
    payload = {"case_id": "legacy", "title": "Original", "created_at": "2026-10-08", "updated_at": "2026-10-08"}
    with db.connect() as connection:
        connection.execute("INSERT INTO cases (case_id, title, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("legacy", "Original", json.dumps(payload), payload["created_at"], payload["updated_at"]))
    case = client.get("/api/cases/legacy").json()
    assert case["revision"] == 0
    result = client.post("/api/cases", json={**case, "title": "Reviewed"}, headers={"If-Match": "0"})
    assert result.status_code == 200
    assert result.json()["revision"] == 1
    assert result.json()["created_at"] == payload["created_at"]


def test_parallel_transactions_keep_all_changes():
    case = uploaded_case()
    barrier = threading.Barrier(8)
    def append(index):
        barrier.wait(timeout=5)
        def transform(current):
            current["notes"] = [*current.get("notes", []), index]
            return current
        db.update_case(case["case_id"], transform)
    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(append, range(8)))
    saved = db.get_case(case["case_id"])
    assert sorted(saved["notes"]) == list(range(8))
    assert saved["revision"] == 9
