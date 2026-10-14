"""Connection setup regressions; all credentials and servers are synthetic."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.ai_setup import routes
from app.main import app
from app.runtime import secrets


client = TestClient(app)


def test_removing_one_provider_reports_its_status_without_removing_another():
    secrets.save_provider_key("test-a", "https://a.example/v1")
    secrets.save_provider_key("test-b", "https://b.example/v1")
    response = client.post("/api/ai-setup/provider-key", json={"key": "", "base_url": "https://a.example/v1"})
    assert response.status_code == 200
    assert response.json() == {"configured": False}
    assert secrets.provider_key("https://b.example/v1") == "test-b"


def test_key_status_is_scoped_and_does_not_expose_credentials():
    secrets.save_provider_key("synthetic-secret", "https://a.example/v1")
    for endpoint, configured in [("https://a.example/v1/", True), ("https://b.example/v1", False)]:
        response = client.get("/api/ai-setup/provider-key", params={"base_url": endpoint})
        assert response.status_code == 200
        assert response.json() == {"configured": configured}


@pytest.mark.parametrize("endpoint", ["", "not-a-url", "https://user:password@a.example/v1", "http://remote.example/v1"])
def test_key_status_rejects_invalid_server_addresses(endpoint):
    response = client.get("/api/ai-setup/provider-key", params={"base_url": endpoint})
    assert response.status_code == 400


@pytest.mark.parametrize("key", [None, 0, True, [], {}])
def test_invalid_key_input_cannot_clear_or_replace_a_saved_credential(key):
    endpoint = "https://a.example/v1"
    secrets.save_provider_key("previous-synthetic-key", endpoint)
    response = client.post("/api/ai-setup/provider-key", json={"key": key, "base_url": endpoint})
    assert response.status_code == 400
    assert secrets.provider_key(endpoint) == "previous-synthetic-key"


def test_missing_key_input_cannot_delete_credentials():
    endpoint = "https://a.example/v1"
    secrets.save_provider_key("previous-synthetic-key", endpoint)
    response = client.post("/api/ai-setup/provider-key", json={"base_url": endpoint})
    assert response.status_code == 400
    assert secrets.provider_key(endpoint) == "previous-synthetic-key"


@pytest.mark.parametrize("model", [None, 0, True, [], {}, "", "  "])
def test_invalid_model_names_are_rejected_before_starting_a_worker(monkeypatch, model):
    class UnexpectedThread:
        def __init__(self, **kwargs):
            pytest.fail("Invalid model name started a worker")
    monkeypatch.setattr(routes.threading, "Thread", UnexpectedThread)
    response = client.post("/api/ai-setup/connection/test", json={
        "backend": "ollama", "task": "chat", "base_url": "http://127.0.0.1:11434", "model": model,
    })
    assert response.status_code == 400


@pytest.mark.parametrize("fails", [False, True])
def test_worker_can_finish_after_its_test_has_expired(monkeypatch, fails):
    monkeypatch.setattr(routes, "_tests", {"expired": {"status": "testing"}})
    def reply(*args):
        with routes._test_lock:
            routes._tests.pop("expired")
        if fails:
            raise TimeoutError("Synthetic timeout")
        return "Hello"
    monkeypatch.setattr(routes.adapters, "openai_compatible_chat", reply)
    routes._test_connection("expired", {
        "backend": "openai-compatible", "task": "chat", "base_url": "http://127.0.0.1:1234/v1", "model": "test-model",
    })
    assert "expired" not in routes._tests


def test_concurrent_private_json_writes_leave_a_complete_document(tmp_path, monkeypatch):
    tmp_path = tmp_path / "keys"
    tmp_path.mkdir()
    path = tmp_path / "credentials.json"
    barrier = threading.Barrier(2)
    original_dump = secrets.json.dump
    def overlapping_dump(payload, stream):
        original_dump(payload, stream)
        stream.flush()
        barrier.wait(timeout=5)
    monkeypatch.setattr(secrets.json, "dump", overlapping_dump)
    payloads = [{"key": "a" * 10000}, {"key": "b"}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(secrets.private_json, path, payload) for payload in payloads]
        for future in futures:
            future.result(timeout=10)
    assert json.loads(path.read_text()) in payloads
    assert sorted(item.name for item in tmp_path.iterdir()) == [path.name]


def test_failed_private_write_keeps_existing_document_and_cleans_temporary_file(tmp_path, monkeypatch):
    tmp_path = tmp_path / "keys"
    tmp_path.mkdir()
    path = tmp_path / "credentials.json"
    path.write_text('{"key": "previous"}')
    def fail_dump(payload, stream):
        stream.write('{"partial":')
        raise OSError("Synthetic disk error")
    monkeypatch.setattr(secrets.json, "dump", fail_dump)
    with pytest.raises(OSError):
        secrets.private_json(path, {"key": "new"})
    assert json.loads(path.read_text()) == {"key": "previous"}
    assert sorted(item.name for item in tmp_path.iterdir()) == [path.name]


def test_concurrent_provider_updates_preserve_both_endpoints(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    original_write = secrets.private_json
    def paused_write(path, payload):
        if "https://a.example/v1" in payload and "https://b.example/v1" not in payload:
            entered.set()
            assert release.wait(timeout=5)
        original_write(path, payload)
    monkeypatch.setattr(secrets, "private_json", paused_write)
    def save_second():
        second_started.set()
        secrets.save_provider_key("test-b", "https://b.example/v1")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(secrets.save_provider_key, "test-a", "https://a.example/v1")
        assert entered.wait(timeout=5)
        second = pool.submit(save_second)
        assert second_started.wait(timeout=5)
        # Let the second writer reach the read/modify/write while the first is paused.
        second_done = threading.Event()
        second.add_done_callback(lambda _: second_done.set())
        second_done.wait(timeout=0.1)
        release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert secrets.provider_key("https://a.example/v1") == "test-a"
    assert secrets.provider_key("https://b.example/v1") == "test-b"
