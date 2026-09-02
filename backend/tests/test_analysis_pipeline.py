import asyncio

from PIL import Image

from app.medrax_adapter.interfaces import MedRaxTool
from app.pipelines.analysis_pipeline import _ollama_vision_prompt, _vlm_finding_label
from app.pipelines.analysis_pipeline import run_analysis


class _BrokenDemoTool(MedRaxTool):
    name = "BrokenDemoTool"
    task_type = "quality"

    async def run(self, context):
        raise RuntimeError("simulated tool failure")


def test_vlm_label_respects_cavitation_negation():
    text = (
        "Left upper-lobe opacity is present. No definite cavitation is seen. The image does not show evidence of "
        "cavitation/lucency, but the opacity could represent consolidation."
    )

    assert _vlm_finding_label(text) == "possible_left_upper_lung_airspace_opacity"


def test_ollama_prompt_contains_reference_calibration():
    prompt = _ollama_vision_prompt(body_region="Chest X-ray")

    assert "upper-lobe consolidation" in prompt
    assert "Only call cavitation" in prompt
    assert "focused on X-ray observations" in prompt
    assert "do not use absence or presence of tree-in-bud" in prompt


def test_ollama_prompt_supports_non_chest_xray_checklists():
    msk_prompt = _ollama_vision_prompt(body_region="MSK/orthopedic X-ray")
    abdomen_prompt = _ollama_vision_prompt(body_region="Abdomen X-ray")

    assert "adequacy/alignment, bones, cartilage/joint spaces" in msk_prompt
    assert "displacement/apposition" in msk_prompt
    assert "bowel gas pattern" in abdomen_prompt
    assert "free air" in abdomen_prompt


