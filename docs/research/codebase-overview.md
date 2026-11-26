# Secret Wards toolkit overview

## What it is

The organizers give teams a small example program, fake hospital exports, an answer key, and local checks. The starter opens each file, masks a handful of recognizable text patterns, writes it to an output folder, and lists what it processed. The hackathon work is making the released data private, clinically faithful, and linkable across records. This investigation used commit `6c0a85a`, which matches both tracked remote tips in this checkout. The configured GitHub tracker returned no issues. [Original brief](../PROBLEM_STATEMENT.md) · [Start here](../../START_HERE.md) · [Configured tracker](../agents/issue-tracker.md)

## Repository map and responsibilities

| Path | Responsibility and main entry points | Reuse or extension |
|---|---|---|
| [`starter/main.py`](../../starter/main.py#L211) | `main()` sorts and enumerates files, hashes bytes, decodes input, selects a handler by extension, handles selected failures, and writes the three outputs. `process_csv()`, `process_json()` and `process_text()` produce per-format output. | Reuse CLI and output interfaces. Evaluate replacing read/transform/write coupling once cross-file evidence and bounded memory matter. |
| [`starter/main.py` helpers](../../starter/main.py#L35) | `load_policy()` reads simple key-value lines. `clean_text()` masks five patterns. `clean_value()` recursively handles JSON strings and keys. `link_records()` always returns `None`. `pseudonym()`, `shift_date()` and `age_band()` provide standalone examples. | Treat decoding and deterministic HMAC as examples. Replace context-free detection, linkage stub, and example privacy policy with evaluated behavior. |
| [`starter/raksha.toml`](../../starter/raksha.toml), [`starter/config/policy.yaml`](../../starter/config/policy.yaml) | Entry-point template and three example policy settings. No dependencies are declared beyond the Python standard library. | Preserve the manifest shape. `min_group_size` is a TODO, and age/date values currently feed dormant helpers. |
| [`dev/`](../../dev) | Practice inputs, manifest, annotated truth, and synthetic evaluator reference data. | Keep truth separate from runtime. Use for baseline, regression, and controlled mutations. |
| [`validate_output.py`](../../validate_output.py#L28) | Checks manifest paths, input coverage by path/hash, UTF-8, and basic `records.jsonl` fields. It can warn and still return success. | Keep as a smoke check. Add independent format, locator, clinical, and privacy checks during the later build. |
| [`check_dev.py`](../../check_dev.py#L84) | Checks annotated text visibility, canaries, preserved values, link pairs and raw copies. | Keep as a fast regression signal. Use stratified holdouts and additional criteria for design decisions. |
| [`check_submission.py`](../../check_submission.py#L99) | Checks root manifest, README and ancillary files. With `--run`, executes three times, validates output, compares release digests, checks literal secret leakage, and rehashes input. | Run before submitting. `run_once()` inherits environment and uses offline flags for model hubs. The official isolation and resource enforcement are described separately. [Sandbox](../SANDBOX.md) |
| [`.github/workflows/kit-check.yml`](../../.github/workflows/kit-check.yml) | GitHub Actions on Ubuntu with Python 3.12. It runs the starter, checks the contract, compares same-secret results except `report.json`, runs a non-blocking static check, and prints practice metrics. | Reuse the smoke-test pattern. The tracked kit has no separate unit-test suite. |
| [`docs/`](..) and [`brief/`](../../brief) | Requirements, contract, scoring, dataset notes, sandbox, fairness, and the Project Brief template. | Use the organizer material as working authority, with conflicting clauses listed for clarification. |

The toolkit is Python standard-library code using `argparse`, `pathlib`, `csv`, `json`, `re`, `hashlib`, `hmac`, and `datetime`. The kit carries an MIT license. The official Linux runner accepts other languages and provides a one-time network-enabled setup stage. The starter reads `RAKSHA_SECRET` from the environment and has no runtime API, database, or model integration. [Starter imports](../../starter/main.py#L20) · [Requirements](../../starter/requirements.txt) · [License](../../LICENSE) · [Execution contract](../SPEC.md#2-execution-environment)

## Verified data flow

1. `main()` reads input files in sorted order, hashes each file and dispatches by extension. `decode()` handles a UTF-8 BOM, UTF-16 BOMs, UTF-8, and cp1252 fallback. [Decoding](../../starter/main.py#L146) · [File loop](../../starter/main.py#L223)
2. CSV/TSV handlers keep the header and mask cells. JSON handling chooses whole documents or lists of objects among top-level keys, escapes `~` and `/` in pointer segments, and recursively masks string keys and values. A FHIR Bundle runs through generic JSON handling. Text notes run through `clean_text()`. [Format handlers](../../starter/main.py#L159) · [JSON cleaning](../../starter/main.py#L123)
3. The starter writes UTF-8 files at unchanged relative paths, produces one hash-based report entry per input file, and emits `records.jsonl` with `null` patient assignments. Selected errors are recorded with controlled reasons. [File output and manifest](../../starter/main.py#L236)

## Baseline measured in this checkout

On Python 3.12.3, the 200-file practice tree occupied 626,836 bytes and covered four hospitals. The annotations contain 48 patients, 883 units including file-level units, and four planted canaries. Of 200 inputs, 192 have `expect: sanitize` and eight have `expect: either`. There are 19 FHIR Bundles, all with one Patient resource in this fixture. One pair of inputs has identical bytes. [Input tree](../../dev/input) · [Practice truth](../../dev/truth/truth.json) · [Dataset guide](../DATASET.md)

| Check | Observed result |
|---|---|
| Output and contract | 195 sanitized, five quarantined, 823 index entries, and `CONTRACT OK`. Quarantine breakdown was three unsupported formats, one empty file, and one malformed JSON. |
| Personal data | 2,718 of 3,230 annotated mentions still visible in the rough checker (84.1%). Latin 82.8%, Devanagari 100%, Hinglish 100%. |
| Canaries and links | Four of four canaries found. Zero linked records. Pairwise F0.5 was 0. |
| Preservation and raw copies | 4,855 of 4,855 checked probes found in exported files. Zero byte-identical broken-file copies flagged. |
| Repeat runs | Same-secret `sanitized/` files and `records.jsonl` matched byte for byte. A different secret produced the same files as well. |
| Pre-submit | The shipped manifest used `python`, missing locally. With a temporary launcher alias to the existing `python3`, the runtime checks passed aside from a warning for no secret-dependent change. The template team name still failed the pre-submit check. |

The self-check searches normalized substrings over entire exported files and counts clinical probes only where a corresponding output file exists. It computes pairs over records annotated `required`, and does not exercise the official privacy evaluator, FHIR validity, or actual official sandbox behavior. The 100% practice reading therefore covers those matched probes, with unknown clinical coverage outside them. Duplicate input hashes also collapse to one output path in its hash-to-path lookup. [Self-check implementation](../../check_dev.py#L94) · [Official scoring](../SCORING.md) · [Official evaluator availability](../FAIRNESS.md#7-what-to-share-with-teams-and-what-to-seal)

## Setup and execution

Run the shipped starter from the kit root with Python 3.12 as in CI. Use an empty destination outside `dev/input`. These commands need no dependency installation.

```bash
out=$(mktemp -d)
RAKSHA_SECRET=practice python3 starter/main.py --input dev/input --output "$out"
python3 validate_output.py --input dev/input --output "$out"
python3 check_dev.py --output "$out"
```

For a team submission the manifest belongs at the submission root. The organizer's guide describes a separate repository created during the event, use of the starter as a seed, and the public repository plus two-page PDF deliverable. The timer and memory fields in `report.json` can vary; the contract defines repeatability for `sanitized/` and `records.jsonl`. [Submission workflow](../../START_HERE.md#then-make-your-own-repository) · [Determinism](../SPEC.md#7-behaviour-that-is-scored) · [Brief instructions](../PROJECT_BRIEF.md)

## Bottlenecks and technical debt

- **Detection and role.** Generic replacements lack field context, multilingual names and relatives, typed IDs, structured numeric redaction, encoded attachment handling, and filename/header sanitation. Multiple JSON keys can become the same placeholder and a dictionary comprehension keeps only one value. [Detection and recursive cleaning](../../starter/main.py#L89)
- **Linkage and privacy.** Per-row or per-document immediate export leaves no dataset-wide linkage pass. No patient pseudonym is embedded and no date shifting, age banding, or suppression is applied. The HMAC helper consumes an empty key if the secret is missing, and it emits a 30-bit ID without a collision check. [Helpers](../../starter/main.py#L48) · [Linkage stub](../../starter/main.py#L134) · [CSV export](../../starter/main.py#L159)
- **Shape and references.** Fixed delimiter by extension and permissive CSV parsing can accept mislabeled files. Generic nested JSON handling does not establish which objects are patients or preserve FHIR reference consistency as a graph. CSV emits index entries for every data row, including patient-free rows. [Handlers](../../starter/main.py#L159) · [Dispatch](../../starter/main.py#L223)
- **Bounds and recovery.** Full-file reads, materialized CSV and JSON, retained records and reports, and a recursion limit raised to 5,000 make memory a plausible bottleneck. Input reads sit outside the per-file `try`; write and filesystem failures can leave a partial directory. The small fixture cannot establish scalability. [File processing](../../starter/main.py#L211)
- **Checker gaps.** The contract checker does not parse each output as its declared format, resolve FHIR references, verify pseudonym placement, or enforce one report entry per physical file for duplicate hashes. These checks matter even with a green smoke test. [Contract checker](../../validate_output.py#L34) · [Source contract](../SPEC.md#4-output-layout)
