import io
import hashlib
import threading
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
import pytest
from app.model_finder import providers
from app.config import get_settings
from app.storage.db import upsert_json


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


@pytest.fixture
def manager(monkeypatch):
    manager = providers.DownloadManager()
    monkeypatch.setattr(providers, "_validate_manual_download_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "_start_worker", lambda *_: None)
    return manager


def run_response(monkeypatch, manager, response, partial=b""):
    job = manager.start("https://models.example/model.pt")
    if partial:
        from pathlib import Path
        Path(job["partial_path"]).write_bytes(partial)
    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=lambda *args, **kwargs: response))
    manager._run(job["id"])
    return job


def test_resume_server_ignores_range_restarts_file(monkeypatch, manager):
    job = run_response(monkeypatch, manager, Response(b"abcdef", headers={"Accept-Ranges": "bytes", "Content-Length": "6"}), b"abc")
    from pathlib import Path
    assert job["status"] == "completed", job.get("error")
    assert Path(job["target_path"]).read_bytes() == b"abcdef"


def test_valid_resume_appends_only_remaining_bytes(monkeypatch, manager):
    job = run_response(monkeypatch, manager, Response(b"def", 206, {"Content-Range": "bytes 3-5/6", "Content-Length": "3"}), b"abc")
    from pathlib import Path
    assert job["status"] == "completed"
    assert Path(job["target_path"]).read_bytes() == b"abcdef"


@pytest.mark.parametrize("headers", [{"Content-Range": "bytes 0-2/6", "Content-Length": "3"}, {"Content-Range": "bad", "Content-Length": "3"}])
def test_invalid_resume_never_promoted(monkeypatch, manager, headers):
    job = run_response(monkeypatch, manager, Response(b"def", 206, headers), b"abc")
    assert job["status"] == "failed"


def test_truncated_response_never_completed(monkeypatch, manager):
    job = run_response(monkeypatch, manager, Response(b"short", headers={"Content-Length": "99"}))
    assert job["status"] == "failed" and job["retryable"]


def test_insufficient_disk_fails_before_write(monkeypatch, manager):
    monkeypatch.setattr(providers.shutil, "disk_usage", lambda *_: SimpleNamespace(free=0))
    job = run_response(monkeypatch, manager, Response(b"model", headers={"Content-Length": "5"}))
    assert job["status"] == "failed" and "disk space" in job["error"]


def test_duplicate_active_download_reuses_job(manager):
    first = manager.start("https://models.example/model.pt")
    second = manager.start("https://models.example/model.pt")
    assert first["id"] == second["id"]


def test_restart_reconciles_interrupted_jobs():
    root = get_settings().models_dir
    upsert_json("downloads", "old", {"id": "old", "status": "downloading", "target_path": str(root / "old.pt"), "partial_path": str(root / "old.pt.part")})
    job = providers.DownloadManager().list()[0]
    assert job["status"] == "paused" and job["retryable"]


def test_redirect_does_not_forward_source_token(monkeypatch):
    providers.save_huggingface_token("hf_private")
    monkeypatch.setattr(providers, "_validate_manual_download_url", lambda *a, **k: None)
    req = urllib.request.Request("https://huggingface.co/file", headers={"Authorization": "Bearer hf_private"})
    redirected = providers._SafeDownloadRedirectHandler().redirect_request(req, None, 302, "Found", {}, "https://cdn.example/file?signature=value")
    assert redirected.get_header("Authorization") is None


def test_user_url_cannot_persist_a_token(monkeypatch):
    with pytest.raises(ValueError, match="credentials"):
        providers._validate_manual_download_url("https://models.example/file?token=secret")


def test_real_segmented_range_download_and_checksum(tmp_path, monkeypatch):
    payload = bytes(range(256)) * 8192
    ranges = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            value = self.headers.get("Range")
            if value:
                start_text, end_text = value.removeprefix("bytes=").split("-", 1)
                start = int(start_text)
                end = int(end_text) if end_text else len(payload) - 1
                ranges.append((start, end))
                body = payload[start:end + 1]
                self.send_response(206)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
            else:
                body = payload
                self.send_response(200)
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    manager = providers.DownloadManager()
    monkeypatch.setattr(providers, "_validate_manual_download_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "_start_worker", lambda *_: None)
    monkeypatch.setattr(providers, "get_settings", lambda: SimpleNamespace(models_dir=tmp_path, cache_dir=tmp_path))
    try:
        digest = hashlib.sha256(payload).hexdigest()
        job = manager.start(f"http://127.0.0.1:{server.server_port}/model.bin", connections=4, checksum_sha256=digest)
        manager._run(job["id"])
    finally:
        server.shutdown()
        server.server_close()

    assert job["status"] == "completed", job.get("error")
    assert job["transfer_mode"] == "segmented"
    assert job["connections_used"] == 4
    assert job["checksum_status"] == "verified"
    assert open(job["target_path"], "rb").read() == payload
    assert len(ranges) >= 5  # one capability probe plus four payload segments
