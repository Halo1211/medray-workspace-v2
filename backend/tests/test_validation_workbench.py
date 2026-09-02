from fastapi.testclient import TestClient

from app.main import app
from app.validation.workbench import _quality_result, curated_sample_fixture, delete_validation_label, label_path, run_validation, save_validation_label, write_curated_sample_fixture


def test_validation_label_save_and_run_missing_case(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)

    saved = save_validation_label(
        {
            "case_id": "missing-case",
            "title": "Missing case",
            "dataset_name": "unit test fixture",
            "expected_body_region": "Chest X-ray",
            "expected_image_quality": {"diagnostic_quality": "adequate", "limitations": ["portable"]},
            "expected_findings": [{"label": "fallback_no_confirmed_abnormality", "status": "uncertain"}],
            "expected_annotations": [{"label": "support device", "coordinate_type": "bbox", "required": False}],
        }
    )
    result = run_validation()

    assert saved["label"]["case_id"] == "missing-case"
    assert saved["label"]["dataset_name"] == "unit test fixture"
    assert result["schema_version"] == "0.4.0"
    assert result["metrics"]["label_count"] == 1
    assert result["metrics"]["skipped_missing_case"] == 1
    assert result["evaluation_status"] == "research_only_not_clinical_performance"
    assert result["dataset_summary"]["dataset_names"] == ["unit test fixture"]
    assert "failure_cases" in result
    assert result["false_alert_burden"]["false_alert_count"] == 0
    assert result["missed_reference_summary"]["missed_reference_count"] == 0
    assert result["model_card_evidence_draft"]["protocol_id"] == "local-research-protocol"
    assert result["model_card_evidence_draft"]["evidence_scope"] == "local_research_prototype_only"

    deleted = delete_validation_label("missing-case")
    assert deleted["deleted"] is True


def test_curated_sample_fixture_writes_to_validation_fixture_dir(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)

    fixture = curated_sample_fixture()
    written = write_curated_sample_fixture()

    assert fixture["schema_version"] == "0.4.0"
    assert len(fixture["labels"]) >= 2
    assert written["path"].endswith("curated_sample_labels.json")
    assert (tmp_path / "fixtures" / "curated_sample_labels.json").exists()


def test_validation_label_paths_do_not_collide_after_sanitization(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)

    first = save_validation_label({"case_id": "case/a", "title": "Slash"})
    second = save_validation_label({"case_id": "casea", "title": "Plain"})

    assert label_path("case/a") != label_path("casea")
    assert first["path"] != second["path"]
    assert len(list((tmp_path / "labels").glob("*.json"))) == 2


def test_validation_quality_match_uses_predicted_quality_not_payload_presence():
    adequate = _quality_result(
        {"expected_image_quality": {"diagnostic_quality": "adequate", "limitations": []}},
        {"image_quality": {"score": 0.8, "limitations": []}},
    )
    limited = _quality_result(
        {"expected_image_quality": {"diagnostic_quality": "adequate", "limitations": []}},
        {"image_quality": {"score": 0.4, "limitations": ["Low contrast"]}},
    )
    missing = _quality_result(
        {"expected_image_quality": {"diagnostic_quality": "adequate", "limitations": []}},
        {"image_quality": {}},
    )

    assert adequate["predicted"] == "adequate"
    assert adequate["matched"] is True
    assert limited["predicted"] == "limited"
    assert limited["matched"] is False
    assert missing["predicted"] == "unknown"
    assert missing["matched"] is None


def test_validation_reports_result_card_agreement(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        workbench,
        "get_case",
        lambda case_id: {
            "case_id": case_id,
            "title": "Local analyzed case",
            "analysis": {
                "systematic_reading": {"body_region": "Chest X-ray"},
                "image_quality": {"score": 0.7, "limitations": []},
                "findings": [{"label": "txrv_cardiomegaly", "status": "positive"}],
                "result_cards": [{"id": "result-1-txrv-cardiomegaly", "finding": "txrv_cardiomegaly", "status": "positive", "review_status": "accepted"}],
                "annotations": [],
                "warnings": [],
                "model_trace": [],
            },
        },
    )

    save_validation_label(
        {
            "case_id": "case-with-card",
            "expected_body_region": "Chest X-ray",
            "expected_findings": [{"label": "txrv_cardiomegaly", "status": "positive"}],
        }
    )
    result = run_validation()

    assert result["metrics"]["result_card_agreements"] == 1
    assert result["metrics"]["result_card_agreement_rate"] == 1
    assert result["results"][0]["result_card_matches"][0]["review_status"] == "accepted"


