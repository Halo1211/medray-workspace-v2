import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ai_setup import routes, service
from app.ai_setup.catalog import TXRV_ID, CLASSIFIER_RECIPES, compatibility, weights_path
from app.model_finder import providers
from app.runtime import adapters
from app.runtime import secrets
from app.runtime.secrets import safe_error

client = TestClient(app)


@pytest.fixture
def no_dependencies(monkeypatch):
    monkeypatch.setattr(service, "dependencies", lambda: [{"name": "PyTorch", "module": "torch", "status": "missing"}])


def test_missing_dependency_never_ready(no_dependencies):
    status = service.xray_readiness()
    assert status["status"] == "dependency_missing"
    assert not status["ready_for_inference"]
    assert "PyTorch" in status["blocking_reasons"][0]
    assert client.post("/api/ai-setup/xray/activate").status_code == 400


def test_classifier_catalog_offers_easy_reviewed_alternatives():
    assert set(CLASSIFIER_RECIPES) >= {
        TXRV_ID,
        "torchxrayvision:densenet121-res224-nih",
        "torchxrayvision:densenet121-res224-chex",
        "torchxrayvision:densenet121-res224-rsna",
    }
    response = client.get("/api/ai-setup/classifiers")
    assert response.status_code == 200
    assert len(response.json()) >= 4
    assert all(item["automatic_setup"] for item in response.json())


def test_downloaded_and_importable_does_not_mean_ready(monkeypatch):
    monkeypatch.setattr(service, "dependencies", lambda: [])
    weights_path().write_bytes(b"weights")
    assert not service.xray_readiness()["ready_for_inference"]
    assert service.xray_readiness()["artifact_status"] == "downloaded"


def test_successful_test_activates_and_file_change_invalidates(monkeypatch):
    monkeypatch.setattr(service, "dependencies", lambda: [])
    weights_path().write_bytes(b"fixture")
    service.write_state(status="ready", passed=True, fingerprint=service.fingerprint())
    assert service.xray_readiness()["ready_for_inference"]
    assert client.post("/api/ai-setup/xray/activate").json()["classification_model"] == TXRV_ID
    weights_path().write_bytes(b"changed weights")
    assert not service.xray_readiness()["ready_for_inference"]
    assert client.post("/api/ai-setup/xray/activate").status_code == 400
    weights_path().unlink()
    assert not service.xray_readiness()["ready_for_inference"]


def test_setup_restart_is_recoverable():
    service.state_path().write_text(json.dumps({"status": "installing", "boot": "previous-process", "passed": True}))
    result = service.xray_readiness()
    assert result["status"] == "error"
    assert not result["ready_for_inference"]
    assert "interrupted" in result["detail"]


def test_no_arbitrary_setup_actions():
    assert client.post("/api/ai-setup/xray/pip-install-custom").status_code == 400


def test_hf_source_never_implies_runtime():
    detail = compatibility({"id": "hf:any/torchxrayvision-model", "library_name": "transformers", "files": ["model.safetensors"], "fit_percent": 100})
    assert detail["status"] == "configuration_required"
    assert not detail["recommended_files"]
    assert compatibility({"id": "github:mlmed/torchxrayvision"})["status"] == "supported"
    assert compatibility({"id": "starter:torchxrayvision"})["status"] == "supported"
    assert compatibility({"id": "hf:torchxrayvision/densenet121-res224-all"})["status"] == "supported"
    assert compatibility({"id": "hf:someone/densenet121-res224-all"})["status"] == "configuration_required"


def test_hf_token_masked_status_and_disconnect():
    token = "hf_private_fixture_do_not_export"
    saved = client.post("/api/runtime/huggingface-token", json={"token": token})
    assert saved.status_code == 200
    assert token not in saved.text
    assert token not in client.get("/api/runtime/huggingface").text
    assert token not in client.get("/api/runtime").text
    assert client.delete("/api/runtime/huggingface-token").json()["configured"] is False
    assert providers.load_huggingface_token() == ""


def test_hf_auth_checks_whoami_without_echoing_token(monkeypatch):
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return b'{"name":"fixture-user"}'
    def open_request(req, timeout):
        captured.append(req)
        return Response()
    monkeypatch.setattr(routes.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=open_request))
    result = client.post("/api/ai-setup/hf/test", json={"token": "hf_secret"})
    assert result.json()["ok"]
    assert captured[0].full_url == "https://huggingface.co/api/whoami-v2"
    assert captured[0].get_header("Authorization") == "Bearer hf_secret"
    assert "hf_secret" not in result.text


