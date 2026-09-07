# GUI Redesign and Workflow

MedRay's interface centers one continuous research workflow:

`Import study → Run analysis → Review evidence → Validate annotations → Draft report → Export`

The application remains a research, education, and prototyping tool and is not an authorized diagnostic device.

## Design decisions

- Daily navigation contains Dashboard, Reading Room, Case Library, Guide, AI Setup, and About.
- The Reading Room exposes one primary next action at each stage while keeping specialist tools available.
- New cases and case switching reset transient state without a browser refresh.
- Anatomy routing, case metadata, prompts, image settings, and technical traces use progressive disclosure.
- Case registry and validation form one continuous workspace; the case list scrolls independently for large libraries.
- AI Setup uses a four-stage connection flow and keeps advanced controls optional.
- Light and dark themes share the same hierarchy, contrast targets, and optical logo alignment.

## Application startup

```mermaid
flowchart TD
    A[Open the MedRay folder] --> B{Operating system}
    B -->|Windows| C[Run setup_medray_v2.bat once]
    B -->|Linux or macOS| D[Run the setup script once]
    C --> E[Run start_medray_v2.bat]
    D --> F[Run start_medray_v2.sh]
    E --> G[Wait for backend and frontend readiness]
    F --> G
    G --> H[Open the local application]
```

## Reading workflow

```mermaid
flowchart TD
    A[Open Reading Room] --> B{Continue or start a new case?}
    B -->|New| C[Enter label and optional identifiers]
    B -->|Continue| D[Select a case from the library]
    C --> E[Import PNG, JPG, or DICOM]
    D --> F[Confirm active study and image]
    E --> F
    F --> G[Confirm or override anatomy route]
    G --> H[Run AI workflow]
    H --> I{Analysis completed?}
    I -->|No| J[Read recovery message and retry]
    J --> H
    I -->|Yes| K[Review findings and source confidence]
    K --> L[Filter and inspect annotations]
    L --> M{Edit, accept, reject, or rerun?}
    M -->|Rerun| H
    M -->|Review| N[Validate evidence and revision history]
    N --> O[Draft and review report]
    O --> P[Check identity and DICOM safety]
    P --> Q[Export reviewed results]
```

## AI configuration workflow

```mermaid
flowchart TD
    A[Choose AI task] --> B{Task type}
    B -->|Vision, chat, report| C[Choose local or hosted provider]
    B -->|Chest X-ray classification| D[Choose a reviewed classifier recipe]
    C --> E[Detect or enter model]
    D --> F[Install dependencies and verified weights]
    E --> G[Run synthetic task test]
    F --> G
    G --> H{Test passed?}
    H -->|No| I[Show bounded recovery guidance]
    I --> G
    H -->|Yes| J[Activate only for selected task]
```

## Safe-use checklist

- Confirm the case and active image before analysis.
- Keep automatic anatomy routing unless the metadata or image clearly requires correction.
- Distinguish classifier scores, VLM observations, AI coordinates, fallback regions, and human annotations.
- Review origin, confidence, uncertainty, evidence, and revisions before accepting an annotation.
- Do not promote unreviewed output into a final report.
- Review patient tags, private tags, UID handling, and burned-in pixels before DICOM export.
- Require qualified physician verification for every output.

## Validation target

Test the interface with representative users performing startup, multi-image import, analysis, case switching, annotation correction, report review, and risky-export interception. Measure task completion, time, errors, assistance, near misses, and System Usability Scale scores. Applying established patterns is not itself usability validation.