def test_validation_reports_box_iou_and_localization_hit(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        workbench,
        "get_case",
        lambda case_id: {
            "case_id": case_id,
            "title": "MSK localization case",
            "analysis": {
                "systematic_reading": {"body_region": "MSK/orthopedic X-ray"},
                "image_quality": {"score": 0.8, "limitations": []},
                "findings": [],
                "result_cards": [],
                "annotations": [{
                    "label": "candidate fracture localization",
                    "coordinate": {"type": "grounding_box", "x": 10, "y": 10, "width": 20, "height": 20},
                }],
                "warnings": [],
                "model_trace": [],
            },
        },
    )
    save_validation_label({
        "case_id": "msk-box-case",
        "expected_body_region": "MSK/orthopedic X-ray",
        "expected_annotations": [{
            "label": "candidate fracture localization",
            "coordinate_type": "grounding_box",
            "required": True,
            "coordinate": {"x": 12, "y": 12, "width": 20, "height": 20},
            "min_iou": 0.5,
        }],
    })

    result = run_validation()

    check = result["results"][0]["annotation_checks"][0]
    assert check["best_iou"] == 0.6807
    assert check["localization_hit"] is True
    assert result["metrics"]["spatial_box_checks"] == 1
    assert result["metrics"]["box_hit_rate"] == 1
    assert result["metrics"]["mean_best_iou"] == 0.681


def test_validation_uses_reviewed_case_annotations_before_stale_analysis_copy(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        workbench,
        "get_case",
        lambda case_id: {
            "case_id": case_id,
            "title": "Reviewed MSK localization case",
            "annotations": [{
                "id": "ann-1",
                "label": "candidate fracture localization",
                "review_status": "accepted",
                "coordinate": {"type": "grounding_box", "x": 12, "y": 12, "width": 20, "height": 20},
            }],
            "analysis": {
                "systematic_reading": {"body_region": "MSK/orthopedic X-ray"},
                "image_quality": {"score": 0.8, "limitations": []},
                "findings": [],
                "result_cards": [],
                "annotations": [{
                    "id": "ann-1",
                    "label": "candidate fracture localization",
                    "review_status": "unreviewed",
                    "coordinate": {"type": "grounding_box", "x": 200, "y": 200, "width": 20, "height": 20},
                }],
                "warnings": [],
                "model_trace": [],
            },
        },
    )
    save_validation_label({
        "case_id": "reviewed-msk-box-case",
        "expected_body_region": "MSK/orthopedic X-ray",
        "expected_annotations": [{
            "label": "candidate fracture localization",
            "coordinate_type": "grounding_box",
            "required": True,
            "coordinate": {"x": 12, "y": 12, "width": 20, "height": 20},
            "min_iou": 0.5,
        }],
    })

    result = run_validation()

    check = result["results"][0]["annotation_checks"][0]
    assert check["best_iou"] == 1
    assert check["localization_hit"] is True


def test_validation_tolerates_malformed_annotation_collections(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        workbench,
        "get_case",
        lambda case_id: {
            "case_id": case_id,
            "title": "Malformed annotations case",
            "annotations": "not-a-list",
            "analysis": {
                "systematic_reading": {"body_region": "MSK/orthopedic X-ray"},
                "image_quality": {"score": 0.8, "limitations": []},
                "findings": [],
                "result_cards": [],
                "annotations": "not-a-list",
                "warnings": [],
                "model_trace": [],
            },
        },
    )
    save_validation_label({
        "case_id": "malformed-annotation-case",
        "expected_body_region": "MSK/orthopedic X-ray",
        "expected_annotations": [{
            "label": "candidate fracture localization",
            "coordinate_type": "grounding_box",
            "required": True,
            "coordinate": {"x": 12, "y": 12, "width": 20, "height": 20},
            "min_iou": 0.5,
        }],
    })

    result = run_validation()

    check = result["results"][0]["annotation_checks"][0]
    assert check["matched"] is False
    assert check["candidate_count"] == 0


def test_validation_tolerates_malformed_analysis_collections(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        workbench,
        "get_case",
        lambda case_id: {
            "case_id": case_id,
            "title": "Malformed analysis case",
            "analysis": {
                "systematic_reading": {"body_region": "Chest X-ray"},
                "image_quality": {"score": 0.8, "limitations": "portable"},
                "findings": "not-a-list",
                "result_cards": "not-a-list",
                "annotations": "not-a-list",
                "warnings": "not-a-list",
                "model_trace": "not-a-list",
            },
        },
    )
    save_validation_label({
        "case_id": "malformed-analysis-case",
        "expected_body_region": "Chest X-ray",
        "expected_image_quality": {"diagnostic_quality": "adequate", "limitations": ["portable"]},
        "expected_findings": [{"label": "txrv_cardiomegaly", "status": "positive"}],
        "expected_annotations": [{
            "label": "candidate fracture localization",
            "coordinate_type": "grounding_box",
            "required": True,
            "coordinate": {"x": 12, "y": 12, "width": 20, "height": 20},
            "min_iou": 0.5,
        }],
    })

    result = run_validation()
    case_result = result["results"][0]

    assert case_result["matches"][0]["predicted_status"] == "not_predicted"
    assert case_result["result_card_matches"][0]["validation_status"] == "not_predicted"
    assert case_result["annotation_checks"][0]["candidate_count"] == 0
    assert case_result["image_quality"]["predicted_limitations"] == []
    assert case_result["warnings"] == []
    assert case_result["trace_count"] == 0
    assert result["runtime_snapshot_summary"]["model_refs"] == []