def test_pipeline_can_generate_english_report(tmp_path):
    image_path = tmp_path / "cxr.png"
    Image.new("L", (32, 32), color=120).save(image_path)

    result = asyncio.run(
        run_analysis(
            "case-english",
            {"stored_path": str(image_path), "filename": "cxr.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
            language="en",
        )
    )

    assert result["report"]["language"] == "en"
    assert result["report"]["indication"] == "Not provided."
    assert "Draf" not in result["report"]["impression"]
    assert result["report"]["technique"].startswith("Conventional radiograph")
    assert result["annotations"][0]["original_coordinate"] == result["annotations"][0]["coordinate"]
    assert result["annotations"][0]["original_state"]["label"] == "demo global review region"
    assert result["annotations"][0]["source_image_id"] == "cxr.png"


def test_pipeline_records_tool_failure_without_crashing(tmp_path, monkeypatch):
    import app.pipelines.analysis_pipeline as pipeline

    image_path = tmp_path / "cxr.png"
    Image.new("L", (32, 32), color=120).save(image_path)
    monkeypatch.setattr(pipeline, "demo_medrax_tools", lambda: [_BrokenDemoTool()])

    result = asyncio.run(
        run_analysis(
            "case-broken-tool",
            {"stored_path": str(image_path), "filename": "cxr.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
        )
    )

    failure = next(item for item in result["model_trace"] if item["model"] == "BrokenDemoTool")
    assert failure["stage"] == "quality"
    assert failure["status"] == "failed"
    assert failure["detail"] == "simulated tool failure"


def test_pipeline_uses_body_region_specific_fallback_for_orthopedic_xray(tmp_path):
    image_path = tmp_path / "wrist.png"
    Image.new("L", (32, 32), color=120).save(image_path)

    result = asyncio.run(
        run_analysis(
            "case-wrist",
            {"stored_path": str(image_path), "filename": "wrist.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
        )
    )

    reading = result["systematic_reading"]
    assert reading["body_region"] == "MSK/orthopedic X-ray"
    assert result["anatomy_route"]["profile_id"] == "msk"
    assert result["anatomy_route"]["anatomy"] == "wrist"
    assert "ABCs" in reading["alignment_anatomy"]
    assert "displacement/apposition" in reading["bone_joint"]


def test_pipeline_uses_body_region_specific_fallback_for_abdomen_xray(tmp_path):
    image_path = tmp_path / "kub.png"
    Image.new("L", (32, 32), color=120).save(image_path)

    result = asyncio.run(
        run_analysis(
            "case-kub",
            {"stored_path": str(image_path), "filename": "kub.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
        )
    )

    reading = result["systematic_reading"]
    assert reading["body_region"] == "Abdomen X-ray"
    assert "pola gas usus" in reading["abdomen"]
    assert "pneumoperitoneum" in reading["negative_important_findings"][0]


def test_pipeline_skips_chest_classifier_for_non_chest_xray(tmp_path):
    image_path = tmp_path / "wrist_ap.png"
    Image.new("L", (32, 32), color=120).save(image_path)

    result = asyncio.run(
        run_analysis(
            "case-wrist-classifier",
            {"stored_path": str(image_path), "filename": "wrist_ap.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
            runtime_snapshot={"classification_model": "torchxrayvision:densenet121-res224-all"},
        )
    )

    classifier_trace = next(item for item in result["model_trace"] if item["stage"] == "anatomy_classification")
    assert classifier_trace["status"] == "skipped"
    assert "not MSK / trauma" in classifier_trace["detail"]
    assert any("Chest classifier was not run" in warning for warning in result["warnings"])


def test_pipeline_tolerates_malformed_classifier_output(tmp_path, monkeypatch):
    import app.pipelines.analysis_pipeline as pipeline

    image_path = tmp_path / "chest_pa.png"
    Image.new("L", (32, 32), color=120).save(image_path)
    monkeypatch.setattr(
        pipeline,
        "run_torchxrayvision_classifier",
        lambda *args, **kwargs: {
            "status": "ok",
            "model": "torchxrayvision:densenet121-res224-all",
            "findings": "not-a-list",
            "warnings": "not-a-list",
        },
    )

    result = asyncio.run(run_analysis(
        "case-bad-classifier",
        {"stored_path": str(image_path), "filename": "chest_pa.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
        runtime_snapshot={"classification_model": "torchxrayvision:densenet121-res224-all"},
    ))

    classifier_trace = next(item for item in result["model_trace"] if item["stage"] == "anatomy_classification")
    assert classifier_trace["status"] == "failed"
    assert result["findings"][0]["label"] == "fallback_no_confirmed_abnormality"
    assert any("Classifier output was ignored" in warning for warning in result["warnings"])


def test_pipeline_converts_real_msk_detector_output_to_grounded_annotation(tmp_path, monkeypatch):
    import app.pipelines.analysis_pipeline as pipeline

    image_path = tmp_path / "wrist_ap.png"
    Image.new("L", (100, 80), color=120).save(image_path)
    monkeypatch.setattr(
        pipeline,
        "run_msk_fracture_detector",
        lambda *args, **kwargs: {
            "status": "ok",
            "model": "local:fracture-test",
            "weights": "best.pt",
            "detail": "one box",
            "detections": [{
                "label": "candidate fracture",
                "model_label": "fracture",
                "confidence": 0.81,
                "coordinate": {"x": 10, "y": 12, "width": 25, "height": 30},
            }],
            "original_width": 100,
            "original_height": 80,
            "model_input_width": 100,
            "model_input_height": 80,
            "warnings": ["research only"],
        },
    )

    result = asyncio.run(run_analysis(
        "case-msk-localization",
        {"stored_path": str(image_path), "filename": "wrist_ap.png", "width": 100, "height": 80, "metadata": {}, "hashes": {}},
        runtime_snapshot={"grounding_model": "local:fracture-test", "cpu_only": True, "localization_confidence_threshold": 0.25},
    ))

    annotation = result["annotations"][0]
    assert annotation["source"] == "model-returned coordinate"
    assert annotation["source_model"] == "local:fracture-test"
    assert annotation["coordinate"]["type"] == "grounding_box"
    assert annotation["coordinate"]["coordinate_space"] == "original_image"
    assert annotation["original_coordinate"] == annotation["coordinate"]
    assert result["findings"][0]["label"] == "candidate_fracture_localization"
    assert result["result_cards"][0]["annotation_refs"] == [annotation["id"]]
    assert any(item["stage"] == "msk_fracture_localization" and item["status"] == "ok" for item in result["model_trace"])


def test_pipeline_tolerates_malformed_detector_output(tmp_path, monkeypatch):
    import app.pipelines.analysis_pipeline as pipeline

    image_path = tmp_path / "wrist_ap.png"
    Image.new("L", (100, 80), color=120).save(image_path)
    monkeypatch.setattr(
        pipeline,
        "run_msk_fracture_detector",
        lambda *args, **kwargs: {
            "status": "ok",
            "model": "local:fracture-test",
            "detections": "not-a-list",
            "warnings": "not-a-list",
            "original_width": 100,
            "original_height": 80,
        },
    )

    result = asyncio.run(run_analysis(
        "case-bad-localization",
        {"stored_path": str(image_path), "filename": "wrist_ap.png", "width": 100, "height": 80, "metadata": {}, "hashes": {}},
        runtime_snapshot={"grounding_model": "local:fracture-test", "cpu_only": True},
    ))

    trace = next(item for item in result["model_trace"] if item["stage"] == "msk_fracture_localization")
    assert trace["status"] == "failed"
    assert result["annotations"][0]["source"] == "fallback heuristic"
    assert any("Detector output was ignored" in warning for warning in result["warnings"])


def test_pipeline_skips_msk_detector_for_chest(tmp_path, monkeypatch):
    import app.pipelines.analysis_pipeline as pipeline

    image_path = tmp_path / "chest_pa.png"
    Image.new("L", (32, 32), color=120).save(image_path)
    monkeypatch.setattr(pipeline, "run_msk_fracture_detector", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")))

    result = asyncio.run(run_analysis(
        "case-chest-localization-gate",
        {"stored_path": str(image_path), "filename": "chest_pa.png", "width": 32, "height": 32, "metadata": {}, "hashes": {}},
        runtime_snapshot={"grounding_model": "local:fracture-test"},
    ))

    trace = next(item for item in result["model_trace"] if item["stage"] == "msk_fracture_localization")
    assert trace["status"] == "skipped"
    assert any("MSK detector was not run" in warning for warning in result["warnings"])
