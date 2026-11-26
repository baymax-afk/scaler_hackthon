# Open Version 2 annotation example

This small, wholly synthetic Patient Record gives both workstreams a shared source-unit example. `inputs.json` is a runtime-safe input to the evaluator. `truth.json` and `predictions.incomplete.json` are evaluation-only artifacts; keep them out of pipeline input directories.

The original decoded text has 73 Unicode code points. Half-open offsets `[6, 16)` and `[21, 31)` both cover `Zevra Qiln`. The first is a patient Direct Identifier to remove; the second is a clinician name to preserve. The protected ranges also cover `BP 120/80` and `metformin 500 mg`. The record is safe to sanitize when scanning completes and only the patient range is replaced. The sample prediction deliberately reports `input_limit` after a partial finding. A release must quarantine that file rather than publish the partial edit.

The opaque `record_id`, `locator`, unit `id`, and SHA-256 of the exact `inputs.json` bytes join the three artifacts. The sample has no real patient, institution, or contact detail. It is open development material, not an independent validation or sealed test.

From the repository root:

```sh
python3 evaluation/evaluate.py score \
  docs/datasets/robustness_v2/open_example/inputs.json \
  docs/datasets/robustness_v2/open_example/truth.json \
  docs/datasets/robustness_v2/open_example/predictions.incomplete.json
```

The result has one exact true positive, zero protected overlaps, and one incomplete unit. Detection metrics describe the partial finding; `input_limit` still blocks publication.
