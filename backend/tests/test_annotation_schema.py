import pytest
from pydantic import ValidationError

from app.models.schemas import Annotation, AnnotationSource, Coordinate


def test_annotation_schema():
    ann = Annotation(label="manual note", confidence=0.5, source=AnnotationSource.MANUAL, coordinate=Coordinate(x=1, y=2, width=3, height=4), explanation="test")
    assert ann.coordinate.width == 3
    assert ann.source.value == "manual user annotation"
    assert ann.coordinate.coordinate_space == "original_image"
    assert ann.transform_metadata.scale_x == 1
    assert ann.review_status == "unreviewed"
    assert ann.locked is False
    assert ann.revision_history == []
    assert ann.source_image_id == "primary"
    assert ann.source_image_index == 0
    assert ann.original_state is None


def test_point_and_polygon_coordinate_contracts():
    point = Coordinate(type="point", x=12, y=18, points=[(12, 18)])
    polygon = Coordinate(type="polygon", points=[(1, 1), (10, 1), (5, 8)])

    assert point.type == "point"
    assert polygon.type == "polygon"
    assert len(polygon.points) == 3
    with pytest.raises(ValidationError):
        Coordinate(type="polygon", points=[(1, 1), (2, 2), (3, 3)])
