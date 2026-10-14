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


def test_measurement_coordinate_contracts():
    length = Coordinate(type="length", points=[(1, 2), (4, 6)])
    ellipse = Coordinate(type="ellipse", x=10, y=20, width=30, height=40)
    assert length.points == [(1, 2), (4, 6)]
    assert ellipse.width == 30
    with pytest.raises(ValidationError):
        Coordinate(type="length", points=[(1, 2)])
    with pytest.raises(ValidationError):
        Coordinate(type="ellipse", x=1, y=1, width=0, height=2)


@pytest.mark.parametrize("kind,points", [
    ("length", [(1, 2), (1, 2)]),
    ("angle", [(1, 2), (1, 2), (3, 4)]),
    ("angle", [(3, 4), (1, 2), (1, 2)]),
    ("length", [(-1e308, 0), (1e308, 0)]),
    ("angle", [(-1e308, 0), (1e308, 0), (1e308, 1)]),
])
def test_measurement_requires_finite_nonzero_arms(kind, points):
    with pytest.raises(ValidationError):
        Coordinate(type=kind, points=points)


@pytest.mark.parametrize("points", [
    [(10, 0), (0, 0), (0, 10)],
    [(10, 0), (0, 0), (20, 0)],
    [(10, 0), (0, 0), (-10, 0)],
])
def test_angle_accepts_right_zero_and_straight_angles(points):
    assert Coordinate(type="angle", points=points).points == points
