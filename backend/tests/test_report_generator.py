from app.reports.generator import _wrapped_pdf_lines, report_json_payload, report_markdown


def test_report_contains_disclaimer():
    text = report_markdown({"case_id": "c1", "title": "Case", "analysis": {"report": {}, "systematic_reading": {}, "image_quality": {}}})
    assert "AI-assisted draft" in text
    assert "Keterbatasan" in text


def test_report_includes_result_cards():
    text = report_markdown(
        {
            "case_id": "c1",
            "title": "Case",
            "analysis": {
                "report": {},
                "systematic_reading": {},
                "image_quality": {"exposure": "adequate", "score": 0.7},
                "result_cards": [
                    {
                        "finding": "txrv_cardiomegaly",
                        "candidate_diagnosis": "AI candidate diagnosis: cardiomegaly",
                        "status": "positive",
                        "probability": 0.71,
                        "confidence": 0.71,
                        "next_safe_action": "Review by a qualified radiologist/physician.",
                    }
                ],
            },
        }
    )
    assert "Result Cards" in text
    assert "AI candidate diagnosis: cardiomegaly" in text


def test_report_promotes_only_reviewed_grounded_statements():
    case = {
            "case_id": "msk-1",
            "title": "Wrist",
            "annotations": [
                {
                    "id": "ann-1",
                    "label": "distal radius candidate box",
                    "review_status": "accepted",
                    "linked_result_card_ids": ["card-1"],
                    "coordinate": {"type": "grounding_box", "x": 10, "y": 20, "width": 30, "height": 40},
                }
            ],
            "analysis": {
                "report": {"findings": "Original draft text.", "impression": "Draft impression."},
                "systematic_reading": {},
                "image_quality": {"exposure": "adequate", "score": 0.8},
                "result_cards": [
                    {
                        "id": "card-1",
                        "finding": "candidate_fracture_localization",
                        "candidate_diagnosis": "AI candidate diagnosis: distal radius fracture cue",
                        "status": "uncertain",
                        "confidence": 0.66,
                        "review_status": "accepted",
                        "annotation_refs": ["ann-1"],
                        "reviewer_note": "Matches subtle cortical step-off.",
                    },
                    {
                        "id": "card-2",
                        "finding": "unsupported_elbow_finding",
                        "candidate_diagnosis": "AI candidate diagnosis: unsupported elbow finding",
                        "status": "positive",
                        "confidence": 0.75,
                        "review_status": "rejected",
                        "annotation_refs": [],
                    },
                    {
                        "id": "card-3",
                        "finding": "unreviewed_soft_tissue_swelling",
                        "candidate_diagnosis": "AI candidate diagnosis: soft tissue swelling",
                        "status": "uncertain",
                        "confidence": 0.5,
                        "review_status": "unreviewed",
                        "annotation_refs": [],
                    },
                ],
            },
        }
    text = report_markdown(case)
    grounded_section = text.split("## Statement Review Grounded", 1)[1].split("## Temuan", 1)[0]
    assert "candidate_fracture_localization" in grounded_section
    assert "distal radius candidate box" in grounded_section
    assert "unsupported_elbow_finding" not in grounded_section
    assert "unreviewed_soft_tissue_swelling" not in grounded_section
    assert "1 rejected dan 1 result card belum direview" in grounded_section

    payload = report_json_payload(case)
    promoted = [item for item in payload["grounded_review_statements"] if item["promoted_to_report"]]
    assert payload["schema_version"] == "0.4.12"
    assert promoted[0]["result_card_id"] == "card-1"
    assert promoted[0]["annotation_refs"] == ["ann-1"]


