import asyncio
import json

from PIL import Image

from app.models.schemas import RuntimeConfig
from app.pipelines import analysis_pipeline as pipeline


def test_runtime_review_depth_is_bounded():
    assert RuntimeConfig(review_depth="focused").review_depth == "focused"
    assert RuntimeConfig(review_depth="thorough").review_depth == "thorough"


def test_quality_and_fallback_reading_follow_language(tmp_path):
    path = tmp_path / "dark.png"
    Image.new("L", (16, 16), 5).save(path)
    english_quality = pipeline.quality_from_image(str(path), "en")
    indonesian_quality = pipeline.quality_from_image(str(path), "id")
    assert "dark" in english_quality.limitations[0].lower()
    assert "gelap" in indonesian_quality.limitations[0].lower()
    assert "non-diagnostic" in pipeline.systematic_template("Chest X-ray", english_quality, "", "en").final_impression.lower()
    assert "non-diagnostik" in pipeline.systematic_template("Chest X-ray", indonesian_quality, "", "id").final_impression


def test_vision_prompt_language_depth_and_annotation_contract():
    prompt = pipeline._ollama_vision_prompt("", "Chest X-ray", language="en", review_depth="thorough")
    assert "Respond entirely in English" in prompt
    assert "thorough review" in prompt.lower()
    assert "MEDRAY_ANNOTATIONS_JSON" in prompt
    assert "normalized 0-1000" in prompt


def test_chat_authored_annotation_payload_is_parsed_and_scaled():
    response = 'Findings: synthetic opacity.\nMEDRAY_ANNOTATIONS_JSON: {"annotations":[{"label":"candidate opacity","confidence":0.73,"box":[100,200,600,800]}]}'
    annotations = pipeline._vlm_annotations_from_text(response, width=200, height=100, model="synthetic-chat-vlm", source_image_id="img-1", language="en")
    assert len(annotations) == 1
    annotation = annotations[0]
    assert (annotation.coordinate.x, annotation.coordinate.y, annotation.coordinate.width, annotation.coordinate.height) == (20, 20, 100, 60)
    assert annotation.review_status == "unreviewed"
    assert "unvalidated" in annotation.explanation.lower()


def test_vlm_annotation_parser_rejects_invalid_or_unstructured_coordinates():
    assert pipeline._vlm_annotations_from_text("possible lesion at left base", 100, 100, "model", "img", "en") == []
    bad = 'MEDRAY_ANNOTATIONS_JSON: {"annotations":[{"label":"x","confidence":2,"box":[0,0,1001,10]}]}'
    assert pipeline._vlm_annotations_from_text(bad, 100, 100, "model", "img", "en") == []


def test_external_report_model_runs_in_english_and_sets_language(tmp_path, monkeypatch):
    path = tmp_path / "study.png"
    Image.new("L", (32, 32), 127).save(path)
    prompts = []
    monkeypatch.setattr(pipeline, "openai_compatible_vision", lambda *_args: 'No definite focal abnormality.\nMEDRAY_ANNOTATIONS_JSON: {"annotations":[]}')
    monkeypatch.setattr(pipeline, "openai_compatible_chat", lambda messages, *_args: prompts.append(messages[-1]["content"]) or json.dumps({"findings": "No definite focal abnormality.", "impression": "Non-diagnostic draft.", "recommendation": "Qualified physician review."}))
    result = asyncio.run(pipeline.run_analysis(
        "case", {"stored_path": str(path), "filename": "study.png", "width": 32, "height": 32},
        backend="openai-compatible", language="en",
        runtime_snapshot={"vision_language_model": "vlm", "report_model": "report", "openai_base_url": "http://localhost:1234/v1", "review_depth": "thorough"},
    ))
    assert result["report"]["language"] == "en"
    assert any("Write an English" in prompt for prompt in prompts)
    assert result["warnings"][0].startswith("Research")


def test_chat_authored_annotation_survives_the_analysis_pipeline(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.png"
    Image.new("L", (200, 100), 127).save(path)
    response = 'Findings: synthetic candidate only.\nMEDRAY_ANNOTATIONS_JSON: {"annotations":[{"label":"synthetic candidate","confidence":0.73,"box":[100,200,600,800]}]}'
    monkeypatch.setattr(pipeline, "openai_compatible_vision", lambda *_args: response)
    result = asyncio.run(pipeline.run_analysis(
        "annotation-case", {"stored_path": str(path), "filename": "chest.png", "width": 200, "height": 100, "source_image_id": "image-1"},
        backend="openai-compatible", language="en",
        runtime_snapshot={"vision_language_model": "synthetic-chat-vlm", "report_model": "demo-report-generator", "openai_base_url": "http://localhost:1234/v1"},
    ))
    model_annotations = [item for item in result["annotations"] if item["source"] == "model-returned coordinate"]
    assert len(model_annotations) == 1
    assert model_annotations[0]["source_image_id"] == "image-1"
    assert model_annotations[0]["coordinate"]["width"] == 100
