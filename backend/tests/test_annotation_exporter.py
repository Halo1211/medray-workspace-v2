from types import SimpleNamespace

from PIL import Image

from app.annotations import exporter


def test_review_package_separates_original_ai_and_reviewed_annotations(tmp_path, monkeypatch):
    image_path = tmp_path / "case.png"
    Image.new("L", (64, 64), color=120).save(image_path)
    monkeypatch.setattr(exporter, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))

    ai_annotation = {
        "id": "ai-1",
        "label": "reviewer edited label",
        "confidence": 0.8,
        "source": "model-returned coordinate",
        "coordinate": {"type": "bbox", "x": 20, "y": 20, "width": 25, "height": 25},
        "original_coordinate": {"type": "bbox", "x": 10, "y": 10, "width": 20, "height": 20},
        "original_state": {
            "label": "AI candidate opacity",
            "confidence": 0.7,
            "coordinate": {"type": "bbox", "x": 10, "y": 10, "width": 20, "height": 20},
            "explanation": "Original model output",
            "visible": True,
        },
        "explanation": "Edited by reviewer",
        "visible": False,
        "review_status": "rejected",
        "reviewer_note": "Not supported",
        "revision_history": [{"action": "edited"}],
        "source_image_id": "image-1",
        "source_image_index": 0,
    }
    manual_annotation = {
        "id": "manual-1",
        "label": "manual finding",
        "confidence": 1,
        "source": "manual user annotation",
        "coordinate": {"type": "bbox", "x": 30, "y": 30, "width": 10, "height": 10},
        "explanation": "Manual",
        "visible": True,
        "review_status": "accepted",
        "revision_history": [{"action": "created"}],
        "source_image_id": "image-1",
        "source_image_index": 0,
    }
    case = {
        "case_id": "case-1",
        "title": "case.png",
        "image_path": str(image_path),
        "metadata": {"ViewPosition": "PA"},
        "annotations": [ai_annotation, manual_annotation],
    }

    result = exporter.export_annotation_review_package(case)
    bundle = result["bundle"]

    assert bundle["review_summary"]["ai_original_count"] == 1
    assert bundle["review_summary"]["reviewed_count"] == 2
    assert bundle["review_summary"]["manual_count"] == 1
    assert bundle["ai_original_annotations"][0]["label"] == "AI candidate opacity"
    assert bundle["ai_original_annotations"][0]["coordinate"]["x"] == 10
    assert bundle["ai_original_annotations"][0]["review_status"] == "unreviewed"
    assert bundle["reviewed_annotations"][0]["review_status"] == "rejected"
    assert (tmp_path / "exports" / "case-1" / "annotated_ai_original.png").exists()
    assert (tmp_path / "exports" / "case-1" / "annotated_reviewed.png").exists()
    assert (tmp_path / "exports" / "case-1" / "annotation_review_comparison.json").exists()


def test_annotated_png_skips_invalid_boxes_and_string_confidence(tmp_path, monkeypatch):
    image_path = tmp_path / "case.png"
    Image.new("L", (64, 64), color=120).save(image_path)
    monkeypatch.setattr(exporter, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))

    path = exporter.export_annotated_png(
        "case-partial",
        str(image_path),
        [
            {
                "label": "string confidence",
                "confidence": "0.42",
                "source": "manual user annotation",
                "coordinate": {"type": "bbox", "x": "5", "y": "6", "width": "10", "height": "12"},
            },
            {
                "label": "invalid box",
                "confidence": None,
                "source": "manual user annotation",
                "coordinate": {"type": "bbox", "x": 1, "y": 1, "width": 0, "height": 10},
            },
        ],
    )

    assert path.endswith("annotated_reviewed.png")
    assert (tmp_path / "exports" / "case-partial" / "annotated_reviewed.png").exists()


def test_annotation_exporter_tolerates_malformed_annotation_collections(tmp_path, monkeypatch):
    image_path = tmp_path / "case.png"
    Image.new("L", (64, 64), color=120).save(image_path)
    monkeypatch.setattr(exporter, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))

    case = {
        "case_id": "case-malformed",
        "title": "case.png",
        "image_path": str(image_path),
        "annotations": "not-a-list",
        "analysis": {
            "annotations": [
                {
                    "id": "ann-1",
                    "label": "fallback analysis annotation",
                    "confidence": 0.5,
                    "source": "model-returned coordinate",
                    "coordinate": {"type": "bbox", "x": 5, "y": 5, "width": 10, "height": 10},
                    "visible": True,
                }
            ]
        },
    }

    bundle = exporter.build_annotation_review_bundle(case)
    path = exporter.export_annotated_png("case-malformed", str(image_path), "not-a-list")

    assert bundle["review_summary"]["reviewed_count"] == 1
    assert bundle["reviewed_annotations"][0]["id"] == "ann-1"
    assert (tmp_path / "exports" / "case-malformed" / "annotated_reviewed.png").exists()
    assert path.endswith("annotated_reviewed.png")


def test_annotated_png_renders_manual_point_and_polygon(tmp_path, monkeypatch):
    image_path = tmp_path / "shapes.png"
    Image.new("RGB", (64, 64), color="black").save(image_path)
    monkeypatch.setattr(exporter, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))

    path = exporter.export_annotated_png(
        "case-shapes",
        str(image_path),
        [
            {"label": "manual point", "source": "manual user annotation", "visible": True, "coordinate": {"type": "point", "x": 20, "y": 20}},
            {"label": "manual polygon", "source": "manual user annotation", "visible": True, "coordinate": {"type": "polygon", "points": [[30, 30], [50, 30], [40, 50]]}},
        ],
    )

    assert (tmp_path / "exports" / "case-shapes" / "annotated_reviewed.png").exists()
    assert path.endswith("annotated_reviewed.png")


def test_annotated_png_scales_legacy_preview_coordinates_to_original_image(tmp_path, monkeypatch):
    image_path = tmp_path / "large.png"
    Image.new("RGB", (200, 100), color="black").save(image_path)
    monkeypatch.setattr(exporter, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))

    path = exporter.export_annotated_png(
        "case-scaled",
        str(image_path),
        [
            {
                "label": "legacy preview box",
                "confidence": 1,
                "source": "manual user annotation",
                "visible": True,
                "coordinate": {"type": "bbox", "x": 10, "y": 10, "width": 10, "height": 10},
                "transform_metadata": {"original_width": 100, "original_height": 50},
            }
        ],
    )

    with Image.open(path) as exported:
        assert exported.getpixel((20, 40)) != (0, 0, 0)
        assert exported.getpixel((10, 40)) == (0, 0, 0)


def test_annotation_review_bundle_tolerates_malformed_mapping_fields():
    bundle = exporter.build_annotation_review_bundle(
        {
            "case_id": "malformed-annotation-mappings",
            "image_path": "missing.png",
            "file_hashes": "not-a-mapping",
            "analysis": "not-a-mapping",
            "annotations": [
                {
                    "id": "ann-1",
                    "source": "model-returned coordinate",
                    "coordinate": "not-a-mapping",
                    "original_state": "not-a-mapping",
                }
            ],
        }
    )

    assert bundle["source_images"][0]["input_hash"] is None
    assert bundle["ai_original_annotations"][0]["coordinate"] == {}
