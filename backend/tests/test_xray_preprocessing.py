from contextlib import nullcontext
import hashlib
from types import SimpleNamespace
import sys

import pytest
from PIL import Image
from app.vision import torchxrayvision_classifier as classifier
from app.ai_setup.catalog import TXRV_ID, weights_path


@pytest.fixture
def fake_runtime(tmp_path, monkeypatch):
    calls = []
    scores = [0.7]
    class Output:
        def __getitem__(self, index): return self
        def detach(self): return self
        def cpu(self): return self
        def tolist(self): return scores
    class Model:
        targets = ["Opacity"]
        def __init__(self, **kwargs): calls.append(kwargs)
        def eval(self): pass
        def __call__(self, tensor): return Output()
    class Tensor:
        def unsqueeze(self, _): return self
    def normalize(image, maximum):
        assert image.max() == 128  # No double normalization.
        calls.append("normalized_once")
        return image
    xrv = SimpleNamespace(models=SimpleNamespace(DenseNet=Model), datasets=SimpleNamespace(normalize=normalize, XRayCenterCrop=lambda: lambda image: image, XRayResizer=lambda _: lambda image: image))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(from_numpy=lambda _: Tensor(), no_grad=nullcontext))
    monkeypatch.setitem(sys.modules, "torchxrayvision", xrv)
    weights_path().write_bytes(b"trusted-fixture")
    monkeypatch.setattr(classifier, "WEIGHTS_SHA256", hashlib.sha256(b"trusted-fixture").hexdigest())
    path = tmp_path / "gambar unicode é.png"
    Image.new("L", (32, 32), 128).save(path)
    return str(path), calls, scores


def test_preprocessing_runs_once_and_loads_only_verified_local_weights(fake_runtime):
    image, calls, _ = fake_runtime
    result = classifier.run_torchxrayvision_classifier(image, TXRV_ID)
    assert result["status"] == "ok"
    assert calls.count("normalized_once") == 1
    assert calls[-1]["cache_dir"] == str(weights_path().parent)


def test_corrupt_weights_rejected_before_model_load(fake_runtime):
    image, calls, _ = fake_runtime
    weights_path().write_bytes(b"untrusted replacement")
    result = classifier.run_torchxrayvision_classifier(image, TXRV_ID)
    assert result["status"] == "failed"
    assert "integrity" in result["detail"]
    assert calls == []


def test_invalid_probabilities_reject_entire_model_output(fake_runtime):
    image, _, scores = fake_runtime
    scores[0] = float("nan")
    result = classifier.run_torchxrayvision_classifier(image, TXRV_ID)
    assert result["status"] == "failed"
    assert result["findings"] == []


def test_missing_weights_never_triggers_hidden_download(fake_runtime):
    image, calls, _ = fake_runtime
    weights_path().unlink()
    assert classifier.run_torchxrayvision_classifier(image, TXRV_ID)["status"] == "failed"
    assert calls == []
