# Secret Wards v3 fixture report

Each archive expands to `input/`, `truth/fixtures.json` and `manifest.json`. Pass only `input/` to the pipeline. Use the development split to build and tune the pipeline. Keep the holdout archive and its authoring source out of training, rule writing and threshold tuning. Evaluate on the frozen holdout after locking the pipeline. The manifests cover every input file and the gold file by SHA-256.

## Design and sources

The comparison used the local Track 3 brief, the public toolkit contract and the public practice fixtures. The practice discharge summaries track admissions, hospital courses and discharge plans. Prescriptions give medication directions, and nursing entries record timed observations, administration and handover. Registration exports primarily carry identity, while lab JSON and chat forwards carry specimen or test results with varying identity evidence. The new fixtures use these workflow distinctions with newly authored texts. [Track 3 problem statement](../../PROBLEM_STATEMENT.md) · [Organizer practice set](https://github.com/Reinforce-SST/Secret-Wards-ToolKit/tree/main/dev) · [Organizer input and output contract](https://raw.githubusercontent.com/Reinforce-SST/Secret-Wards-ToolKit/main/docs/SPEC.md)

The blind baseline has 562 input files, with 562 matching its archived manifest. Across its 500 notes, all 167 discharge notes begin with a Latin patient label, all 166 prescriptions use the Romanized inline-name family, and all 167 nursing notes begin with a Devanagari patient label. The category folder therefore reveals both the style and the identity placement. Of the 500 basenames, 497 follow the sequential naming scheme and three use a distinct scheme. All 1,983 populated phones and all 1,983 populated emails in the baseline truth carry the patient-index suffix. The new splits use neutral filenames, cross headings with layouts, and shuffle structured records. Household contact numbers can be shared by separate patients.

The development author generated patient and household records first, then admissions, prescriptions and observations. Registration, medication, bedside, discharge, lab and forwarded messages draw from the resulting histories. Some later follow-ups refer to the earlier discharge. The holdout author received the organizer sample, requirements and the shared truth schema in a separate context. The author built distinct facilities, names, templates, labels and serialization rules without access to the development renderer or its fixtures. Neither generator runs inside the pipeline.

## Evaluator truth

- Text labels resolve by zero-based, half-open Unicode code-point spans on the decoded UTF-8 text. CSV and TSV labels use zero-based rows after the header and exact column names. JSON labels use RFC 6901 pointers.
- `REMOVE`, `PRESERVE`, `SHIFT` and `GENERALIZE` apply to individual occurrences. A surface can receive different actions in a single note. Event-linked labels identify the canonical fact to compare across records.
- Linkage truth contains annotated pairs with visible supporting evidence or an explanation of ambiguity. `NON_LINK` means distinct patients. `ABSTAIN` means the surface evidence cannot justify linking the fragment to the candidate. These are selected pairs, alongside full record-to-patient assignments for identified records.

## Verified coverage

| Measure | Development | Independent holdout |
| --- | ---: | ---: |
| Input files | 227 | 264 |
| Fictional patients | 54 | 54 |
| Encounters | 61 | 60 |
| Records | 335 | 358 |
| Gold occurrence and field labels | 2,770 | 3,016 |
| Clean note controls | 27 | 81 |
| Notes with the same patient and clinician name | 9 | 3 |
| Notes with the same digits as a record identifier and a drug dose | 9 | 4 |
| Notes with both identifying and clinical uses of C/O | 9 | 7 |
| True links, including cross-script links | 308 (61 cross-script) | 222 (164 cross-script) |
| False-merge trap pairs | 3 | 2 |
| Ambiguous records and their abstain pair decisions | 3 records, 6 pairs | 1 record, 2 pairs |
| Labels checked against canonical encounter facts | 1,186 | 1,275 |
| Encounter facts verified in multiple documents | 358 | 378 |
| Date order, stay length or follow-up chronology checks | 68 | 60 |
| Unresolved or overlapping gold locators | 0 | 0 |

### Note type and writing style

Each cell shows the development and holdout note counts, including clean controls. Each cell contains three layouts and three heading states (two named headings and a headingless variant), with all nine heading and layout pairings present in both splits. There are seven headingless notes per development cell and nine per holdout cell. The holdout contains two patient-bearing notes and one clean control in each pairing.

| Note type | Latin | Devanagari | Code-switched |
| --- | ---: | ---: | ---: |
| Discharge | 21 / 27 | 21 / 27 | 21 / 27 |
| Prescription | 21 / 27 | 21 / 27 | 21 / 27 |
| Nursing | 21 / 27 | 21 / 27 | 21 / 27 |

### Shortcut checks

| Feature used alone | Development balanced accuracy for REMOVE presence | Holdout balanced accuracy for REMOVE presence |
| --- | ---: | ---: |
| Filename pattern and parent folder | 50.00% | 50.00% |
| Heading | 50.00% | 48.77% |
| Layout | 50.00% | 50.00% |
| Script | 50.00% | 50.00% |

The checks fit a majority rule for each feature on four folds and predict on the fifth, rotating held-out folds. The target is whether the note contains any `REMOVE` label. When the target is any of the three contextual contrasts, the same single-feature rules achieve 49.07%–50.00% balanced accuracy in development and 48.91%–50.00% on holdout. The row-order rule linked registration and lab records at the same physical position, regardless of their contents. It found 0 of 61 true candidate pairs in development and 4 of 60 in holdout, with 0/54 and 4/300 precision respectively. These checks cover simple rules on these fixtures. Combined features and learning-based attacks were outside the measured scope.

### Reproducibility and limits

- The initial pilot and both rerenders matched byte-for-byte across all 126 development and 177 holdout files, including truth and manifests. The scaled rerenders also matched all 229 development and 266 holdout files.
- Across the frozen splits, there were zero shared patient IDs, zero shared normalized patient-name surfaces and zero duplicate note hashes. The verifier also rejected test mutations to input bytes, a Unicode offset and a canonical haemoglobin value.
- Development contains truncated JSON, an empty file and an invalid UTF-8 text file. Holdout contains malformed JSON, malformed CSV and an invalid byte sequence. The official starter's output passed the format validator for both splits. The starter classified the invalid UTF-8 development text and the malformed holdout CSV as sanitized, so these remain targeted quarantine tests.
- The fixture corpus targets a finite set of workflows and clinical probes. Coverage excludes FHIR, legacy valid encodings, filename PII and the organizer's attacker registry. The toolkit's scoring was outside this run.

| Frozen archive | SHA-256 |
| --- | --- |
| `secret_wards_v3_dev.zip` | `cb8450af7363f997903763e32953c3046925f2bbfdb1262d2be4be850b240ef0` |
| `secret_wards_v3_holdout.zip` | `ed1308d4db2d407a0276869857555992f680a0496dabec95ca62df408e11f814` |

See the [machine-readable verification results](secret_wards_v3_verification.json) for every matrix cell, label action and shortcut check.

## Reproducing the checks

```powershell
python docs/datasets/secret_wards_v3/build_secret_wards_dev.py testing/v3_dev_repeat
python docs/datasets/secret_wards_v3/build_secret_wards_holdout.py testing/v3_holdout_repeat
python docs/datasets/secret_wards_v3/verify_secret_wards_v3.py testing/v3_dev_repeat testing/v3_holdout_repeat --json
```

Each build command expects a fresh output directory. Add `--pilot` for a small reproducibility run. Compare the repeat manifest against the matching frozen archive.
