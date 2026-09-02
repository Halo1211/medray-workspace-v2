# Safety

MedRay v2 is intended only for research, education, prototyping, and controlled validation. It is not a certified medical device or clinical diagnostic system. Also read the repository-level [medical disclaimer](../DISCLAIMER.md).

## Output rules

- Never state an uncertain model suggestion as a confirmed diagnosis.
- Show confidence and uncertainty where the source provides them.
- Keep observations, reasoning, and impressions distinct.
- Label annotations with their source and generation method.
- Never present deterministic fallback guides as clinical model localization.
- Keep the report watermark: `AI-assisted draft, not for standalone clinical diagnosis.`
- Require a deliberate human-review step before export.

## Data handling

- Prefer synthetic data during development and demonstrations.
- Treat every DICOM object as potentially identifiable.
- Check metadata, private tags, filenames, logs, and burned-in pixel text.
- Do not expose the local API to an untrusted network.
- Do not send images to an external provider without authorization and a documented data-handling basis.

De-identification reduces risk but is not a guarantee. Validate the result with an approved institutional process before sharing it.
