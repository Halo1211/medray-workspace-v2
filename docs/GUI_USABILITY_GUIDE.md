# GUI Usability Guide

This guide translates human-factors and radiology-workstation principles into practical MedRay interface rules. It is design guidance for a research prototype, not evidence of regulatory compliance or formal usability validation.

## Core principles

1. **Task-first, feature-preserving.** Keep the workflow aligned to `Import → Route → Review image → Inspect AI signal → Review annotation → Draft report → Export`. Place specialist controls behind consistent disclosure instead of removing them.
2. **Persistent study identity.** Keep the case label, study, series, view, laterality, and active-image identity visible wherever evidence is reviewed.
3. **Staged disclosure.** Surface image quality, anatomy route, active models, confidence, review state, and the next safe action before technical traces.
4. **Redundant status cues.** Distinguish demo, fallback, AI signal, human-reviewed, rejected, uncertain, and protocol-validated states with text or icons as well as color.
5. **Reversible work.** Preserve annotation revision history and require clear confirmation around deletion, risky export, and runtime changes.
6. **Accessible interaction.** Important controls must be keyboard reachable, visibly focused, sufficiently large, and usable without drag-only gestures.
7. **Local safety copy.** Place concise warnings next to the action they govern.

## Reading Room

- Keep the active case and image context in the header.
- Provide an immediate **New case** action that resets transient workspace state without a page refresh.
- Keep image tools near the viewer and evidence tools in the review panel.
- Treat AI annotations as proposals: display origin, source model, confidence, review state, and revisions.
- Support origin, review-state, and minimum-confidence filters without hiding manual annotations behind an AI threshold.
- Allow batch accept/reject only for visible, unreviewed AI proposals.
- Make rerunning AI explicit and preserve human edits as auditable revisions.
- Show confidence as a percentage, but never as a diagnosis or calibration claim.

## Case Library and validation

- Keep validation in the same page as the registry but above the long, internally scrollable case list.
- Load cases in bounded batches and retain search, rename, open, and delete actions.
- Make the difference between “no reference label” and “AI output not reviewed” explicit.
- Preserve the current case context when opening validation.

## AI Setup

- Keep the demo available without setup.
- Separate provider connections from specialist classifiers because their inputs and outputs differ.
- Let vision, chat, and report tasks keep independent tested provider assignments.
- Describe hosted-provider data egress before enabling any request.
- Show why a model cannot be activated next to the disabled action.
- Treat downloaded, reviewed, technically ready, and protocol validated as separate states.

## DICOM safety

- Summarize patient tags, private tags, burned-in pixel risk, UID changes, and source preservation before export.
- Group preview changes as removed, replaced/regenerated, and retained.
- Require a clear pixel-review acknowledgement when burned-in or high-risk content may remain.

## Light and dark themes

- Verify contrast for selected cards, muted copy, badges, outlines, disabled controls, and the logo in both themes.
- Do not reuse dark-theme surfaces or muted colors in light mode.
- Preserve the same visual hierarchy and focus visibility across themes.

## Usability test checklist

- A new user can import a study and find the analysis action without reading long documentation.
- A user can identify the active image at a glance.
- A user can answer which model produced an output, its confidence, and whether it was reviewed.
- A user can switch cases without refreshing the browser.
- A user cannot export a high-risk DICOM without seeing the reason and acknowledging pixel review.
- Keyboard focus remains visible when panels and tabs change.
- Errors provide a recovery action rather than a raw exception.
- Representative users complete realistic tasks while completion rate, time, interaction errors, near misses, and SUS are recorded.

## References

- [FDA: Applying Human Factors and Usability Engineering to Medical Devices](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/applying-human-factors-and-usability-engineering-medical-devices)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [W3C cognitive accessibility objectives](https://www.w3.org/WAI/WCAG2/supplemental/objectives/o1-understandable/)
- [GOV.UK: Structuring forms](https://www.gov.uk/service-manual/design/form-structure)
- [GOV.UK: Check answers](https://design-system.service.gov.uk/patterns/check-answers/)
- [Microsoft: Progressive disclosure controls](https://learn.microsoft.com/en-us/windows/win32/uxguide/ctrl-progressive-disclosure-controls)
- [Design Requirements for Radiology Workstations](https://pmc.ncbi.nlm.nih.gov/articles/PMC3043976/)
