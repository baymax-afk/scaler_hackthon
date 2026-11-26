# Developer B handoff for Version 2

Own the additional synthetic corpus, its annotation and split integrity, and independent evaluation. Developer A owns production parsing, detection, linkage, privacy transformations and release. Start with the shared annotation example and corpus design while A probes the release boundary. The [Phase A handoff](developer-b-handoff.md) records the earlier division.

## Start from main

In your clone, fetch the published handoff and create a sibling worktree.

```sh
git fetch origin main
git worktree add -b feature/robustness-v2-data ../t3_scaler-data-v2 origin/main
cd ../t3_scaler-data-v2
git status --short --branch
```

Use your existing worktree if the branch already exists. Keep open-data generation and evaluation in small, separately reviewable pull requests. Keep experimental code on a separate prototype branch. Contact A before changing the shared locator, span or evaluation conventions. [Git workflow](development-plan.md#git-collaboration)

## First independent slice

1. Share one **open synthetic** record with a stable opaque ID and locator, original code-point spans, a surface used in two roles, expected edits, protected clinical facts and an input disposition. Include one example prediction with an explicit incomplete status. A can use this example through the CLI or detector seam.
2. Plan families and institutions before rendering. Reserve **1,000 development, 400 validation and 600 sealed** Patient Records. The final valid-record quotas are **400 CSV, 300 TSV, 400 JSON, 400 FHIR and 500 text**. Put malformed inputs in a separate versioned fixture suite. Maintain the original 2,000-record corpus as its own regression dataset.
3. Start with a development-only vertical slice. Demonstrate generation, manifest hashing, structural validation, original-coordinate round-trips, protected-span scoring and detection of a deliberate split collision. Validate FHIR R4 and separately validate any ABDM profile claims.
4. Prepare the common evaluator under `evaluation/`. Join by opaque record ID, locator and input digest. Separate exact and partial span metrics, file disposition, all-input utility and clinical hard-negative preservation, and eligible linkage pairs and False Merges. Score only adjudicated units for precision or false-positive rate and preserve incomplete/undefined outcomes. Run Version 1 first by pinned SHA.
5. Share the branch and base SHA, reproducible commands, counts, known gaps and the next open interface decision. Keep review evidence free of identifiers and report only allowed aggregates from the sealed split.

## Custody and integration

- You own independently authored sealed families. Keep their inputs, templates, seeds and annotations out of the shared repository, detector workspace and PRs. Keep patients, institutions, template families and near-duplicates within one split. Share only digests and agreed aggregate validation evidence.
- On the shared branch, restrict tracked artifacts to authorized synthetic open data, source, documentation and outputs with no sensitive values. Keep opaque truth and predictions separate from runtime inputs. Place new dataset tools alongside the existing corpus under `docs/datasets/`. Own `evaluation/`; coordinate any interface change into `submission/` with A.
- Run the sealed comparison on frozen Version 1 and Version 2 revisions and configuration. Release aggregate counts and denominators after the run. If findings guide tuning, reclassify that split as development and establish a fresh holdout.
- Fixture generation and evaluator checks can start together from the open example. Full dataset design and scoring gates should be reviewed at the first checkpoint. Keep model training and hybrid work behind the agreed readiness and approval gates.

[Dataset protocol](research/dataset-v2-design.md) · [Development plan](development-plan.md#version-2-planning-and-handoff) · [Version 1 benchmarks](research/generalization-analysis.md)
