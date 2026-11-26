# Secret Wards Phase A

Run the offline regex detector and deterministic release adapters with Python 3.12.

```sh
RAKSHA_SECRET=practice python3 main.py --input ../dev/input --output /tmp/secret-wards-phase-a
```

Use an absent or empty output directory outside the input tree. Run the organizer's format and practice checks separately. Neither runtime parsing nor rule selection reads evaluator truth.

The CLI walks inputs in stable order. CSV and TSV adapters attach original field labels and keep the delimiter. The JSON adapter rejects duplicate keys and preserves decimal precision. Supported FHIR Bundles keep structural identifiers and local references when safe. The adapter parses XHTML narratives and rewrites bounded base64 plain-text attachments. Text notes are scanned in original decoded coordinates. Upper layers apply deterministic typed replacements. Safe relative paths remain unchanged. Detected identifying filenames receive keyed replacements, while detected identifying directory components cause quarantine because the contract requires the folder tree to be retained. The report maps every input hash to its output or quarantine status.

Each input file gets a ledger entry. If the detector returns unresolved findings or a file would require an unsafe rewrite, the file is recorded as quarantined. Quarantine produces audit metadata and keeps the raw input in its original location. The pipeline stages only processed artifacts and publishes a completed output directory. It produces a hash-indexed `report.json`, a `records.jsonl` index, and `sanitized/`. Runtime output and controlled errors omit match text and secrets. Every run explicitly abstains from cross-file patient linkage.

The detector is a local rule set. Known source labels carry more evidence than a number's appearance. Clinical units protect numeric observations. Ambiguous clinical-number or care-of matches can withhold an entire file, so the evaluation reports clinical coverage against all input. Important remaining gaps include unfamiliar unmarked names, broad encoded payload detection, full FHIR profile validation, patient linkage, release-level quasi-identifier policy and an independent held-out quality evaluation. Key rotation changes renamed paths. The current release does not use the secret to derive patient IDs or date shifts.

From the team repository root, run the focused checks with `PYTHONPATH=submission python3 -m unittest discover -s submission/tests`. The team evaluation driver lives outside this package in `evaluation/`.
