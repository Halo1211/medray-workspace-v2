# MedRAX Adapter

MedRay does not copy MedRAX. It provides a narrow adapter boundary so an external research tool can participate without changing UI or storage contracts.

## Goals

- Normalize findings, annotations, reports, warnings, and model traces.
- Preserve explicit failure and fallback states.
- Distinguish model coordinates, masks, fallback regions, and human annotations.
- Keep localization evidence reviewable and exportable.
- Persist the runtime snapshot required to audit a result.

## Tool contract

An adapter receives a bounded context containing the case identifier, stored image path, preview path, image metadata, custom prompt, and runtime settings. It returns:

- `task_type`: classification, segmentation, grounding, VQA, report, or utility.
- `status`: ok, fallback, skipped, or failed.
- `model`: the actual model identifier.
- `outputs`: a locally safe raw payload.
- `normalized`: supported result fields.
- `warnings`: limitations and failure conditions.

Coordinate-producing tools must also return coordinate space, source and model-input dimensions, resize/crop/padding transforms, coordinate or mask provenance, and links to related findings when available.

## Integration order

1. DICOM utility and metadata validation.
2. Chest X-ray classification with calibration warnings.
3. Annotation provenance, revision, and export.
4. Grounding only when coordinates originate from a reviewed model.
5. Segmentation only when masks and transforms remain auditable.
6. Report generation from reviewed structured evidence.
7. VQA or planning after deterministic tools are stable.

## References

- [MedRAX repository](https://github.com/bowang-lab/MedRAX)
- [MedRAX paper](https://arxiv.org/abs/2502.02673)
