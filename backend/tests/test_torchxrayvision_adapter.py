import asyncio

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.pipelines.analysis_pipeline import run_analysis
from app.vision.registry import list_vision_adapters
from app.vision.torchxrayvision_classifier import is_torchxrayvision_model, parse_weights


def test_torchxrayvision_model_id_helpers():
    assert is_torchxrayvision_model("torchxrayvision:densenet121-res224-all")
    assert not is_torchxrayvision_model("demo-classifier")
    assert parse_weights("torchxrayvision:densenet121-res224-chex") == "densenet121-res224-chex"
    assert parse_weights(None) == "densenet121-res224-all"


def test_pipeline_uses_torchxrayvision_classifier_when_configured(tmp_path, monkeypatch):
    image_path = tmp_path / "cxr.png"
    Image.new("L", (32, 32), color=120).save(image_path)

    def fake_classifier(image_path_arg, model_id):
        assert image_path_arg == str(image_path)
        assert model_id == "torchxrayvision:densenet121-res224-all"
        return {
            "status": "ok",
            "model": model_id,
            "findings": [
                {
                    "label": "txrv_cardiomegaly",
                    "description": "Research classifier signal for Cardiomegaly. This is not a diagnosis.",
                    "confidence": 0.71,
                    "probability": 0.71,
                    "evidence": ["TorchXRayVision weights=densenet121-res224-all"],
                    "status": "positive",
                }
            ],
            "warnings": ["classifier calibration warning"],
            "detail": "fake classifier result",
        }

    import app.pipelines.analysis_pipeline as pipeline

    monkeypatch.setattr(pipeline, "run_torchxrayvision_classifier", fake_classifier)
    result = asyncio.run(
        run_analysis(
            "case-txrv",
            {"stored_path": str(image_path), "filename": "cxr.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}, "source_image_id": "study-image-2", "source_image_index": 1, "source_series_id": "series-b", "source_view": "lateral"},
            backend="huggingface-local",
            runtime_snapshot={"classification_model": "torchxrayvision:densenet121-res224-all", "primary_backend": "huggingface-local"},
        )
    )

    assert result["findings"][0]["label"] == "txrv_cardiomegaly"
    assert result["findings"][0]["probability"] == 0.71
    assert result["result_cards"][0]["finding"] == "txrv_cardiomegaly"
    assert result["result_cards"][0]["candidate_diagnosis"] == "AI candidate diagnosis: cardiomegaly"
    assert result["result_cards"][0]["review_status"] == "unreviewed"
    assert result["result_cards"][0]["source_image_ids"] == ["study-image-2"]
    assert result["result_cards"][0]["source_series_ids"] == ["series-b"]
    assert result["result_cards"][0]["source_views"] == ["lateral"]
    assert result["input"]["source_image_id"] == "study-image-2"
    assert result["input"]["source_image_index"] == 1
    assert any(item["model"] == "torchxrayvision:densenet121-res224-all" and item["status"] == "ok" for item in result["model_trace"])
    assert "classifier calibration warning" in result["warnings"]


def test_pipeline_uses_ollama_vision_when_configured(tmp_path, monkeypatch):
    image_path = tmp_path / "cxr.png"
    Image.new("L", (32, 32), color=120).save(image_path)

    import app.pipelines.analysis_pipeline as pipeline

    def fake_vision(image_path_arg, prompt, model, base_url):
        assert image_path_arg == str(image_path)
        assert "chest X-ray" in prompt
        assert model == "qwen2.5vl:7b"
        assert base_url == "http://127.0.0.1:11434"
        return "Findings: candidate left upper-zone opacity. Impression: possible infection; verify clinically."

    monkeypatch.setattr(pipeline, "ollama_vision", fake_vision)
    result = asyncio.run(
        run_analysis(
            "case-ollama-vlm",
            {"stored_path": str(image_path), "filename": "cxr.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
            backend="ollama",
            runtime_snapshot={
                "primary_backend": "ollama",
                "vision_language_model": "qwen2.5vl:7b",
                "ollama_base_url": "http://127.0.0.1:11434",
            },
        )
    )

    assert result["findings"][0]["label"] == "possible_left_upper_lung_airspace_opacity"
    assert "candidate left upper-zone opacity" in result["report"]["impression"]
    assert any(item["stage"] == "vision_language" and item["status"] == "ok" for item in result["model_trace"])
    assert any("Ollama VLM aktif" in warning for warning in result["warnings"])


def test_vision_adapter_registry_and_endpoint_shape():
    adapters = list_vision_adapters()
    res = TestClient(app).get("/api/runtime/vision-adapters")
    txrv = next(item for item in adapters if item["id"] == "torchxrayvision:densenet121-res224-all")

    assert adapters[0]["id"] == "torchxrayvision:densenet121-res224-all"
    assert txrv["runtime_field"] == "classification_model"
    assert "safety_note" in txrv
    assert res.status_code == 200
    assert res.json()[0]["model_card_id"] == "torchxrayvision:densenet121-res224-all"


def test_vision_adapter_registry_tolerates_malformed_ollama_tags(monkeypatch):
    import app.vision.registry as registry

    monkeypatch.setattr(
        registry,
        "ollama_tags",
        lambda: {
            "models": [
                "not-a-model",
                {"name": "llava:latest", "capabilities": "not-a-list"},
                {"name": "", "capabilities": ["vision"]},
            ]
        },
    )

    adapters = registry.list_vision_adapters()

    assert any(item["id"] == "llava:latest" for item in adapters)
