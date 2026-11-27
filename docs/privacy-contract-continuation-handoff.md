# Privacy and submission continuation after db6ece2

Working branch: `privacy-hardening-d8973ab`, based on organizer merge `d8973ab`. This update corrects and supersedes the path-policy recommendation in `privacy-hardening-d8973ab-handoff.md`.

## Integrated changes

- `raksha.toml` is now at the GitHub repository root and runs `submission/main.py`, matching the toolkit's repository entrypoint contract.
- The release retains safe relative paths. It HMAC-renames only filenames with detected identifiers and records their output in the SHA-indexed report. A detected identifying directory component quarantines its files because the written contract requires retaining the folder tree. This resolves the unconditional-renaming conflict with `docs/SPEC.md` section 4. Undetected PII in paths remains a release risk.
- A filename-only pattern recognizes inpatient IDs shaped `IP-YY-NNNNN`; the rule does not run on clinical content.
- Typed fields now cover `Naam`, `Gaon`, `Pata`, `patient_ref`, `hospital_uhid`, and `pmjay_id` in the organizer's multilingual exports.
- CSV/TSV patient-table rows and text-document locators no longer depend on detecting an identifier. Table headers distinguish obvious patient exports from clean reference tables. JSON locators use patient-role structure, preserve escaped RFC 6901 pointers for record collections, index a patient-bearing single document as `doc`, and avoid indexing nonpatient metadata or ward lists. Ambiguous collections quarantine. This is heuristic record census, not complete semantic classification.

## Measured practice evidence

On the organizer's synthetic `dev/input`, with disposable local secret and output `/tmp/devforge-privacy-contract-final2`:

| Measure | Result |
| --- | ---: |
| Visible labeled identifiers, rough open self-check | 355 / 3,230 (11.0%) |
| Filename channel visibility | 0 / 48 |
| Medical probes preserved in exported files | 4,382 / 4,382 |
| Files sanitized / quarantined | 168 / 32 |
| Unique record locators | 755 / 755 |
| Canary exposures / raw unsupported copies / false merges | 0 / 0 / 0 |
| Linkage precision / recall / F0.5 | 0 / 0 / 0 |

`validate_output.py` reports `CONTRACT OK`. Submission tests pass 16/16, evaluation tests 37/37. Generated V2 JSON development and validation locators matched the corresponding generated truth 280/280; these labels are not independently adjudicated. The self-check is a rough practice measure, not an official score. Medical coverage across all input remains limited by 32 quarantined files (prior measured 4,382/4,855 probes, 90.3%).

On the generated Version 2 development set, the final pipeline sanitized 456/456 files. `evaluation/robustness_v2.py release` found all 1,000/1,000 records locatable, zero extra index entries, and 1,448/1,448 protected spans preserved. It still counted 1,558 literal labeled identifier residuals and zero linked pairs. These generated labels remain unreviewed and are not an official score.

Run from the repository root:

```sh
PYTHONPATH=submission python3 -m unittest discover -s submission/tests -p 'test_*.py'
python3 -m unittest discover -s evaluation -p 'test_*.py'
RAKSHA_SECRET=practice python3 submission/main.py --input dev/input --output /tmp/secret-wards-final-practice
python3 validate_output.py --input dev/input --output /tmp/secret-wards-final-practice
python3 check_dev.py --output /tmp/secret-wards-final-practice --show 0
python3 check_submission.py --repo . --run
```

## Remaining gates

1. **Privacy:** 355 labeled identifiers remain visible, especially Hinglish/Devanagari narrative patient and relative names. Add role-aware note rules with clinical homonym tests, then evaluate all-input clinical coverage and quasi-identifier uniqueness. The path detector cannot prove every arbitrary original basename is safe.
2. **Linkage and date policy:** all `records.jsonl` patient values remain null; there are no patient pseudonyms or date shifts. Implement conservative unique-anchor linkage with abstention, verify false merges and pseudonym occurrence in exported records, and use independent keyed date-shift derivation while preserving intervals. The toolkit's different-secret check passes on renamed filenames alone, so its message does not establish this requirement.
3. **Required brief:** the two-page Project Brief PDF is missing. It requires actual team members, repo link, measured privacy/utility trade-off, security design and limits. The mechanical checker warns rather than fails for this missing separate deliverable. Confirm the actual team name too; the root TOML currently follows the existing `submission/raksha.toml` value, `Secret Wards Phase A`.
4. **Further validation:** finish the independent V2 open labels, sealed private split and frozen comparison from `developer-b-v2-remaining-handoff.md`. Validate FHIR R4/ABDM profiles, adversarial attacks, held-out quasi-identifier risk and false-merge performance. Use the 900-second main contract limit until organizers resolve the conflicting large-profile limit.
