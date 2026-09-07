"""Small protocol and routing checks; no model downloads or external services."""
import asyncio
import json
import time
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.ai_setup import routes
from app.runtime import adapters
from app.pipelines import analysis_pipeline as pipeline


def test_compatible_vision_sends_image_content_not_only_text(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.png"
    Image.new("L", (16, 16), 127).save(path)
    captured = []
    monkeypatch.setattr(adapters, "openai_compatible_chat", lambda messages, *args: captured.append(messages) or "Synthetic gray image")
    assert adapters.openai_compatible_vision(str(path), "Describe", "any-vlm", "http://localhost/v1", "")
    content = captured[0][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_compatible_server_runs_image_review_and_report_with_correct_provenance(tmp_path, monkeypatch):
    path = tmp_path / "chest.png"
    Image.new("L", (32, 32), 127).save(path)
    monkeypatch.setattr(pipeline, "openai_compatible_vision", lambda *args: "Synthetic test image; no clinical interpretation.")
    monkeypatch.setattr(pipeline, "openai_compatible_chat", lambda *args: json.dumps({"findings": "Gambar sintetis.", "impression": "Tidak untuk interpretasi klinis.", "recommendation": "Verifikasi dokter."}))
    result = asyncio.run(pipeline.run_analysis("test", {"stored_path": str(path), "filename": "chest.png", "width": 32, "height": 32}, backend="openai-compatible", language="id", runtime_snapshot={"vision_language_model": "custom-vlm", "report_model": "custom-report", "openai_base_url": "http://localhost:1234/v1"}))
    for stage in ("vision_language", "report_generation"):
        trace = next(item for item in result["model_trace"] if item["stage"] == stage)
        assert trace["backend"] == "openai-compatible" and trace["status"] == "ok"
    assert "openai-compatible" in result["report"]["watermark"]


def test_analysis_forwards_bounded_generation_controls_to_vision_and_report(tmp_path, monkeypatch):
    path = tmp_path / "chest.png"
    Image.new("L", (32, 32), 127).save(path)
    captured = []

    def fake_provider(*args, temperature, top_p, seed, max_output_tokens, timeout, max_retries):
        captured.append((temperature, top_p, seed, max_output_tokens, timeout, max_retries))
        if isinstance(args[0], str):
            return "Synthetic image candidate; verify clinically."
        return json.dumps({"findings": "Synthetic finding.", "impression": "Research candidate.", "recommendation": "Verify."})

    monkeypatch.setattr(pipeline, "openai_compatible_vision", fake_provider)
    monkeypatch.setattr(pipeline, "openai_compatible_chat", fake_provider)
    asyncio.run(pipeline.run_analysis(
        "controls", {"stored_path": str(path), "filename": "chest.png", "width": 32, "height": 32},
        backend="openai-compatible", language="en", anatomy_profile_override="chest",
        runtime_snapshot={
            "vision_language_model": "custom-vlm", "report_model": "custom-report",
            "openai_base_url": "http://localhost:1234/v1", "temperature": 0.35,
            "max_output_tokens": 4096, "request_timeout_seconds": 240, "max_retries": 3,
        },
    ))
    assert captured == [
        (0.35, 0.95, -1, 4096, 240, 3),
        (0.35, 0.95, -1, 4096, 240, 3),
    ]


def test_analysis_routes_vision_and_report_to_independent_provider_connections(tmp_path, monkeypatch):
    path = tmp_path / "multi-provider.png"
    Image.new("L", (32, 32), 127).save(path)
    calls = []

    def fake_vision(image_path, prompt, model, base_url, api_key, **options):
        calls.append(("vision", model, base_url))
        return "Synthetic image candidate; verify clinically."

    def fake_report(messages, model, base_url, api_key, **options):
        calls.append(("report", model, base_url))
        return json.dumps({"findings": "Synthetic finding.", "impression": "Research candidate.", "recommendation": "Verify."})

    monkeypatch.setattr(pipeline, "openai_compatible_vision", fake_vision)
    monkeypatch.setattr(pipeline, "openai_compatible_chat", fake_report)
    asyncio.run(pipeline.run_analysis(
        "multi-provider", {"stored_path": str(path), "filename": "multi-provider.png", "width": 32, "height": 32},
        backend="openai-compatible", language="en", anatomy_profile_override="chest",
        runtime_snapshot={
            "primary_backend": "openai-compatible",
            "vision_language_model": "vision-a",
            "report_model": "report-b",
            "openai_base_url": "http://localhost:9999/v1",
            "task_connections": {
                "vision": {"backend": "openai-compatible", "model": "vision-a", "base_url": "http://localhost:1234/v1", "allow_cloud": False},
                "report": {"backend": "openai-compatible", "model": "report-b", "base_url": "http://localhost:1337/v1", "allow_cloud": False},
            },
        },
    ))

    assert calls == [
        ("vision", "vision-a", "http://localhost:1234/v1"),
        ("report", "report-b", "http://localhost:1337/v1"),
    ]


def test_cloud_image_review_does_not_send_without_opt_in(tmp_path, monkeypatch):
    path = tmp_path / "chest.png"
    Image.new("L", (16, 16), 127).save(path)
    called = []
    monkeypatch.setattr(pipeline, "openai_compatible_vision", lambda *args: called.append(True))
    asyncio.run(pipeline.run_analysis("test", {"stored_path": str(path), "filename": "chest.png", "width": 16, "height": 16}, backend="openai-compatible", runtime_snapshot={"vision_language_model": "model", "openai_base_url": "https://provider.example/v1", "allow_cloud": False}))
    assert not called


def test_each_task_keeps_its_independently_tested_provider_assignment():
    client = TestClient(app)
    vision = {"backend": "openai-compatible", "task": "vision", "model": "local-vlm", "base_url": "http://localhost:1234/v1", "allow_cloud": False}
    chat = {"backend": "openai-compatible", "task": "chat", "model": "local-chat", "base_url": "http://localhost:1337/v1", "allow_cloud": False}
    routes._tests["vision-provider"] = {"status": "ready", "created_at": time.time(), "signature": routes._signature(vision)}
    routes._tests["chat-provider"] = {"status": "ready", "created_at": time.time(), "signature": routes._signature(chat)}

    assert client.post("/api/ai-setup/connection/activate", json={**vision, "test_id": "vision-provider"}).status_code == 200
    result = client.post("/api/ai-setup/connection/activate", json={**chat, "test_id": "chat-provider"})

    assert result.status_code == 200
    runtime = result.json()
    assert runtime["vision_language_model"] == "local-vlm"
    assert runtime["chat_model"] == "local-chat"
    assert runtime["task_connections"]["vision"]["base_url"] == "http://localhost:1234/v1"
    assert runtime["task_connections"]["chat"]["base_url"] == "http://localhost:1337/v1"


def test_preferences_cannot_replace_connection_or_assign_unknown_models():
    client = TestClient(app)
    original = client.get("/api/runtime").json()
    saved = client.post("/api/ai-setup/preferences", json={"cpu_only": True, "chest_xray_model": "disabled"})
    assert saved.status_code == 200
    assert saved.json()["openai_base_url"] == original["openai_base_url"]
    assert client.post("/api/ai-setup/preferences", json={"allow_cloud": True}).status_code == 400
    assert client.post("/api/ai-setup/preferences", json={"chest_xray_model": "untested-model"}).status_code == 400


def test_preferences_accept_a_bounded_localization_threshold():
    client = TestClient(app)
    saved = client.post("/api/ai-setup/preferences", json={"localization_confidence_threshold": 0.4})
    assert saved.status_code == 200
    assert saved.json()["localization_confidence_threshold"] == 0.4
    assert client.post("/api/ai-setup/preferences", json={"localization_confidence_threshold": -0.1}).status_code == 400
    assert client.post("/api/ai-setup/preferences", json={"localization_confidence_threshold": 1.1}).status_code == 400


def test_preferences_accept_only_known_review_depths():
    client = TestClient(app)
    assert client.post("/api/ai-setup/preferences", json={"review_depth": "thorough"}).json()["review_depth"] == "thorough"
    assert client.post("/api/ai-setup/preferences", json={"review_depth": "unlimited"}).status_code == 400


def test_ai_setup_overview_backfills_new_runtime_defaults():
    runtime = TestClient(app).get("/api/ai-setup").json()["runtime"]
    assert runtime["review_depth"] in {"focused", "balanced", "thorough"}


def test_demo_chat_never_sends_context_to_configured_provider(monkeypatch):
    from app.models.schemas import RuntimeConfig
    monkeypatch.setattr(adapters, "openai_compatible_chat", lambda *args: (_ for _ in ()).throw(AssertionError("Unexpected transmission")))
    result = adapters.chat_response("hello", [], RuntimeConfig(primary_backend="openai-compatible"), {})
    assert result["backend"] == "demo"
