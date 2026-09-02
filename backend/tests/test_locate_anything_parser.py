import pytest

from app.models.schemas import AnnotationSource
from app.vision.locate_anything_parser import (
    MAX_LOCATE_ANYTHING_GROUNDINGS,
    MAX_LOCATE_ANYTHING_OUTPUT_CHARS,
    locate_anything_annotations,
    parse_locate_anything_output,
)


def test_parses_labeled_box_and_query_labeled_point_in_original_pixels():
    parsed = parse_locate_anything_output(
        "<ref>candidate region</ref><box><100><200><600><800></box> <box><250><750></box>",
        2000,
        1000,
        query="review target",
    )

    assert parsed["status"] == "ok"
    assert parsed["rejected_count"] == 0
    assert parsed["groundings"] == [
        {
            "type": "grounding_box",
            "label": "candidate region",
            "normalized_coordinate": {"x1": 100, "y1": 200, "x2": 600, "y2": 800, "scale": 1000},
            "coordinate": {
                "type": "grounding_box",
                "x": 200.0,
                "y": 200.0,
                "width": 1000.0,
                "height": 600.0,
                "points": [],
                "coordinate_space": "original_image",
            },
        },
        {
            "type": "point",
            "label": "review target",
            "normalized_coordinate": {"x": 250, "y": 750, "scale": 1000},
            "coordinate": {
                "type": "point",
                "x": 500.0,
                "y": 750.0,
                "width": 0.0,
                "height": 0.0,
                "points": [(500.0, 750.0)],
                "coordinate_space": "original_image",
            },
        },
    ]
    assert len(parsed["raw_output_hash"]) == 64


def test_none_output_is_an_explicit_abstention_without_annotations():
    parsed = parse_locate_anything_output("<box>none</box>", 512, 512, query="fracture")

    assert parsed["status"] == "none"
    assert parsed["none_count"] == 1
    assert parsed["groundings"] == []
    assert locate_anything_annotations(parsed) == []


@pytest.mark.parametrize(
    "answer",
    [
        "<box><500><100><400><900></box>",
        "<box><100><500><900><400></box>",
        "<box><0><0><1001><900></box>",
        "<box><100><200><300></box>",
        "<box><-1><20></box>",
    ],
)
def test_rejects_reversed_out_of_range_and_malformed_coordinates(answer):
    parsed = parse_locate_anything_output(answer, 1024, 1024, query="target")

    assert parsed["status"] == "rejected"
    assert parsed["groundings"] == []
    assert parsed["rejected_count"] >= 1
    assert parsed["warnings"]


def test_rejects_unbalanced_or_unbound_label_tags_without_partial_acceptance():
    unbalanced = parse_locate_anything_output("<ref>target<box><1><2><3><4></box>", 100, 100)
    unbound = parse_locate_anything_output("<ref>orphan</ref> text <box><1><2><30><40></box>", 100, 100)

    assert unbalanced["status"] == "rejected"
    assert unbalanced["groundings"] == []
    assert "unbalanced" in unbalanced["warnings"][0]
    assert unbound["status"] == "rejected"
    assert unbound["groundings"] == []
    assert "not bound" in unbound["warnings"][0]


def test_rejects_entire_output_when_grounding_count_exceeds_budget():
    answer = " ".join("<box><1><2></box>" for _ in range(MAX_LOCATE_ANYTHING_GROUNDINGS + 1))

    parsed = parse_locate_anything_output(answer, 100, 100)

    assert parsed["status"] == "rejected"
    assert parsed["groundings"] == []
    assert parsed["rejected_count"] == MAX_LOCATE_ANYTHING_GROUNDINGS + 1


def test_parser_rejects_invalid_budgets_and_dimensions_before_parsing():
    with pytest.raises(ValueError, match="character budget"):
        parse_locate_anything_output("x" * (MAX_LOCATE_ANYTHING_OUTPUT_CHARS + 1), 100, 100)
    with pytest.raises(ValueError, match="dimensions"):
        parse_locate_anything_output("<box>none</box>", 0, 100)
    with pytest.raises(ValueError, match="dimensions"):
        parse_locate_anything_output("<box>none</box>", 100_000, 100_000)
    with pytest.raises(ValueError, match="max_items"):
        parse_locate_anything_output("<box>none</box>", 100, 100, max_items=True)
    with pytest.raises(TypeError, match="string"):
        parse_locate_anything_output(None, 100, 100)  # type: ignore[arg-type]


def test_deduplicates_only_near_identical_groundings_with_same_label():
    parsed = parse_locate_anything_output(
        " ".join([
            "<ref>target</ref><box><100><100><500><500></box>",
            "<ref>target</ref><box><102><102><498><498></box>",
            "<ref>different target</ref><box><100><100><500><500></box>",
            "<ref>target</ref><box><200><200></box>",
            "<ref>target</ref><box><200><200></box>",
        ]),
        1000,
        1000,
    )

    assert parsed["status"] == "ok"
    assert len(parsed["groundings"]) == 3
    assert parsed["deduplicated_count"] == 2
    assert any("duplicate" in warning for warning in parsed["warnings"])


def test_mixed_none_and_coordinates_remains_unreviewed_with_warning():
    parsed = parse_locate_anything_output(
        "<box>none</box> <ref>target</ref><box><10><20><300><400></box>",
        1000,
        1000,
    )

    assert parsed["status"] == "ok"
    assert parsed["none_count"] == 1
    assert len(parsed["groundings"]) == 1
    assert any("mixed" in warning.lower() for warning in parsed["warnings"])


def test_converts_parsed_output_to_traceable_unreviewed_medray_annotations():
    parsed = parse_locate_anything_output(
        "<ref>candidate region</ref><box><100><200><600><800></box> <box><250><750></box>",
        2000,
        1000,
        query="fixed reviewed query",
    )

    annotations = locate_anything_annotations(
        parsed,
        source_model="local:locate-anything",
        source_model_version="revision-abc123",
        source_image_id="image-2",
        source_image_index=1,
        source_view="LATERAL",
        source_series_id="series-7",
    )

    assert len(annotations) == 2
    box, point = annotations
    assert box.source == AnnotationSource.MODEL_COORDINATE
    assert box.source_model == "local:locate-anything"
    assert box.source_model_version == "revision-abc123"
    assert box.coordinate.type == "grounding_box"
    assert point.coordinate.type == "point"
    assert box.confidence == 0
    assert box.review_status == "unreviewed"
    assert "no calibrated pathology confidence" in box.explanation
    assert box.original_state is not None
    assert box.original_state.coordinate == box.coordinate
    assert box.source_image_id == "image-2"
    assert box.source_image_index == 1
    assert box.source_view == "LATERAL"
    assert box.source_series_id == "series-7"
    assert parsed["raw_output_hash"] in box.transform_metadata.note


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "polygon"},
        {"width": -1},
        {"x": 999, "width": 2},
        {"x": float("nan")},
    ],
)
def test_annotation_conversion_revalidates_tampered_parser_result(patch):
    parsed = parse_locate_anything_output("<box><100><200><600><800></box>", 1000, 1000)
    parsed["groundings"][0]["coordinate"].update(patch)

    with pytest.raises(ValueError):
        locate_anything_annotations(parsed)
