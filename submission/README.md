# Secret Wards · Prompt & Pray

Run the offline regex detector and deterministic release adapters with Python 3.12.

```sh
RAKSHA_SECRET=practice python3 main.py --input ../dev/input --output /tmp/secret-wards-phase-a
```

Use an absent or empty output directory outside the input tree. Run the organizer's format and practice checks separately. Neither runtime parsing nor rule selection reads evaluator truth.

The CLI walks inputs in stable order. CSV and TSV adapters attach original field labels and keep the delimiter. The JSON adapter rejects duplicate keys and preserves decimal precision. Supported FHIR Bundles keep structural identifiers and local references when safe. The adapter parses XHTML narratives and rewrites bounded base64 plain-text attachments. Text notes are scanned in original decoded coordinates. Upper layers apply deterministic typed replacements. Safe relative paths remain unchanged. Detected identifying filenames receive keyed replacements, while detected identifying directory components cause quarantine because the contract requires the folder tree to be retained. The report maps every input hash to its output or quarantine status.

Each input file gets a ledger entry. If the detector returns unresolved findings or a file would require an unsafe rewrite, the file is recorded as quarantined. Quarantine produces audit metadata and keeps the raw input in its original location. The pipeline stages only processed artifacts and publishes a completed output directory. It produces a hash-indexed `report.json`, a `records.jsonl` index, and `sanitized/`. Runtime output and controlled errors omit match text and secrets. For clearly identified CSV/TSV rows, typed JSON records, explicitly labeled text notes and single-patient FHIR Bundles, the release first collects keyed identity evidence and resolves only conservative matches across sanitized files. When a cluster is accepted, the same keyed pseudonym replaces an existing redacted identifier field or text span and appears in the record index. Unsupported, ambiguous or singleton records abstain.

The detector is a local rule set, including localized field aliases, measured-vital and patient-report cues, relationship context, source-aware nested JSON names, and safe header disambiguation. Known source labels carry more evidence than a number's appearance. Clinical units protect numeric observations. Ambiguous clinical-number or care-of matches can withhold an entire file, so the evaluation reports clinical coverage against all input. Important remaining gaps include unfamiliar unmarked names, broad encoded payload detection, full FHIR profile validation, broader cross-format and cross-script patient linkage, patient-consistent date shifting, rare-value suppression and an independent held-out quality evaluation. Key rotation changes renamed paths and patient pseudonyms.

From the team repository root, run the focused checks with `PYTHONPATH=submission python3 -m unittest discover -s submission/tests`. The team evaluation driver lives outside this package in `evaluation/`.

### Identity resolution and quasi-identifiers

The conservative linker accepts typed MRN/UHID, Aadhaar, ABHA, mobile and email evidence. A full name plus strong or corroborated identity evidence is required; a pair of agreeing global IDs may also suffice. Names, identifiers and supporting evidence are independently keyed with HMAC-SHA256. Conflicts, overly common anchors and non-clique match components abstain. Pseudonyms are deterministic for a fixed evidence batch and release secret; they rotate when that secret changes. This deliberately favors precision over recall. For FHIR, linkage accepts only a unique typed medical-record identifier with an explicit MRN/UHID system and abstains when identifier-valued references are present. Raw evidence is processed in memory and is never serialized into an output mapping.

Recognizable patient tables generalize whole-year ages into inclusive five-year bands, six-digit PINs into a three-digit prefix plus `***`, and locality/village into a plausible explicitly supplied same-row district. Transformations do not guess districts, touch clinical value columns or alter row shape. Recognized patient-context JSON string values receive the same safe generalizations while numeric and clinical types are retained. FHIR Patient.birthDate is reduced to a valid year; known patient reference displays, relative-name extensions and exact patient names in supported text attachments are redacted. The report counts each generalized exported record once. Location generalization trusts source field roles, not independently verified geographic truth. Unstructured prose generalization, broader numeric JSON generalization and patient-consistent date shifting remain outside this release policy.

### Operating the judged CLI

Run from the directory containing `raksha.toml`. The launcher supplies absolute input and output paths and a per-release secret in the environment. On a local practice run supply a disposable secret in the environment before invoking the same command. Keep real release keys out of command arguments, shell history and repository configuration. The organizer runs with a read-only input tree. Give the process a private writable output parent for sibling staging and the completed release. Use encrypted storage and access controls for the input and output volumes. The CLI itself writes ordinary files and provides no disk encryption.

The privacy checks apply to content and several secondary channels. For example, a masked mobile number in a recognized shape still discloses digits that can be matched with outside contact data. The detector rewrites that shape in prose and uses a keyed replacement for affected filenames. An external FHIR attachment link can grant access to the original document. The adapter quarantines a Bundle with a recognized URL-bearing attachment, including one that also supplies inline data. An unrelated valid input can still be published. Inspect aggregate quarantine counts alongside release coverage when interpreting these controls.

A successful exit indicates that the batch was published. Inspect the file dispositions in `report.json` before interpreting coverage. The organizer's output validator checks the format, and the practice self-check estimates residual exposure against synthetic labels. Neither tool measures the full re-identification risk of a Research Release.

### Candidate verification (organizer practice, 27 November 2026)

Run from the development repository root:

```sh
PYTHONPATH=submission python3 -m unittest discover -s submission/tests
work=$(mktemp -d)
python3 prepare_submission.py "$work/team"
python3 check_submission.py --repo "$work/team" --run
RAKSHA_SECRET=practice python3 "$work/team/main.py" --input dev/input --output "$work/out"
python3 validate_output.py --input dev/input --output "$work/out"
python3 check_dev.py --output "$work/out"
```

| Metric | Original main (0f61f55) | Candidate |
| --- | ---: | ---: |
| Visible labeled identifiers (whole practice input denominator) | 333/3,230 | 0/3,230 |
| Files sanitized / quarantined | 168 / 32 | 187 / 13 |
| Clinical probes preserved in exported files | 4,382/4,382 | 4,701/4,701 |
| Clinical probes preserved across all input | 4,382/4,855 | 4,701/4,855 |
| Linked records | 0 | 99 (28 pseudonyms) |
| Generalized records | 0 | 452 |
| Pairwise linkage precision / recall / F0.5 | 0 / 0 / 0 | 1.00 / 0.04 / 0.17 |
| Observed wrong patient merges | 0 | 0 |
| Planted canaries found / raw-copy violations | 0 / 0 | 0 / 0 |

The generated V2 development corpus (456 files) exported all 1,000 locatable and indexed records, preserved 1,448/1,448 protected spans, and had zero literal aligned identifier residuals out of 3,157 labels. A separate release-wide surface scan still found 69 matching known unique surfaces; these matches are not necessarily original-occurrence leaks. After freezing the runtime, the separate open V2 validation split (183 files) exported all 400 locatable records, indexed 340, preserved 552/552 protected spans, and had 250/1,234 literal aligned residuals. It had 155 matching known unique surfaces in the broader scan. Neither V2 split linked any eligible pairs. The rejection audit matched 8/9 expected fixture dispositions; invalid UTF-8 interpreted as cp1252 remains a discrepancy. Practice and V2 development informed rule selection; the open validation split is not a sealed organizer evaluation. No trained ML model is used. All 87 runtime, 51 evaluator and 21 dataset tests pass.

The development repository is not itself a public judged submission. The packager includes the runtime modules and `project-brief.pdf`; it excludes the practice data, evaluator truth, tests, caches and release outputs. Inspect the exact output of the packager before publishing a separate judged repository.
