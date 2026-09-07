from pathlib import Path
from app.config import get_settings

TXRV_ID = "torchxrayvision:densenet121-res224-all"
WEIGHTS_NAME = "nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt"
WEIGHTS_URL = "https://github.com/mlmed/torchxrayvision/releases/download/v1/" + WEIGHTS_NAME
# SHA-256 of the official release artifact, downloaded and verified 2026-09-05.
# The upstream loader uses Python pickle; never pass unverified files to it.
WEIGHTS_SHA256 = "56524913dd16a906422e8d8b66a7a5c46be1d82eb7ac012d8103776f1aa68899"

CLASSIFIER_RECIPES = {
    TXRV_ID: {
        "display_name": "DenseNet-121 All-Datasets",
        "weights": "densenet121-res224-all",
        "weights_name": WEIGHTS_NAME,
        "url": WEIGHTS_URL,
        "sha256": WEIGHTS_SHA256,
        "resolution": 224,
        "dataset": "NIH, PadChest, CheXpert, MIMIC-CXR and other public CXR cohorts",
        "scope": "Broad 18-label research baseline; recommended starting point.",
    },
    "torchxrayvision:densenet121-res224-nih": {
        "display_name": "DenseNet-121 NIH ChestX-ray8",
        "weights": "densenet121-res224-nih",
        "weights_name": "nih-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
        "url": "https://github.com/mlmed/torchxrayvision/releases/download/v1/nih-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
        "sha256": "31a5475c6b1383a7edbfcaf96af9ce302eb9969cfe28b6b8b5859afc6f274fdf",
        "resolution": 224,
        "dataset": "NIH ChestX-ray8",
        "scope": "Dataset-specific research comparison; only NIH-trained targets are meaningful.",
    },
    "torchxrayvision:densenet121-res224-chex": {
        "display_name": "DenseNet-121 CheXpert",
        "weights": "densenet121-res224-chex",
        "weights_name": "chex-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
        "url": "https://github.com/mlmed/torchxrayvision/releases/download/v1/chex-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
        "sha256": "1a914ae802170187a4852e594708206c12468eeeefd66aa4e8e26141649d61a4",
        "resolution": 224,
        "dataset": "CheXpert",
        "scope": "CheXpert-trained research comparison; unsupported target outputs are excluded.",
    },
    "torchxrayvision:densenet121-res224-rsna": {
        "display_name": "DenseNet-121 RSNA Pneumonia",
        "weights": "densenet121-res224-rsna",
        "weights_name": "kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
        "url": "https://github.com/mlmed/torchxrayvision/releases/download/v1/kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
        "sha256": "906a59f48cf09638b745d66848a6c6f9d741368c66244717a81207329d140268",
        "resolution": 224,
        "dataset": "RSNA Pneumonia Challenge",
        "scope": "Narrow pneumonia/lung-opacity research comparison; not a general classifier.",
    },
}


def classifier_recipe(model_id: str = TXRV_ID) -> dict:
    try:
        return CLASSIFIER_RECIPES[model_id]
    except KeyError:
        raise ValueError("Unknown or unreviewed classifier recipe.") from None


def weights_path(model_id: str = TXRV_ID) -> Path:
    return get_settings().models_dir / classifier_recipe(model_id)["weights_name"]


def compatibility(model: dict) -> dict:
    # A Hub repository is a source, not an executable adapter. Only exact reviewed
    # integrations can have an automatic install plan. Never infer support from tags.
    identity = str(model.get("id", "")).removeprefix("github:")
    if identity in {"mlmed/torchxrayvision", "starter:torchxrayvision", TXRV_ID, "hf:torchxrayvision/densenet121-res224-all"}:
        return {"status": "supported", "runtime": "TorchXRayVision", "model_id": TXRV_ID,
                "reason": "MedRay supports this DenseNet-121 model through its reviewed TorchXRayVision recipe. Setup uses the pinned official GitHub release weights; repository code and arbitrary Hub files are not executed.",
                "action": "Set up X-ray Vision", "recommended_files": [WEIGHTS_NAME]}
    return {"status": "configuration_required", "runtime": None, "model_id": None,
            "reason": "This repository has no embedded MedRay setup recipe. Load the model in an application that supports its architecture, then connect and test it in Local AI or Online AI. Chat-completions servers can provide image review, chat and reports when the model supports that task. Raw classification/segmentation weights still need a matching task adapter. Repository scripts and remote code are never run automatically.",
            "action": "Connect a compatible runtime", "recommended_files": []}
