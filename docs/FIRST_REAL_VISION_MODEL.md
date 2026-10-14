# Set up a chest X-ray classifier

1. Open **AI Setup → X-ray Classifiers**.
2. Choose a reviewed DenseNet-121 recipe: All-Datasets, NIH ChestX-ray8, CheXpert,
   or RSNA Pneumonia.
3. Follow the guided CPU setup or the platform-specific installation guidance.
4. Download the official weights and run the synthetic load/inference test.
5. After the model is technically ready, select **Use as classifier**.

Each recipe uses pinned official weights with SHA-256 verification. The adapter
normalizes grayscale input once, center-crops it, and resizes it to 224 × 224.
Analysis does not silently download missing weights. Missing dependencies,
changed weights, load failures, and invalid output prevent model readiness.

Classifier scores are uncalibrated research signals. They do not localize lesions,
segment anatomy, establish a diagnosis, or demonstrate clinical validity. Local
validation evidence and qualified human review remain necessary.

For general image review, chat, and reporting through Ollama or a compatible
server, follow the [AI Setup guide](AI_SETUP.md). See [verification](VERIFICATION.md)
for the tested scope.

References: [TorchXRayVision](https://github.com/mlmed/torchxrayvision) and the
[PyTorch installation selector](https://pytorch.org/get-started/locally/).
