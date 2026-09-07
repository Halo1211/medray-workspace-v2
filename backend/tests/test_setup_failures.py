import sqlite3
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.runtime.secrets import provider_key


def test_database_relocation_preserves_uncheckpointed_wal(tmp_path, monkeypatch):
    from app import config
    original = tmp_path / "source.sqlite3"
    target = tmp_path / "destination"
    with sqlite3.connect(original) as source:
        source.execute("PRAGMA journal_mode=WAL")
        source.execute("PRAGMA wal_autocheckpoint=0")
        source.execute("CREATE TABLE cases (title TEXT)")
        source.execute("INSERT INTO cases VALUES ('newest case')")
        source.commit()
        monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(db_path=original, data_dir=tmp_path))
        monkeypatch.setattr(config, "DATABASE_LOCATION_CONFIG", tmp_path / "location.json")
        config.set_database_folder(str(target))
        with sqlite3.connect(target / config.DATABASE_FILENAME) as destination:
            assert destination.execute("SELECT title FROM cases").fetchone()[0] == "newest case"


def test_invalid_database_relocation_cleans_up_target(tmp_path, monkeypatch):
    from app import config
    original = tmp_path / "corrupt.sqlite3"
    original.write_bytes(b"not a database")
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(db_path=original, data_dir=tmp_path))
    monkeypatch.setattr(config, "DATABASE_LOCATION_CONFIG", tmp_path / "location.json")
    with pytest.raises(sqlite3.DatabaseError):
        config.set_database_folder(str(tmp_path / "target"))
    assert not (tmp_path / "target" / config.DATABASE_FILENAME).exists()
    assert original.read_bytes() == b"not a database"


def test_database_locked_has_recovery_message(monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "list_cases", lambda *args, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("database locked token=secret")))
    response = TestClient(app).get("/api/cases")
    assert response.status_code == 503
    assert "database is busy" in response.json()["detail"]
    assert "secret" not in response.text


def test_invalid_runtime_is_human_readable():
    response = TestClient(app).post("/api/runtime", json={"primary_backend": "unsupported-adapter"})
    assert response.status_code == 400
    assert "fields are invalid" in response.json()["detail"]


def test_validation_error_never_echoes_a_credential():
    response = TestClient(app).post("/api/runtime/huggingface-token", json={"token": {"secret": "hf_private"}})
    assert response.status_code == 422
    assert "hf_private" not in response.text


def test_provider_key_is_bound_to_configured_endpoint():
    client = TestClient(app)
    client.post("/api/ai-setup/provider-key", json={"key": "private_key", "base_url": "https://provider.example/v1"})
    assert provider_key("https://provider.example/v1") == "private_key"
    assert provider_key("https://another.example/v1") == ""
    assert "private_key" not in client.get("/api/runtime").text


def test_missing_dependency_install_error_is_actionable(monkeypatch):
    from app.ai_setup import service
    monkeypatch.setattr(service, "dependencies", lambda: [{"name": "PyTorch", "status": "missing"}])
    monkeypatch.setattr(service, "install_dependencies", lambda: (_ for _ in ()).throw(RuntimeError("CPU dependency installation failed.")))
    service._setup("setup")
    result = service.read_state()
    assert result["status"] == "error" and not result["passed"]
    assert "retry" in result["detail"]


@pytest.mark.parametrize("filename", ["private-name.png", "private-name.dcm"])
def test_corrupt_image_upload_is_readable_and_leaves_no_case(filename):
    client = TestClient(app)
    before = client.get("/api/cases").json()
    response = client.post("/api/upload", files={"file": (filename, b"corrupted image bytes")})
    assert response.status_code == 400
    assert "Choose another image" in response.json()["detail"]
    assert "private-name" not in response.text
    assert client.get("/api/cases").json() == before


def test_failed_report_and_vision_hide_provider_exception_and_label_fallback(tmp_path, monkeypatch):
    import asyncio
    import json
    from PIL import Image
    from app.pipelines import analysis_pipeline as pipeline
    path = tmp_path / "synthetic.png"
    Image.new("L", (32, 32), 127).save(path)
    def fail(*args, **kwargs):
        raise RuntimeError("provider returned credential=private_fixture_key")
    monkeypatch.setattr(pipeline, "ollama_vision", fail)
    monkeypatch.setattr(pipeline, "build_ollama_report", fail)
    result = asyncio.run(pipeline.run_analysis("fixture", {"stored_path": str(path), "filename": "chest_pa.png", "width": 32, "height": 32}, backend="ollama", language="id", runtime_snapshot={"vision_language_model": "fixture", "report_model": "fixture", "ollama_base_url": "http://127.0.0.1:11434"}))
    assert "private_fixture_key" not in json.dumps(result)
    assert "Built-in Demo report fallback" in result["report"]["watermark"]
    assert any("Built-in Demo" in warning for warning in result["warnings"])


def test_model_test_keeps_safe_weight_recovery_reason(monkeypatch):
    from app.ai_setup import service
    monkeypatch.setattr(service, "_run_command", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout='{"status":"failed","detail":"Weights integrity check failed. Download the official weights again in AI Setup."}'))
    service._setup("test")
    assert service.read_state()["status"] == "error"
    assert "Weights integrity" in service.read_state()["detail"]
