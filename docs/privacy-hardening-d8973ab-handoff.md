# Privacy hardening and submission handoff from d8973ab

Source commit: `d8973ab06f368f1ae3f1f4a4e285844384961fd6` (`Merge remote main and reconcile Version 2 dataset guides`). Working branch: `privacy-hardening-d8973ab`. This branch started from a clean worktree because the other local checkout has CRLF-only modifications that invalidate a byte-hash fixture.

## Changes

- Every sanitized output file and directory now receives a `RAKSHA_SECRET`-keyed HMAC path component. Paths retain only the required format extension. This removes the need to recognize an identifier in the original path before hiding it. The report still maps input SHA-256 to the output path, as required by the contract.
- The detector recognizes `Janm Tithi` and `Janam Tithi` as birth-date field labels. A proposed dash separator was removed after independent review found it could redact a clinical sentence under a `Patient - ...` heading.
- The local open-slice auditor now joins release paths through the report ledger and accepts safe renamed paths. It continues to reject traversal, duplicate paths, missing outputs, and incomplete record indexes.

## Measured checks

These are local practice/self-check numbers, not an official or hidden score. Runs used the organizer's synthetic `dev/input` with a disposable practice secret. No source values or secret are included here.

| Measure | Clean d8973ab | This branch |
| --- | ---: | ---: |
| Visible labeled identifiers | 581 / 3,230 (18.0%) | 541 / 3,230 (16.7%) |
| Filename-channel visibility | 20.8% | 0.0% |
| DOB visibility | 30 / 111 | 0 / 111 |
| Preserved medical probes in exported files | 4,382 / 4,382 | 4,382 / 4,382 |
| Preserved medical probes across all input | 4,382 / 4,855 (90.3%) | 4,382 / 4,855 (90.3%) |
| Sanitized / quarantined files | 168 / 32 | 168 / 32 |
| Canaries / raw copies / false patient merges | 0 / 0 / 0 | 0 / 0 / 0 |
| Patient linkage precision / recall / F0.5 | 0 / 0 / 0 | 0 / 0 / 0 |

Branch practice output passed `validate_output.py`. `check_submission.py --repo submission --run` passed three-run contract and determinism checks, with warnings for the required two-page Project Brief PDF and optional policy file. Its different-secret check sees renamed paths; it does **not** prove secret-derived pseudonyms or date shifts. Submission tests: 11/11 pass. Evaluation tests: 37/37 pass. The Version 2 development generator's 1,000 records were all indexed, with 1,448/1,448 protected spans preserved and zero linked pairs; its 1,558 literal labeled residuals remain. These open annotations are generated, not independently adjudicated.

Reproduce from the repository root (use a fresh output directory for each run):

```sh
PYTHONPATH=submission python3 -m unittest discover -s submission/tests -p 'test_*.py'
python3 -m unittest discover -s evaluation -p 'test_*.py'
RAKSHA_SECRET=practice python3 submission/main.py --input dev/input --output /tmp/secret-wards-practice
python3 validate_output.py --input dev/input --output /tmp/secret-wards-practice
python3 check_dev.py --output /tmp/secret-wards-practice --show 0
python3 check_submission.py --repo submission --run
```

## Remaining submission gates, highest priority first

1. **Privacy and clinical policy:** 541 practice identifiers remain visible, especially in Hindi/Hinglish narrative and metadata fields. Do not apply broad name redaction without testing clinician-name and clinical-term homonyms. Build a release-level quasi-identifier assessment and safe generalization policy. Recheck medical preservation and all-input clinical coverage after each change.
2. **Identity linkage:** `records.jsonl` still has null `patient` for every record. There are no secret-derived patient IDs or date shifts. Implement conservative cross-script linkage with abstention, test false merges, and make changed-secret checks inspect actual patient IDs and dates rather than only renamed paths.
3. **Required artifact:** Prepare and submit the two-page Project Brief PDF with the actual team roster, architecture, measured trade-offs and limits. The checker warns because no PDF is present. Run the submission checker against `submission/`, which contains `raksha.toml`; the repository root is a development workspace, not the packaged entrypoint.
4. **Version 2 evidence:** Complete independent open-label review, the sealed private split, split-neutral scoring, and a frozen V1/V2 comparison from `docs/developer-b-v2-remaining-handoff.md`. Resolve the candidate indexing gate (362/1,400 on d25e72a versus 1,400/1,400 on V1) before promoting a new candidate. The rejection fixture expecting invalid UTF-8 quarantine conflicts with the allowed cp1252 fallback and needs a policy or fixture decision.
5. **Contract depth:** Validate emitted FHIR against the required R4/ABDM profiles, exercise adversarial attack cases, and measure false joins and quasi-identifier exposure on held-out data. Passing the format checker alone does not establish scoring readiness.

Use the 900-second main contract limit while the toolkit's large-profile 1,800-second value is clarified with organizers. The clean baseline ran from `/tmp` while this worktree is under `/mnt/c`; their wall times are not a controlled runtime comparison.