def test_github_auth_checks_user_without_echoing_token(monkeypatch):
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return b'{"login":"fixture-user"}'
    def open_request(req, timeout):
        captured.append(req)
        return Response()
    monkeypatch.setattr(routes.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=open_request))
    result = client.post("/api/ai-setup/github/test", json={"token": "github_secret"})
    assert result.json()["ok"]
    assert captured[0].full_url == "https://api.github.com/user"
    assert captured[0].get_header("Authorization") == "Bearer github_secret"
    assert "github_secret" not in result.text


@pytest.mark.parametrize("code", [401, 403, 429])
def test_hf_wrong_gated_expired_token_safe_error(monkeypatch, code):
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("https://example/?token=hf_secret", code, "hf_secret", {}, None)
    monkeypatch.setattr(routes.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=fail))
    result = client.post("/api/ai-setup/hf/test", json={"token": "hf_secret"})
    assert not result.json()["ok"]
    assert "hf_secret" not in result.text


def test_ollama_offline(monkeypatch):
    monkeypatch.setattr(adapters, "ollama_tags", lambda *_: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(adapters, "ollama_installed", lambda: True)
    result = client.get("/api/ai-setup/ollama").json()
    assert result["installed"] and not result["running"]
    assert result["models"] == []


def test_ollama_discovers_actual_models_without_guessing_vision(monkeypatch):
    monkeypatch.setattr(adapters, "ollama_tags", lambda *_: {"models": [{"name": "custom-model"}, "bad", {}]})
    result = service.ollama_status("http://127.0.0.1:11434")
    assert result["models"] == [{"name": "custom-model", "status": "needs_setup", "detail": "Installed. Test the selected task before use."}]


def test_cloud_discovery_requires_opt_in(monkeypatch):
    called = []
    monkeypatch.setattr(routes.urllib.request, "build_opener", lambda *_: called.append(True))
    result = client.post("/api/ai-setup/connection/models", json={"base_url": "https://cloud.example/v1"})
    assert result.status_code == 400 and not called


def test_compatible_model_discovery(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return b'{"data":[{"id":"local-a"},{"id":"local-b"},{},42]}'
    monkeypatch.setattr(routes.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=lambda *a, **k: Response()))
    result = client.post("/api/ai-setup/connection/models", json={"backend": "openai-compatible", "base_url": "http://127.0.0.1:1234/v1"})
    assert result.json()["models"] == [{"name": "local-a"}, {"name": "local-b"}]


def test_connection_activation_bound_to_test_config_and_key(monkeypatch):
    config = {"backend": "openai-compatible", "task": "chat", "base_url": "http://127.0.0.1:1234/v1", "model": "fixture", "allow_cloud": False}
    import time
    routes._tests["proof"] = {"status": "ready", "signature": routes._signature(config), "created_at": time.time()}
    assert client.post("/api/ai-setup/connection/activate", json={**config, "test_id": "proof"}).status_code == 200
    assert client.post("/api/ai-setup/connection/activate", json={**config, "model": "other", "test_id": "proof"}).status_code == 400
    client.post("/api/ai-setup/provider-key", json={"key": "private_key", "base_url": config["base_url"]})
    assert client.post("/api/ai-setup/connection/activate", json={**config, "test_id": "proof"}).status_code == 400
    assert "private_key" not in client.get("/api/runtime").text


def test_provider_keys_are_scoped_to_multiple_endpoints(tmp_path, monkeypatch):
    settings = SimpleNamespace(cache_dir=tmp_path, openai_base_url="", openai_api_key="")
    monkeypatch.setattr(secrets, "get_settings", lambda: settings)
    secrets.save_provider_key("key-a", "https://provider-a.example/v1")
    secrets.save_provider_key("key-b", "https://provider-b.example/v1")

    assert secrets.provider_key("https://provider-a.example/v1") == "key-a"
    assert secrets.provider_key("https://provider-b.example/v1") == "key-b"
    secrets.save_provider_key("", "https://provider-a.example/v1")
    assert secrets.provider_key("https://provider-a.example/v1") == ""
    assert secrets.provider_key("https://provider-b.example/v1") == "key-b"


def test_unknown_server_task_not_falsely_supported():
    with pytest.raises(ValueError, match="no implemented"):
        routes._connection({"backend": "openai-compatible", "task": "segmentation"})


@pytest.mark.parametrize("url", ["file:///secret", "http://key@localhost:8000/v1", "http://localhost/v1?key=secret", "http://localhost/v1#secret", "http://provider.example/v1"])
def test_invalid_server_address_rejected(url):
    with pytest.raises(RuntimeError):
        adapters.require_allowed_endpoint(url, True)


def test_local_import_no_execution_or_path_traversal():
    response = client.post("/api/ai-setup/local/import", files={"file": ("../../arbitrary.pt", b"not executable", "application/octet-stream")})
    assert response.status_code == 200
    artifact = response.json()["artifact"]
    assert Path(artifact["artifact_path"]).parent == service.get_settings().models_dir
    assert artifact["runtime_eligible"] is False
    assert client.post("/api/ai-setup/local/activate", json={"model_id": artifact["id"]}).status_code == 404
    assert client.post("/api/ai-setup/local/import", files={"file": ("script.py", b"raise Exception()")}).status_code == 400


def test_local_removal_archives_artifact_and_preserves_cases():
    artifact = client.post("/api/ai-setup/local/import", files={"file": ("test.pt", b"weights")}).json()["artifact"]
    before = client.get("/api/cases").json()
    assert client.post("/api/ai-setup/local/remove", json={"model_id": artifact["id"]}).status_code == 200
    assert not Path(artifact["artifact_path"]).exists()
    assert list((service.get_settings().models_dir / ".removed").iterdir())
    assert client.get("/api/cases").json() == before


@pytest.mark.parametrize("exc", [MemoryError("secret"), RuntimeError("CUDA out of memory token=secret"), PermissionError("secret"), OSError(28, "secret"), TimeoutError("secret")])
def test_failure_messages_do_not_expose_sensitive_exception_text(exc):
    assert "secret" not in safe_error(exc)


def test_connection_failure_and_invalid_output_never_ready(monkeypatch):
    config = {"backend": "openai-compatible", "task": "chat", "base_url": "http://127.0.0.1:1234/v1", "model": "fixture", "allow_cloud": False}
    routes._tests["failure"] = {"status": "testing"}
    monkeypatch.setattr(adapters, "openai_compatible_chat", lambda *args: "")
    routes._test_connection("failure", config)
    assert routes._tests["failure"]["status"] == "connection_failed"


@pytest.mark.parametrize("output,expected", [
    ('{"findings":"Test","impression":"Synthetic","recommendation":"Verify"}', "ready"),
    ('{"findings":[],"impression":"Synthetic","recommendation":"Verify"}', "connection_failed"),
    ("not a structured report", "connection_failed"),
])
def test_ollama_report_setup_checks_structured_output(monkeypatch, output, expected):
    monkeypatch.setattr(adapters, "ollama_tags", lambda *_: {"models": [{"name": "fixture"}]})
    monkeypatch.setattr(adapters, "ollama_chat", lambda *args: output)
    config = {"backend": "ollama", "task": "report", "base_url": "http://127.0.0.1:11434", "model": "fixture", "allow_cloud": False}
    routes._tests["report-test"] = {"status": "testing"}
    routes._test_connection("report-test", config)
    assert routes._tests["report-test"]["status"] == expected


def test_legacy_vision_list_does_not_claim_detected_ollama_is_tested(monkeypatch):
    from app.vision import registry
    monkeypatch.setattr(registry, "ollama_tags", lambda: {"models": [{"name": "fixture-vision"}]})
    candidate = next(item for item in registry.list_vision_adapters() if item["id"] == "fixture-vision")
    assert candidate["status"] == "needs_setup"
    assert not candidate["available"]


def test_advanced_preferences_are_bounded_and_persisted():
    response = client.post("/api/ai-setup/preferences", json={
        "temperature": 0.35,
        "top_p": 0.85,
        "seed": 42,
        "max_output_tokens": 2048,
        "request_timeout_seconds": 240,
        "max_retries": 2,
        "download_connections": 6,
        "annotation_auto_accept_threshold": 0.9,
    })
    assert response.status_code == 200
    assert response.json()["download_connections"] == 6
    assert response.json()["top_p"] == 0.85
    assert response.json()["seed"] == 42
    assert client.post("/api/ai-setup/preferences", json={"temperature": 9}).status_code == 422
    assert client.post("/api/ai-setup/preferences", json={"top_p": 0}).status_code == 422
    assert client.post("/api/ai-setup/preferences", json={"seed": -2}).status_code == 422
    assert client.post("/api/ai-setup/preferences", json={"download_connections": 99}).status_code == 422
