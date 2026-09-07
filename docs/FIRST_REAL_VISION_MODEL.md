# First real vision model

Open **AI Setup → My Models → TorchXRayVision → Continue setup**. MedRay checks dependencies, installs the reviewed CPU recipe where supported, downloads official weights, then loads and tests a synthetic image. After **Ready**, click **Use as classifier**. No adapter ID or filename is required.

See [AI Setup](AI_SETUP.md) for Windows installation, GPU guidance, troubleshooting and alternatives: Ollama and compatible servers for image review, chat and report drafting.

Only reviewed DenseNet-121 all-datasets weights are supported. Grayscale pixels are normalized once, center-cropped and resized to 224 × 224. Official weights are SHA-256 checked before the upstream loader. Inference does not trigger a hidden weights download. Missing dependencies, invalid weights, load failure and invalid output prevent readiness.

Classification produces uncalibrated research probabilities. It does not localize lesions, segment anatomy, establish a diagnosis or prove clinical validity. Model cards, validation evidence, human verification and provenance remain. Failed real inference explicitly identifies fallback use and its reason.

Advanced/internal ID: `torchxrayvision:densenet121-res224-all`.

Official references: [TorchXRayVision](https://github.com/mlmed/torchxrayvision), [PyTorch installation selector](https://pytorch.org/get-started/locally/).
