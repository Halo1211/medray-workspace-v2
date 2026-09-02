# Validation Workbench

The Validation Workbench is a local research tool for comparing model outputs with curated labels. It is an agreement and traceability workflow, not a clinical performance claim generator.

## Workflow

1. Open **Validation Workbench**.
2. Create or load a curated fixture.
3. Enter a case ID, protocol ID, source image/series identity, labels, and reviewer notes.
4. Save the label locally.
5. Run the validation check.
6. Review agreement metrics, false-alert burden, missed-reference summaries, runtime/model references, and limitations.
7. Export the validation report and preserve the protocol and dataset context with it.

## Evidence expectations

Useful validation evidence should identify:

- dataset and split;
- protocol and label definitions;
- sample counts and inclusion criteria;
- metric definitions and failure summaries;
- coverage, reviewer, and review date;
- exact model artifact and weight hash where available.

Do not describe a local agreement result as clinical accuracy without an appropriate study design and external review.

## Related documentation

- [Model Integration](Model-Integration.md)
- [Contributing](Contributing.md)
- The main repository's `docs/VALIDATION_WORKBENCH.md` and `docs/MSK_LOCALIZATION_PILOT.md` contain the detailed design notes.
