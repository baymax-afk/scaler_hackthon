# Secret Wards Wayfinder diagrams

The [Secret Wards hackathon decision map](https://github.com/baymax-afk/scaler_hackthon/issues/1) is the canonical tracker. Its tickets carry the questions, ownership and current dependencies.

## Destination and first frontier

Plan a format-preserving **Research Release** that protects patient identities and keeps clinical facts useful on unfamiliar synthetic exports. The team has 24 total person-hours. One person owns ingestion, FHIR export and Linux packaging. The other owns multilingual detection and linkage evaluation. The team chose unfamiliar field-role inference as the first comparison. The showcase feature is still a decision. [Problem statement](PROBLEM_STATEMENT.md) · [Existing feasibility estimates](research/feasibility-analysis.md)

Privacy (25%), detection (20%), and clinical utility (20%) account for 65 points before penalties. Patient identity consistency (15%), integrity (10%), and reliability (10%) account for the rest. The kit reported `CONTRACT OK` on the starter while the practice checker observed 84.1% of annotated PII mentions still visible, all four Canary identities, and zero patient links. The organizers' reference scored 84.84 on standard normal data and 50.33 on standard unfamiliar-format data. These are two different baselines. [Scoring](SCORING.md) · [Starter measurements](research/codebase-overview.md#baseline-measured-in-this-checkout)

DevForge publishes an absolute code freeze at **09:00 IST on Friday, November 27, 2026**. The general rubric includes innovation, technical complexity, feasibility, impact and presentation, with shortlisted teams presenting live. Track 3 also requires a public event-created submission repository and a two-page brief. The configured planning repository is currently private and GitHub records its creation at 09:00:18 IST on Day 0. The eligibility of the starter import is open. Reserve time before the freeze for preflight on the commit the judges will receive. [DevForge rules](https://yugaantar.org/events/devforge) · [Track 3 requirements](PROBLEM_STATEMENT.md) · [Verify organizer rules that affect submission and export](https://github.com/baymax-afk/scaler_hackthon/issues/2)

| Status at charting | Decision or evidence |
| --- | --- |
| Already set | Synthetic-only data, offline CPU submission, format-preserving output, safe quarantine, repeatable keyed pseudonyms and safe abstention. The team prioritizes unfamiliar inputs and shared holdout evidence. |
| Ready now | Establish the holdout, verify access to a judge-like Linux runner, and select an eligible public submission repository. [Choose the eligible public submission repository](https://github.com/baymax-afk/scaler_hackthon/issues/14) |
| Blocked | Prototype conclusions depend on common fixtures. The release boundary depends on export and runtime evidence. The differentiator and submission plan depend on acceptance gates and comparative results. |
| Requires investigation | Exact organizer behavior for PII-bearing locators, permissible pseudonym placement and multi-patient Bundles; submission repository eligibility and any Track 3-specific live judging instructions; tool setup and measured benefit; performance on realistic skew and unfamiliar formats. |

The contract requires an input JSON locator in the index and also scans that index for identifying information. It requires a Patient Pseudonym in the record while limiting schema changes. Test both conflicts on synthetic fixtures. The problem statement and fairness guide use a per-dataset ranking margin, while the scoring guide describes a paired-significance rule. Use the documented 900 s cap for planning even though the scoring configuration lists 1,800 s for the large profile. [Submission contract](SPEC.md) · [Open organizer questions](research/open-questions.md)

| Decision type | Resolution skill or workflow |
| --- | --- |
| Research | Use Research to seek new first-party guidance. |
| Grilling | Use Grilling with Domain Modeling to settle team trade-offs and record durable terms or decisions. |
| Prototype | Use Prototype for a throwaway comparison with a measured result and a team verdict. |
| Task | Use the Wayfinder task workflow for shared fixtures and runner access. Use Wizard only if runner access requires manual provisioning the agent cannot perform. |

## Overall decision map

```mermaid
flowchart TD
    A["Known: judging weights, release contract, 24 person-hours"] --> B["P0: freeze synthetic holdout"]
    A --> C["P0: verify judge-like runner"]
    A --> D["P0: verify organizer clarifications"]
    B --> E["P1: compare detector, linkage and format export"]
    E --> F["P1: compare privacy policy and runtime shape"]
    C --> F
    D --> G["P1: choose the release boundary"]
    D --> K["P0: choose an eligible public submission repository"]
    F --> G
    G --> H["P2: agree on acceptance gates"]
    H --> I["P2: choose MVP scope and measured differentiator"]
    I --> J["P2: plan judge preflight and demonstration"]
    K --> J
```

## Native blocking dependencies

Arrows point from prerequisites to the decisions they unlock. The export test can probe documented cases and expose ambiguous ones while organizer research is underway.

```mermaid
flowchart LR
    Rules["Verify organizer rules that affect submission and export"] --> Boundary["Choose the fail-closed release boundary"]
    Rules --> Eligibility["Choose the eligible public submission repository"]
    Holdout["Freeze the synthetic holdout and comparison metrics"] --> Export["Test schema-safe export and honest quarantine"]
    Holdout --> Detection["Compare multilingual detection on unfamiliar field roles"]
    Holdout --> Linkage["Compare cross-script linkage and safe abstention"]
    Runner["Verify access to a judge-like Linux runner"] --> Runtime["Bound memory and runtime before choosing the batch shape"]
    Export --> Runtime
    Linkage --> Runtime
    Linkage --> Policy["Compare fixed and selective privacy policies"]
    Export --> Boundary
    Runtime --> Boundary
    Detection --> Gates["Set MVP privacy, utility and linkage acceptance gates"]
    Policy --> Gates
    Boundary --> Gates
    Gates --> Scope["Choose the MVP cut and the differentiator to demonstrate"]
    Scope --> Handoff["Choose the submission preflight and demonstration evidence"]
    Eligibility --> Handoff
```

## Alternative solution pathways

Mix and compare components on the same unseen synthetic patients, schemas and note templates. Candidate library versions and setup costs are documented in the research. [Technology survey](research/tools-and-technologies.md) · [Feasibility comparison](research/feasibility-analysis.md)

```mermaid
flowchart TD
    A["Reuse CLI, starter behavior as comparator and official checks"] --> D{"Which evidence extraction improves held-out results?"}
    D --> D1["Field roles, contextual rules and bounded normalization"]
    D --> D2["Custom recognizers or small classical model with labeled synthetic spans"]
    D1 --> L{"Which grouping is precise enough?"}
    D2 --> L
    L --> L1["Issuer-scoped anchors, bounded cross-script similarity and group conflicts"]
    L --> L2["Probabilistic pair scoring with explicit cluster constraints"]
    L1 --> P{"Which policy preserves utility at lower measured risk?"}
    L2 --> P
    P --> P1["Fixed truthful bands, geography and keyed patient date shifts"]
    P --> P2["Selective coarsening for rare patient groups"]
    P1 --> R{"Which batch shape meets the resource budget?"}
    P2 --> R
    R --> R1["Compact in-memory evidence with a bounded export pass"]
    R --> R2["Reread or segment input and evaluate encrypted spill only if needed"]
    R1 --> V["Compare on the same contract, clinical and resource gates"]
    R2 --> V
```

The first comparison starts with contextual field-role rules and asks whether additional evidence improves recall without erasing protected clinical spans. The team can use deterministic transliteration and fuzzy matching helpers for bounded linkage comparisons. Any learned model needs synthetic labels, a patient- and template-disjoint holdout, declared provenance and offline packaging. OCR, additional libraries and adaptive policies have to earn their time through measured benefit. [Technical candidates](research/tools-and-technologies.md) · [Evaluation plan](research/feasibility-analysis.md#experiments-for-the-prototype-phase)

## Critical decision points

```mermaid
flowchart TD
    A{"Can the file be read and safely transformed?"} -->|No| Q["Account for the quarantined file"]
    A -->|Yes| B{"Can the output keep format, references and safe locators?"}
    B -->|No or ambiguous| C["Use an organizer-approved or verified conservative handling path"]
    C -->|Unsafe to release| Q
    C -->|Exportable| D{"Is identity evidence sufficient and compatible?"}
    B -->|Yes| D
    D -->|No| E["Abstain and check local interval preservation"]
    D -->|Yes| F["Use a keyed Patient Pseudonym and patient-consistent date policy"]
    E --> G{"Are clinical, hygiene and accounting checks satisfied?"}
    F --> G
    Q --> G
    G -->|Yes| H["Complete the research release, index and report"]
    G -->|No| I["Fail with a controlled diagnostic or quarantine eligible file"]
```

Test the conflicts that change these choices: ambiguous dates, reused hospital IDs, homonyms and shared contacts, duplicate hashes, colliding keys, FHIR reference rewrites, and unsupported payloads. Pair a zero-observed-Canary-escape gate with held-out clinical retention, precision and risk measures. Confirm the conservative handling of disputed cases after the organizer review. [Edge-case matrix](research/outliers-and-edge-cases.md) · [Execution and output contract](SPEC.md)

## Shortest candidate path to a working MVP

```mermaid
flowchart TD
    A["Shared foundation: fixture slices, metrics and Linux preflight access"] --> B["Release track: minimal CSV, TSV, JSON, FHIR R4 and text handling"]
    A --> C["Evidence track: test unfamiliar field-role inference"]
    B --> D["Safe export, manifest reconciliation and quarantine"]
    C --> E["Conservative linkage and abstention with a keyed pseudonym"]
    D --> F["One end-to-end slice with fixed privacy policy"]
    E --> F
    F --> G{"Do normal and held-out runs meet release gates?"}
    G -->|Yes| H["Freeze the package and explain the best measured gain"]
    G -->|Gaps in required behavior| I["Fix required coverage and rerun the preflight"]
    I --> G
```

Use the previous budget estimate as a planning ceiling. A provisional allocation is 3 person-hours for shared fixtures and runner access, 5 for release and format handling, 5 for detection and linkage comparisons, 5 for policy and remaining compatibility, and 6 for integration, verification and the brief. Test a small end-to-end slice early, then widen to all required formats. The estimate needs evidence from the first slice. The official limits are 2 CPUs, 4 GB process-tree RSS and a 900 s run. Use the standard full-credit markers of 60 s and 512 MB as comparison points. [Budget basis](research/feasibility-analysis.md#packaging-and-budget) · [Scoring targets](SCORING.md#6-cpu-efficiency--reliability-10)

For the brief, pair a reproducible practice run with the unfamiliar-input comparison. Report privacy proxies, exact clinical preservation, false merges, quarantine coverage and resource usage with their denominators. Prepare a short live command-line run on a synthetic fixture if shortlisted. The local checkers cover only some of the official behavior. Add independent R4/reference, per-file accounting, channel, changed-secret and read-only input checks during the later preflight. [Project Brief requirements](PROJECT_BRIEF.md) · [Toolkit limitations](research/codebase-overview.md#baseline-measured-in-this-checkout)