def test_validation_endpoints_smoke():
    client = TestClient(app)

    labels = client.get("/api/validation/labels")
    run = client.post("/api/validation/run", json={"export": False})
    fixture = client.get("/api/validation/fixtures/curated-sample")

    assert labels.status_code == 200
    assert run.status_code == 200
    assert fixture.status_code == 200
    assert "metrics" in run.json()


def test_validation_reports_point_distance_and_polygon_geometry(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        workbench,
        "get_case",
        lambda case_id: {
            "case_id": case_id,
            "analysis": {
                "systematic_reading": {"body_region": "MSK/orthopedic X-ray"},
                "image_quality": {"score": 0.8, "limitations": []},
                "findings": [],
                "result_cards": [],
                "annotations": [
                    {"label": "review point", "coordinate": {"type": "point", "x": 11, "y": 13}},
                    {"label": "review polygon", "coordinate": {"type": "polygon", "points": [[1, 1], [20, 1], [10, 15]]}},
                ],
                "warnings": [],
                "model_trace": [],
            },
        },
    )
    save_validation_label({
        "case_id": "shape-case",
        "expected_annotations": [
            {"label": "review point", "coordinate_type": "point", "required": True, "points": [[10, 10]], "max_point_distance": 5},
            {"label": "review polygon", "coordinate_type": "polygon", "required": True, "min_vertex_count": 3},
        ],
    })

    result = run_validation()
    checks = result["results"][0]["annotation_checks"]
    assert checks[0]["best_point_distance"] == 3.162
    assert checks[0]["localization_hit"] is True
    assert checks[1]["valid_geometry_count"] == 1
    assert checks[1]["localization_hit"] is True
    assert result["metrics"]["point_hit_rate"] == 1
    assert result["metrics"]["polygon_geometry_hit_rate"] == 1


def test_validation_uses_analysis_from_referenced_source_image(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    analysis_a = {
        "systematic_reading": {"body_region": "Chest X-ray"},
        "image_quality": {"score": 0.8, "limitations": []},
        "findings": [{"label": "view_specific_finding", "status": "negative"}],
        "result_cards": [{"id": "card-a", "finding": "view_specific_finding", "status": "negative"}],
        "annotations": [], "warnings": [], "model_trace": [],
    }
    analysis_b = {
        **analysis_a,
        "findings": [{"label": "view_specific_finding", "status": "positive"}],
        "result_cards": [{"id": "card-b", "finding": "view_specific_finding", "status": "positive"}],
    }
    monkeypatch.setattr(workbench, "get_case", lambda case_id: {
        "case_id": case_id,
        "active_image_id": "image-a",
        "analysis": analysis_a,
        "analyses_by_image": {"image-a": analysis_a, "image-b": analysis_b},
        "annotations": [],
    })
    save_validation_label({
        "case_id": "multi-view-validation",
        "source_image_id": "image-b",
        "expected_body_region": "Chest X-ray",
        "expected_findings": [{"label": "view_specific_finding", "status": "positive"}],
    })

    result = run_validation()
    case_result = result["results"][0]
    assert case_result["matches"][0]["predicted_status"] == "positive"
    assert case_result["result_card_matches"][0]["result_card_id"] == "card-b"
    assert case_result["result_card_matches"][0]["matched"] is True


def test_validation_uses_referenced_analysis_annotations_when_case_copy_is_missing(tmp_path, monkeypatch):
    import app.validation.workbench as workbench

    monkeypatch.setattr(workbench, "validation_dir", lambda: tmp_path)
    (tmp_path / "labels").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(workbench, "get_case", lambda case_id: {
        "case_id": case_id,
        "active_image_id": "image-a",
        "annotations": [],
        "analysis": {"annotations": []},
        "analyses_by_image": {
            "image-b": {
                "systematic_reading": {"body_region": "MSK/orthopedic X-ray"},
                "image_quality": {"score": 0.8, "limitations": []},
                "findings": [],
                "result_cards": [],
                "annotations": [{
                    "id": "ann-image-b",
                    "label": "candidate fracture localization",
                    "source_image_id": "image-b",
                    "coordinate": {"type": "grounding_box", "x": 10, "y": 10, "width": 20, "height": 20},
                }],
                "warnings": [],
                "model_trace": [],
            },
        },
    })
    save_validation_label({
        "case_id": "referenced-analysis-annotation-case",
        "source_image_id": "image-b",
        "expected_annotations": [{
            "label": "candidate fracture localization",
            "coordinate_type": "grounding_box",
            "required": True,
            "source_image_id": "image-b",
            "coordinate": {"x": 10, "y": 10, "width": 20, "height": 20},
            "min_iou": 0.5,
        }],
    })

    result = run_validation()

    check = result["results"][0]["annotation_checks"][0]
    assert check["candidate_count"] == 1
    assert check["localization_hit"] is True
