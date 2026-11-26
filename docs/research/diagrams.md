# Secret Wards diagrams

## Confirmed challenge breakdown

```mermaid
flowchart TD
    A[Hospital exports for public-health research] --> B[Read each supported format safely]
    A --> C[Find identifiers and protect clinical values]
    A --> D[Link records that share credible patient evidence]
    A --> E[Reduce identifying combinations in the release]
    B --> F[Release, index and report]
    C --> F
    D --> F
    E --> F
    F --> G[Privacy, utility, integrity and reliability evaluation]
```

A useful release needs readable data, accurate patient histories, and fewer ways to identify a person. The judges measure all three along with processing behavior. [Brief](../PROBLEM_STATEMENT.md) · [Scoring](../SCORING.md)

## Verified starter architecture and module dependencies

```mermaid
flowchart LR
    Driver[starter main] --> Policy[load_policy and environment]
    Driver --> Decode[decode]
    Driver --> Adapter[CSV, JSON and text handlers]
    Adapter --> Clean[clean_text and clean_value]
    Adapter --> Link[link_records returns null]
    Driver --> Outputs[sanitized files, report and index]
    Outputs --> Contract[validate_output]
    Outputs --> Score[check_dev]
    Truth[Practice truth] --> Score
    Sub[check_submission] --> Driver
    Sub --> Contract
```

The starter handlers clean one file at a time. The checkers sit outside the pipeline, and only the local self-check sees the practice truth. The date and age helpers are currently unused during a run. [Starter](../../starter/main.py#L35) · [Pre-submit runner](../../check_submission.py#L173) · [Local self-check](../../check_dev.py#L84)

## Verified starter data flow and failure handling

```mermaid
flowchart TD
    A[Enumerate next sorted input file] --> B[Read all bytes and compute SHA-256]
    B --> C{Supported extension, nonempty and decodable?}
    C -->|Yes| D[Parse or scan text]
    D --> E{Handled parse or transform error?}
    E -->|No| F[Write UTF-8 at the existing relative path]
    F --> G[Buffer a sanitized manifest entry]
    C -->|No| H[Buffer a quarantine manifest entry]
    E -->|Yes| H
    G --> I{More input files?}
    H --> I
    I -->|Yes| A
    I -->|No| J[Write records.jsonl and report.json]
    B -. Read failure outside per-file handler .-> K[Run can terminate with partial output]
    F -. Unhandled I/O error .-> K
```

Recognized failures become report rows. A failure outside the error types the starter catches can terminate before it writes the final manifest. [File loop and output](../../starter/main.py#L211)

## Documented interaction flow

```mermaid
sequenceDiagram
    actor Team
    participant Kit as Starter and public checks
    participant Repo as Team submission
    participant Judge as Organizer evaluator
    Team->>Kit: Reproduce the starter baseline on practice data
    Team->>Repo: Prepare the runnable package and brief during the event
    Team->>Kit: Check format, repeatability and practice metrics
    Team->>Judge: Submit public repository link and two-page PDF
    Judge->>Repo: Freeze the submission commit
    Judge->>Repo: Run setup with network enabled
    Judge->>Repo: Run on hidden inputs with read-only input and no network
    Repo-->>Judge: Sanitized files, report and records index
    Judge-->>Team: Scorecard
```

The hackathon workflow centers on a command-line batch. The evaluator prepares the repository, calls the command, and scores the output. [Submission instructions](../PROBLEM_STATEMENT.md#4-submission-format) · [Execution contract](../SPEC.md#1-repository) · [Fairness](../FAIRNESS.md)

## Hypothetical alternative designs

```mermaid
flowchart TD
    A[Raw input behind a trust boundary] --> B[Format-specific reader]
    B --> C[Context rules and format evidence]
    B --> D[Feature extraction with optional learned detector]
    C --> E[Deterministic anchors and conflict checks]
    D --> F[Blocked probabilistic matching and conflict checks]
    E --> G[Evaluate cluster confidence]
    F --> G
    G --> H[Compare uniform and selective privacy policies]
    H --> I[Render and verify release]
    I --> J[Publish research release and report]
```

The alternatives share format and safety work. Their detection and linkage components can also be tested independently in mixed combinations. Uniform versus selective privacy is a separate decision downstream of patient grouping. [Feasibility matrix](feasibility-analysis.md) · [Existing privacy approaches](existing-solutions.md)

## Hypothetical release decision tree

```mermaid
flowchart TD
    A[Input file] --> B{Can we parse the file within limits?}
    B -->|No| C[Quarantine and use a controlled reason]
    B -->|Yes| D{Can privacy and format checks pass?}
    D -->|No| C
    D -->|Yes| E{Is patient evidence sufficient?}
    E -->|No| F[Keep index patient value null]
    E -->|Yes| G[Use a patient pseudonym for matching records]
    F --> H[Apply policy for dates, ages and locations]
    G --> H
    H --> I{Clinical values, references and locators preserved?}
    I -->|No| C
    I -->|Yes| J[Stage sanitized output and reconcile reports]
    J --> K{All inputs accounted for and only safe outputs present?}
    K -->|Yes| L[Publish completed release]
    K -->|No| M[Fail with a controlled diagnostic]
```

This candidate describes how safe parsing, abstention, and release checks could fit together. The uncertain-date policy and organizer constraints on output fields still need to be resolved. [Edge cases](outliers-and-edge-cases.md) · [Contract questions](open-questions.md)

## Research dependencies for Wayfinder

```mermaid
flowchart TD
    A[Agreed objective: robust unfamiliar-input performance] --> B[Capacity and team skills]
    C[Contract ambiguities] --> D[Define valid fixtures and scored invariants]
    B --> E[Bound prototype effort]
    D --> F[Compare role-aware multilingual detection]
    D --> G[Compare conflict-aware linkage]
    D --> H[Compare privacy policies and integrity]
    E --> F
    E --> G
    E --> H
    F --> I[Compare independent results and integration cost]
    G --> I
    H --> I
    I --> J[Choose a measured differentiator and plan the build]
```

The first decision sets the objective. Capacity and contract facts determine which tests can meaningfully separate the candidates. The resulting evidence feeds the later Wayfinder discussion. [Decision frontier](open-questions.md) · [Experiments](feasibility-analysis.md#experiments-for-the-prototype-phase)
