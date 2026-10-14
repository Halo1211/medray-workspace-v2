"""Regression checks for storage, download recovery, chat and report exports."""

from pathlib import Path
from types import SimpleNamespace
import os

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.model_finder import providers
from app.storage import db
from test_bug_audit import png, upload
from test_download_recovery import Response


@pytest.fixture
def audit_download_manager(monkeypatch):
    manager = providers.DownloadManager()
    monkeypatch.setattr(providers, "_validate_manual_download_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "_start_worker", lambda *_: None)
    return manager


@pytest.mark.parametrize("fail_transaction", [False, True])
def test_database_context_closes_connection_and_preserves_transaction_semantics(fail_transaction):
    with db.connect() as setup:
        setup.execute("CREATE TABLE audit_transaction (value TEXT)")
    try:
        with db.connect() as connection:
            connection.execute("INSERT INTO audit_transaction VALUES ('synthetic')")
            if fail_transaction:
                raise RuntimeError("rollback this transaction")
    except RuntimeError:
        pass
    with db.connect() as check:
        count = check.execute("SELECT COUNT(*) FROM audit_transaction").fetchone()[0]
    assert count == (0 if fail_transaction else 1)
    with pytest.raises(db.sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_cancelled_download_can_be_retried(monkeypatch, audit_download_manager):
    manager = audit_download_manager
    job = manager.start("https://models.example/model.pt")
    assert manager.cancel(job["id"])["status"] == "cancelled"
    response = Response(b"complete", headers={"Content-Length": "8"})
    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=lambda *args, **kwargs: response))
    manager.retry(job["id"])
    manager._run(job["id"])
    assert job["status"] == "completed", job.get("error")
    assert Path(job["target_path"]).read_bytes() == b"complete"


def test_paused_segmented_download_keeps_its_target(audit_download_manager):
    manager = audit_download_manager
    first = manager.start("https://models.example/first.pt", filename="model.pt", connections=4)
    segment = Path(first["partial_path"] + ".segment-0")
    segment.write_bytes(b"first model bytes")
    first["status"] = "paused"
    manager.reserved_targets.discard(str(Path(first["target_path"]).resolve()))
    second = manager.start("https://models.example/second.pt", filename="model.pt", connections=4)
    assert second["target_path"] != first["target_path"]
    assert segment.read_bytes() == b"first model bytes"


def test_recoverable_download_target_is_reserved_after_restart(monkeypatch, audit_download_manager):
    first = audit_download_manager.start("https://models.example/first.pt", filename="model.pt")
    first["status"] = "paused"
    db.upsert_json("downloads", first["id"], first)
    restarted = providers.DownloadManager()
    monkeypatch.setattr(restarted, "_start_worker", lambda *_: None)
    second = restarted.start("https://models.example/second.pt", filename="model.pt")
    assert second["target_path"] != first["target_path"]


def test_download_filename_handles_windows_reserved_device_names(audit_download_manager):
    job = audit_download_manager.start("https://models.example/model.pt", filename="CON.pt")
    assert Path(job["target_path"]).name != "CON.pt"
    Path(job["partial_path"]).write_bytes(b"synthetic")


@pytest.mark.skipif(os.name != "nt", reason="Windows filenames are case-insensitive")
def test_windows_download_targets_do_not_collide_by_letter_case(audit_download_manager):
    first = audit_download_manager.start("https://models.example/first.pt", filename="Model.pt")
    second = audit_download_manager.start("https://models.example/second.pt", filename="model.pt")
    assert Path(first["target_path"]) != Path(second["target_path"])


@pytest.mark.parametrize("action", ["cancel", "pause", "resume", "retry", "delete"])
def test_unknown_download_action_does_not_create_a_job_or_leave_flags(audit_download_manager, action):
    result = getattr(audit_download_manager, action)("missing-job")
    assert result["status"] == "not_found"
    assert db.list_json("downloads") == []
    assert not audit_download_manager.cancel_flags
    assert not audit_download_manager.pause_flags


@pytest.mark.parametrize("action", ["cancel", "pause", "resume", "retry", "delete"])
def test_unknown_download_endpoint_returns_404(action):
    client = TestClient(app)
    if action == "delete":
        response = client.delete("/api/models/downloads/missing-job")
    else:
        response = client.post(f"/api/models/downloads/missing-job/{action}")
    assert response.status_code == 404
    assert client.get("/api/models/downloads").json() == []


def test_chat_preserves_edits_made_while_waiting_for_provider(monkeypatch):
    client = TestClient(app)
    case = upload(client)

    def edit_during_chat(*args, **kwargs):
        latest = db.get_case(case["case_id"])
        latest["title"] = "Edited during chat"
        latest["chat_history"] = [{"role": "user", "content": "earlier concurrent message"}]
        db.save_case(latest)
        return {"content": "synthetic reply", "backend": "demo", "fallback": False}

    monkeypatch.setattr(routes, "chat_response", edit_during_chat)
    response = client.post(f"/api/chat/{case['case_id']}", json={"message": "test"})
    assert response.status_code == 200
    latest = client.get(f"/api/cases/{case['case_id']}").json()
    assert latest["title"] == "Edited during chat"
    assert [entry["content"] for entry in latest["chat_history"]] == ["earlier concurrent message", "test", "synthetic reply"]


def test_chat_does_not_resurrect_a_deleted_case(monkeypatch):
    client = TestClient(app)
    case = upload(client)

    def delete_during_chat(*args, **kwargs):
        db.delete_case(case["case_id"])
        return {"content": "synthetic reply", "backend": "demo", "fallback": False}

    monkeypatch.setattr(routes, "chat_response", delete_during_chat)
    assert client.post(f"/api/chat/{case['case_id']}", json={"message": "test"}).status_code == 404
    assert client.get(f"/api/cases/{case['case_id']}").status_code == 404


@pytest.mark.parametrize("fmt", ["json", "markdown", "pdf"])
def test_reports_for_different_images_do_not_overwrite_each_other(fmt):
    client = TestClient(app)
    case = upload(client)
    case = client.post(f"/api/cases/{case['case_id']}/images", files={"file": ("second.png", png("white"), "image/png")}).json()["case"]
    assert client.post(f"/api/analysis/{case['case_id']}").status_code == 200
    first_export = client.post(f"/api/reports/{case['case_id']}/export", json={"format": fmt, "language": "en"}).json()
    first_path = Path(first_export["path"])
    first_content = first_path.read_bytes()
    second_id = case["images"][1]["image_id"]
    client.post(f"/api/cases/{case['case_id']}/active-image", json={"image_id": second_id})
    assert client.post(f"/api/analysis/{case['case_id']}").status_code == 200
    second_export = client.post(f"/api/reports/{case['case_id']}/export", json={"format": fmt, "language": "en"}).json()
    assert second_export["path"] != str(first_path)
    assert first_path.read_bytes() == first_content


def test_runtime_invalid_input_keeps_existing_configuration():
    client = TestClient(app)
    original = client.get("/api/runtime").json()
    response = client.post("/api/runtime", json={**original, "temperature": 99})
    assert response.status_code == 400
    assert client.get("/api/runtime").json() == original
