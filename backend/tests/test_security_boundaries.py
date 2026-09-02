import pytest

from app.api.routes import _annotation_matches_image, _validate_case_geometry


def test_raw_case_rejects_oversized_polygon():
    with pytest.raises(ValueError, match="4096"):
        _validate_case_geometry({
            "annotations": [{
                "coordinate": {"type": "polygon", "points": [[index, 0] for index in range(4097)]},
            }],
        })


def test_filename_alias_is_only_used_when_unique():
    image = {"image_id": "image-a", "filename": "same.png"}
    images = [image, {"image_id": "image-b", "filename": "same.png"}]
    annotation = {"source_image_id": "same.png"}
    assert _annotation_matches_image(annotation, image, images=images) is False
    assert _annotation_matches_image(annotation, image, images=[image]) is True
