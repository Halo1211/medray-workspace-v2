from app.results.differential import build_differential_assistance


def test_differential_assistance_is_tentative_and_traceable():
    candidates = build_differential_assistance(
        [
            {
                "id": "card-1",
                "finding": "candidate fracture",
                "status": "uncertain",
                "candidate_diagnosis": "AI candidate diagnosis: possible fracture",
                "review_status": "needs_follow_up",
                "validation_status": "not_validated",
                "evidence": [
                    {"kind": "finding", "text": "Cortical irregularity research signal."},
                    {"kind": "limitation", "text": "Single view only."},
                ],
                "annotation_refs": ["ann-1"],
                "source_image_ids": ["image-2"],
            }
        ],
        {"comparison": "Tidak tersedia."},
    )

    assert candidates[0]["tentative"] is True
    assert candidates[0]["eligible_for_report_review"] is True
    assert candidates[0]["result_card_id"] == "card-1"
    assert candidates[0]["annotation_refs"] == ["ann-1"]
    assert candidates[0]["source_image_ids"] == ["image-2"]
    assert "Single view only." in candidates[0]["evidence_against"]
    assert "Prior comparison is unavailable." in candidates[0]["missing_information"]


def test_differential_assistance_excludes_negative_rejected_and_malformed_cards():
    candidates = build_differential_assistance(
        [
            "bad",
            {"status": "negative", "candidate_diagnosis": "AI candidate diagnosis: no finding"},
            {"status": "positive", "review_status": "rejected", "candidate_diagnosis": "AI candidate diagnosis: rejected"},
            {"status": "uncertain", "candidate_diagnosis": "No AI candidate diagnosis from fallback output"},
        ]
    )

    assert candidates == []
