# AI setup overhaul — implementation audit

Baseline, 2026-09-05 (before source changes): backend 141 passed / 1 skipped;
frontend 14 passed; TypeScript and Vite build passed. Initial commands failed because
system Python lacked core dependencies and PATH selected Node 21.7.2. A project
venv and supported bundled Node were used for the baseline. Existing user change
to frontend/public/medray-v2-logo.png is preserved.

## Findings and design

The React entry point mixes Model Finder and two Runtime Settings experiences.
The simple connection test always probes Ollama even for an OpenAI server. It
assigns one model to vision, report and chat without testing those capabilities.
Model Finder shows heuristic fit percentages that are not runtime compatibility.
HF login exists but has no authentication test and is hidden under Advanced.

Backend integrations: deterministic demo, Ollama chat/vision, OpenAI-compatible
chat, TorchXRayVision chest classifier, reviewed local Ultralytics MSK detector.
LocateAnything is a parser; MedRAX is an interface boundary. Transformers packages
in optional requirements do not implement a general Hugging Face runtime.
Segmentation has no executable model adapter. Existing model cards, human review,
structured validation evidence, audit provenance and anatomy routing are retained.

TorchXRayVision checks package discovery rather than import/load/inference. Image
normalization is applied twice; weights can download invisibly during analysis.
Download manager persists jobs, but restart states need reconciliation, a server
ignoring Range can corrupt a resume, short responses can be marked complete, and
redirects can forward credentials across origins. Windows startup lacks frontend
readiness/browser opening, setup exit-code checks and duplicate launch handling.

Design: one AI Setup entry, task-oriented Quick Setup, X-ray Vision wizard,
Local AI, Online AI, Find Models, My Models, System Check and Advanced. Backend
readiness distinguishes artifacts/dependencies/test/review/validation. Technical
readiness never means clinical validity. No general HF compatibility is inferred
from a model name or file extension; unsupported repositories explain why.

References inspected: official TorchXRayVision models/utils source, PyTorch local
installation guide, Hugging Face token documentation. No remote model code is run.

## User-directed redesign, 2026-09-06

The earlier Advanced/Localization design above is superseded. AdvancedRuntimeSettings and the old ModelFinder component were deleted, including duplicate connection, auth, search and download forms. Local import/model-card editing now lives only in My Models; account controls only in Find Models; downloads have one queue. Preferences merge only their own allowed fields. Quick Setup is the default with the other sections in a sidebar. TorchXRayVision lives in My Models as one specialist choice. The new Ultralytics installer/test/activation endpoints were removed; historical annotation formats and legacy pipeline compatibility were retained.

General compatible-server integration now handles image input and structured report generation, in addition to chat. Switching servers clears other external task assignments to avoid sending stale model selections to a different provider. Cloud image input keeps the existing opt-in boundary.

Following the user's request, verification of this revision is targeted; no repeated full suites or large model downloads.

## Capability recovery and guided-flow revision, 2026-09-06

Comparison with the previous Model Finder and the current repository exposed an unintended regression: the simplified screen had lost combined Hugging Face/GitHub/Ollama discovery, hardware- and task-aware recommendations, richer ranking, expanded-query feedback, pagination, detailed repository inspection, direct file queueing, and the handoff from reviewed source metadata to local model cards. Those capabilities are restored in a dedicated ModelDiscovery component while the single-owner structure remains: local import/model-card editing stays in My Models and queue lifecycle stays in Downloads.

AI Setup now exposes a persistent four-stage flow (goal, connect/find, technical test, use), beginner goal cards, Indonesian/English copy, and progressive disclosure for advanced tools. Advanced preferences remain a strict allowlist; the newly exposed localization threshold is validated as a numeric value from 0 through 1 in both frontend and backend. Provider keys remain masked, server-bound, and excluded from discovery results and audit content.
