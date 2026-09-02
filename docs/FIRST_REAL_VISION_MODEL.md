# First Real Vision Model

v0.4 starts with one optional local CXR classifier adapter. The first supported adapter target is:

`torchxrayvision:densenet121-res224-all`

This is an optional integration path for TorchXRayVision DenseNet-121 pathology classifiers. It is not enabled by default and is not a clinical device feature.

## Why Classifier First

- Classification returns structured labels and probabilities.
- It does not claim lesion location.
- It can be compared against Validation Workbench labels before adding grounding or segmentation.
- It fits the current Trust Layer: model card, runtime snapshot, model trace, warning text, and audit bundle.

## Runtime Behavior

The adapter only runs when `Runtime Settings -> classification_model` starts with:

`torchxrayvision:`

Example:

`torchxrayvision:densenet121-res224-all`

If dependencies are missing, the model cannot load, or inference fails, MedRay keeps the fallback output and records a classifier trace event with `skipped` or `failed`.

Runtime Settings also shows `Local vision adapters`, a read-only readiness panel. The `Use for classifier` button only writes the adapter id into the runtime config draft. It does not install dependencies, download weights, or run analysis by itself.

## Optional Dependencies

Install from `backend/requirements-optional.txt` when you want real local classifier inference:

```bash
pip install -r backend/requirements-optional.txt
```

PyTorch installation may need a CPU/GPU-specific command from the PyTorch project. TorchXRayVision pretrained weights may be downloaded and cached by the library on first use.

## Safety Constraints

- Classifier probabilities are uncalibrated for the user's local dataset and protocol.
- Outputs are research signals, not diagnoses.
- No bounding boxes or masks are shown unless a localization/segmentation model returns real coordinates later.
- Report text remains watermarked and non-diagnostic.
- Validation Workbench should be used before trusting any model behavior.

## References

- TorchXRayVision model docs: https://mlmed.org/torchxrayvision/models.html
- TorchXRayVision paper: https://arxiv.org/abs/2111.00595
- CheXpert dataset: https://stanfordmlgroup.github.io/competitions/chexpert/
- FDA MLMD transparency principles: https://www.fda.gov/medical-devices/software-medical-device-samd/transparency-machine-learning-enabled-medical-devices-guiding-principles
