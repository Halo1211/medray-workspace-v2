# Model Integration

## Built-in Demo

The Built-in Demo is the safest first-run path for exploring the application. It is deterministic scaffolding, not a trained clinical AI model, and does not require model weights.

## Ollama

Install and start Ollama separately, then pull a compatible model. For example:

```bash
ollama pull qwen2.5:3b
```

Choose Ollama in **Runtime Settings** and enter the exact model name shown by `ollama list`. A compatible vision model is required for image review. A text model can be used for chat and selected report-drafting paths.

## OpenAI-compatible endpoints

Configure the base URL and credential only when an appropriate endpoint is already available. Cloud access is disabled by default and endpoint safety checks reject unsafe destinations unless the runtime is explicitly configured to allow them.

## Optional local adapters

Install optional packages with:

```powershell
.\scripts\setup_windows.ps1 -WithOptional
```

or:

```bash
MEDRAY_INSTALL_OPTIONAL=1 ./scripts/setup_unix.sh
```

Available adapter boundaries include:

- TorchXRayVision DenseNet-121 for research-only multi-label CXR classification.
- A reviewed local Ultralytics adapter for MSK fracture bounding-box candidates.
- A bounded LocateAnything output parser; the model itself is not bundled or automatically executed.

## Model-card gate

Downloaded or imported artifacts remain inactive until the local model card is reviewed. A card should record intended use, task, license, dataset provenance, limitations, and validation evidence. Weights identity is tracked with hashes where supported.

Model output is always candidate evidence. It is not automatically a diagnosis, triage decision, or proof of pathology.
