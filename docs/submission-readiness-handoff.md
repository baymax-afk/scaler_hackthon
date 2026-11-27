# Submission readiness handoff

**Start here after merging the generalization and privacy work.** This repository is the development checkout. The judged repository needs the contents produced by `prepare_submission.py` at its root, plus the final team brief. Merging the development branch does not submit an entry. [Runbook](../START_HERE.md#run-this-teams-submission) · [Organizer deliverables](PROBLEM_STATEMENT.md) · [Runtime contract](SPEC.md)

## Starting evidence

| Latest verified public result | Interpretation |
|---|---|
| Practice exported 168/200 files, including 166/192 required files. 529/2,940 direct-identifier labels in exported files were still visible. | 166 patient-name labels remained. In 29 files both a patient-name label and a geographic label were visible. A file can contain multiple patients. |
| Practice preserved 4,382/4,855 clinical probes across input files and 4,382/4,382 in exported files. | Report coverage with utility. Current cross-file linkage abstains. Secret rotation changes keyed paths. |
| Open development and validation exported 1,400/1,400 records, fully transforming 2,892/4,391 labeled identifiers and preserving 2,000/2,000 protected spans. | 1,494 identifier occurrences remained visible and five partly visible. The 2,000-record original regression reproduced its historical audit. Independent sealed evaluation is pending. |

Use these numbers as regression comparators. The practice checker searches whole files. Mapped occurrence results and the organizer's attacker score answer different questions. [Paired practice results](research/attacker-defense-evidence.md) · [Open results and benchmark limitations](research/detector-performance-report.md)

## Engineering work before declaring the product ready

| Order and owner | Work and module | Completion evidence |
|---|---|---|
| 1 · B, evaluator and data | Reconcile every input hash, disposition, record locator, output and reason. Adjudicate residual patient and relative names versus clinicians and hard negatives at their actual occurrences. Review duplicate strings, suppressed records and partial spans. Keep annotations outside inference. | Publish denominator-explicit reports for input and exported records, residual identifiers, clinical preservation, coverage, and script/format subgroups. Report precision only on exhaustively annotated units. |
| 1 · A, adapters and release | Address the two known rejection-fixture discrepancies (ambiguous encoding and metadata-only indexing). Support valid cp1252. Define which byte sequences can be distinguished reliably. Correct metadata classification and index legitimate records independently of redaction. | Exercise the real CLI with valid legacy input, ambiguous/broken input, metadata, duplicate files and clean patient records. Assert ledger, index and disposition and check for raw output after failure. |
| 1 · A, detector | Triage the remaining name, MRN and relative-name leaks and poor TSV coverage. Include unmarked identities, alternate headers, Unicode, filenames, narrative nodes, attachments and identifiers adjacent to doses. | Each change has an unseen positive and a clinical or clinician control. Compare occurrence results, all-input clinical probes and exported records against this baseline. |
| 2 · B, linkage; A, adapters | Resolve conservative patient clusters from source evidence before transformation. Require corroboration for weak names and conflicting identifiers. Produce per-release keyed pseudonyms and propagate them into both records and index across formats. | Exercise same-patient and homonym pairs, conflicting identifiers, repeated encounters and key rotation. Report false merges, missed links, abstentions, pairwise F0.5, cluster metrics and pseudonym consistency. |
| 2 · A, privacy layer; B, evaluation | Implement patient-consistent date transformations and truthful age/location generalization where policy calls for them. Assess distinctive combinations including rare diagnoses, geography and visit timing. Coordinate stable identity and transform policy with linkage. | Verify age-band containment, interval preservation, leap and year boundaries, rotating keys, and clinical hard negatives. Report unique or small patient groups, generalization and suppression alongside retained coverage. |
| 2 · A, FHIR and export | Validate R4 structure and references after transformation, including narrative, typed dates, contained resources and supported attachments. Inspect URL-only and unsupported attachment forms. Revisit required-file quarantines on practice. | Record profile/validator scope; verify readable safe attachments, consistent references, preserved units, deterministic quarantine and no partial exports. |
| 3 · B, independent release review | Check released records, filenames, report, index, stdout/stderr, logs and private temporary/home directories. Review raw mappings, keys, staging cleanup, file permissions and at-rest storage assumptions. | Preserve aggregate evidence for malformed, oversized and interrupted runs; check canaries, raw copies and side channels. Distinguish name/geography co-exposure from a measured re-identification rate. |
| 3 · B, independent custodian | Freeze runtime revision, package digest, configuration and open benchmark commands. Run the independent 600-record sealed assessment under the custodian's control. | Share aggregate metrics by format, script, role and layout with limitations. Keep sealed inputs and truth private. Reclassify a test used for tuning and obtain a new holdout. |

A and B can begin the first three rows concurrently in separate branches. B owns evaluation and sealed access; A owns release integration. Coordinate source coordinates, identity evidence and locator contracts before changing either side. A learned model, hybrid fusion and neural regularization are deferred experiments with separate approval and data prerequisites. The offline deterministic CLI is the submission candidate. [Engineering spec](GENERALIZATION_SPEC.md) · [Workstream plan](development-plan.md) · [Organizer attacks](ATTACKS.md)

## Final delivery checklist

- [ ] **Team lead** confirms the public judged GitHub repository, display name, member attribution, event deadline and submission channel. Rehearse from a fresh clone of the exact judged revision.
- [ ] **A** builds a fresh runtime directory and verifies the manifest, README, dependency declaration and runtime modules. Keep private datasets, evaluator truth, raw mappings, keys, local outputs and caches out of delivery. Verify the allowlist again when adding modules.
- [ ] **B** runs the commands below on the candidate and retains aggregate metrics, benchmark revisions, config and resource measurements. Inspect quarantine reasons and required-file coverage. Check the organizer constraints on Linux with two CPU cores, 4,096 MB, 15 minutes, no network, read-only input and private scratch. The local checker exercises the contract; official isolation needs an appropriate runner.
- [ ] **Team lead and B** finalize the README and a readable two-page PDF with team and repository details, architecture, attack defenses, key management, encryption responsibilities, measured privacy/utility/linkage, runtime, peak memory and limitations. Add the approved PDF to the judged root or a subdirectory after packaging. The packager currently carries runtime files only. A policy YAML is a checker recommendation. [Brief requirements](PROJECT_BRIEF.md) · [Template](../brief/PROJECT_BRIEF_TEMPLATE.md)
- [ ] **Team lead** verifies a fresh public clone contains root-level `raksha.toml`, runs the declared command, checks the exact PDF and commit, and submits the repository link and PDF via the organizer's channel. Record the submitted SHA and receipt. Publication of a separate judged repository and delivery to the organizer are separate actions.

From the development checkout, run:

```sh
PYTHONPATH=submission python3 -m unittest discover -s submission/tests
PYTHONPATH=.:submission:evaluation python3 -m unittest discover -s evaluation
PYTHONPATH=.:submission:evaluation python3 -m unittest discover -s docs/datasets/robustness_v2
work=$(mktemp -d)
python3 prepare_submission.py "$work/team"
python3 check_submission.py --repo "$work/team" --run
RAKSHA_SECRET=practice python3 "$work/team/main.py" --input dev/input --output "$work/out"
python3 validate_output.py --input dev/input --output "$work/out"
python3 check_dev.py --output "$work/out"
python3 evaluation/evaluate.py practice-audit "$work/out"
```

Use the public practice key only for rehearsal. The organizer supplies the event secret. Replay the original and open suites using the [versioned benchmark instructions](research/detector-performance-report.md) and [open dataset guide](datasets/robustness_v2/README.md). Claim readiness for submission mechanics, privacy outcomes and final event delivery separately, with evidence for each.
