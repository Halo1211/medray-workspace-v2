from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import UnidentifiedImageError

from app.services import image_service


def test_invalid_upload_is_rolled_back(tmp_path, monkeypatch):
    target = tmp_path / "case-invalid" / "invalid.png"
    target.parent.mkdir()
    monkeypatch.setattr(image_service, "safe_case_path", lambda case_id, filename: target)
    upload = SimpleNamespace(filename="invalid.png", file=BytesIO(b"not an image"))

    with pytest.raises(UnidentifiedImageError):
        image_service.ingest_upload(upload, case_id="case-invalid")

    assert not target.exists()
    assert not target.parent.exists()
