from app.audit.bundle import build_audit_bundle, hash_file


def test_hash_file_and_audit_bundle_include_trust_layer(tmp_path):
    image = tmp_path / "case.png"
    preview = tmp_path / "case.preview.png"
    image.write_bytes(b"input-image")
    preview.write_bytes(b"preview-image")

    case = {
        "case_id": "case-1",
        "title": "Trust case",
        "image_path": str(image),
        "image_preview": str(preview),
        "metadata": {"format": "PNG"},
        "file_hashes": {"input": hash_file(str(image)), "preview": hash_file(str(preview))},
        "runtime": {"primary_backend": "demo"},
        "analysis": {
            "model_trace": [{"stage": "custom_prompt", "backend": "demo", "model": "pipeline", "status": "skipped", "detail": "", "timestamp": "now"}],
            "warnings": ["demo only"],
            "anatomy_route": {"profile_id": "chest", "body_region": "Chest X-ray"},
            "result_cards": [
                {
                    "id": "card-1",
                    "finding": "reviewed_finding",
                    "candidate_diagnosis": "AI candidate diagnosis: reviewed finding",
                    "status": "uncertain",
                    "confidence": 0.5,
                    "review_status": "accepted",
                    "annotation_refs": [],
                }
            ],
        },
    }

    bundle = build_audit_bundle(case)

    assert bundle["schema_version"] == "0.4.0"
    assert bundle["input_hashes"]["input"]["digest"]
    assert bundle["runtime_snapshot"]["primary_backend"] == "demo"
    assert bundle["immutable_model_trace"][0]["model"] == "pipeline"
    assert bundle["model_cards"][0]["id"] == "pipeline"
    assert "safety" in bundle["why_this_output_exists"]
    assert bundle["output_summary"]["annotation_review_summary"]["reviewed_count"] == 0
    assert bundle["output_summary"]["anatomy_route"]["profile_id"] == "chest"
    assert bundle["output_summary"]["grounded_review_statement_count"] == 1
    assert bundle["output_summary"]["grounded_review_statements"][0]["result_card_id"] == "card-1"
    assert "grounded_review_statements" in bundle["why_this_output_exists"]
    assert bundle["validation_evidence_used"] == []


def test_audit_bundle_tolerates_malformed_collections():
    bundle = build_audit_bundle(
        {
            "case_id": "malformed-audit",
            "title": "Malformed audit",
            "annotations": "not-a-list",
            "analysis": {
                "model_trace": "not-a-list",
                "warnings": "not-a-list",
                "findings": "not-a-list",
                "result_cards": "not-a-list",
                "annotations": "not-a-list",
                "report": {},
            },
        }
    )

    assert bundle["immutable_model_trace"] == []
    assert bundle["model_cards"] == []
    assert bundle["output_summary"]["warnings"] == []
    assert bundle["output_summary"]["findings_count"] == 0
    assert bundle["output_summary"]["result_cards_count"] == 0
    assert bundle["output_summary"]["annotations_count"] == 0


def test_audit_bundle_tolerates_malformed_mapping_fields():
    bundle = build_audit_bundle(
        {
            "case_id": "malformed-mappings",
            "image_path": "missing.png",
            "file_hashes": "not-a-mapping",
            "analysis": "not-a-mapping",
            "report": "not-a-mapping",
        }
    )

    assert bundle["immutable_model_trace"] == []
    assert bundle["runtime_snapshot"] == {}
    assert bundle["input_hashes"]["input"]["status"] == "missing"
    assert bundle["output_summary"]["report_watermark"] is None