def test_grounded_report_prefers_reviewed_case_annotations_over_stale_analysis_copy():
    case = {
        "case_id": "msk-stale",
        "title": "Wrist",
        "annotations": [
            {
                "id": "ann-1",
                "label": "reviewed distal radius box",
                "review_status": "accepted",
                "linked_result_card_ids": ["card-1"],
                "coordinate": {"type": "grounding_box", "x": 10, "y": 20, "width": 30, "height": 40},
            },
            {
                "id": "ann-2",
                "label": "unreviewed linked box",
                "review_status": "unreviewed",
                "linked_result_card_ids": ["card-1"],
                "coordinate": {"type": "grounding_box", "x": 50, "y": 60, "width": 70, "height": 80},
            },
        ],
        "analysis": {
            "report": {},
            "systematic_reading": {},
            "image_quality": {"exposure": "adequate", "score": 0.8},
            "annotations": [
                {
                    "id": "ann-1",
                    "label": "stale unreviewed copy",
                    "review_status": "unreviewed",
                    "linked_result_card_ids": ["card-1"],
                    "coordinate": {"type": "grounding_box", "x": 0, "y": 0, "width": 1, "height": 1},
                }
            ],
            "result_cards": [
                {
                    "id": "card-1",
                    "finding": "candidate_fracture_localization",
                    "candidate_diagnosis": "AI candidate diagnosis: distal radius fracture cue",
                    "status": "uncertain",
                    "confidence": 0.66,
                    "review_status": "accepted",
                    "annotation_refs": ["ann-1", "ann-2"],
                }
            ],
        },
    }

    payload = report_json_payload(case)
    promoted = [item for item in payload["grounded_review_statements"] if item["promoted_to_report"]]

    assert promoted[0]["annotation_refs"] == ["ann-1"]
    assert "reviewed distal radius box" in promoted[0]["text"]
    assert "stale unreviewed copy" not in promoted[0]["text"]
    assert "unreviewed linked box" not in promoted[0]["text"]


def test_report_exports_exclude_unreviewed_differential_candidates():
    case = {
        "case_id": "unreviewed-differential",
        "title": "Unreviewed differential",
        "analysis": {
            "report": {},
            "systematic_reading": {},
            "image_quality": {"exposure": "adequate", "score": 0.8},
            "result_cards": [{
                "id": "card-unreviewed",
                "finding": "candidate opacity",
                "candidate_diagnosis": "AI candidate diagnosis: possible opacity",
                "status": "uncertain",
                "review_status": "unreviewed",
            }],
        },
    }

    payload = report_json_payload(case)
    markdown = report_markdown(case)

    assert payload["differential_assistance"] == []
    assert "- Tentatif:" not in markdown


def test_grounded_report_handles_legacy_null_annotation_refs():
    payload = report_json_payload(
        {
            "case_id": "legacy-card",
            "title": "Legacy card",
            "analysis": {
                "report": {},
                "systematic_reading": {},
                "image_quality": {"exposure": "adequate", "score": 0.8},
                "result_cards": [
                    {
                        "id": "card-legacy",
                        "finding": "legacy_candidate",
                        "candidate_diagnosis": "AI candidate diagnosis: legacy candidate",
                        "status": "uncertain",
                        "confidence": 0.5,
                        "review_status": "accepted",
                        "annotation_refs": None,
                    }
                ],
            },
        }
    )

    promoted = [item for item in payload["grounded_review_statements"] if item["promoted_to_report"]]
    assert promoted[0]["annotation_refs"] == []
    assert "belum ada anotasi tertaut" in promoted[0]["text"]


def test_report_tolerates_malformed_annotation_and_card_collections():
    payload = report_json_payload(
        {
            "case_id": "legacy-malformed",
            "title": "Legacy malformed",
            "annotations": "not-a-list",
            "analysis": {
                "report": {},
                "systematic_reading": {},
                "image_quality": {"exposure": "adequate", "score": 0.8},
                "annotations": [{"id": "ann-ok", "label": "valid reviewed annotation", "review_status": "accepted", "coordinate": {"type": "bbox"}}],
                "result_cards": "not-a-list",
                "differential_diagnosis": "not-a-list",
            },
        }
    )

    assert payload["result_cards"] == []
    assert payload["annotations"][0]["id"] == "ann-ok"
    assert payload["grounded_review_statements"][0]["kind"] == "standalone_reviewed_annotation"


def test_english_export_reconstructs_mismatched_indonesian_report_language():
    case = {
        "case_id": "language-case",
        "report": {"language": "id", "findings": "Temuan Indonesia", "impression": "Kesan Indonesia"},
        "analysis": {"image_quality": {"exposure": "adequate", "score": 0.8}, "systematic_reading": {"body_region": "Chest X-ray"}},
    }

    text = report_markdown(case, "en")
    payload = report_json_payload(case, "en")

    assert "## Findings" in text
    assert "Temuan Indonesia" not in text
    assert payload["report"]["language"] == "en"


def test_pdf_line_wrapping_preserves_all_text():
    original = "word " * 100
    wrapped = _wrapped_pdf_lines(original, width=40)

    assert len(wrapped) > 1
    assert "".join(wrapped).replace(" ", "") == original.replace(" ", "")
