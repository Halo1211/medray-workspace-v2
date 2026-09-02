import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


_ORIGINAL_DATA_DIR = os.environ.get("MEDRAY_DATA_DIR")
_COLLECTION_DATA_DIR = Path(tempfile.mkdtemp(prefix="medray-pytest-"))
os.environ["MEDRAY_DATA_DIR"] = str(_COLLECTION_DATA_DIR)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.storage.db import init_db

    monkeypatch.setenv("MEDRAY_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    init_db()
    yield
    get_settings.cache_clear()


def pytest_unconfigure(config):
    from app.config import get_settings

    get_settings.cache_clear()
    if _ORIGINAL_DATA_DIR is None:
        os.environ.pop("MEDRAY_DATA_DIR", None)
    else:
        os.environ["MEDRAY_DATA_DIR"] = _ORIGINAL_DATA_DIR
    shutil.rmtree(_COLLECTION_DATA_DIR, ignore_errors=True)
