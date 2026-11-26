# robustness_v2 open corpus

Use this guide to reproduce the 1,400-record open benchmark. For a small end-to-end check of the dataset, detector, and evaluator interface, see the [five-record integration slice](OPEN_SLICE.md).

This version materializes 1,000 development and 400 validation Patient Records for evaluating the Secret Wards toolkit. They are fictional. The original Secret Wards Blind corpus remains its own version. The planned 600 sealed records require independent authorship and custody by the teammate. This generator has no sealed split, private seed or private renderer.

| Split | CSV | TSV | JSON | FHIR | Plain text | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 200 | 150 | 200 | 200 | 250 | 1,000 |
| Validation | 80 | 60 | 80 | 80 | 100 | 400 |
| **Open total** | **280** | **210** | **280** | **280** | **350** | **1,400** |

## Generate and validate

Run from the repository root. Choose a new destination outside the runtime input tree. The generator refuses an existing destination.

```sh
dataset=/tmp/robustness-v2-team-run
python3 -B docs/datasets/robustness_v2/generate.py "$dataset"
python3 -B evaluation/robustness_v2.py validate "$dataset"
```

The default seed is `20261127`. Each split has an `input/` tree, an immutable-file manifest, occurrence truth and linkage ground truth. Give the runtime only `input/`. The JSON truth records include opaque IDs, original record locators, split and family metadata, and source units with original code-point offsets. Tabular coordinates use zero-based column indices. Text attachments use offsets in decoded UTF-8. Scalar labels use the string representation of the emitted value. Generated annotations record transformations and literal clinical preservation expectations. They need human adjudication before use for precision or false-positive estimates.

The validator checks allocations, file and truth hashes, exact duplicate files, locators and source span round-trips. It verifies split disjointness for patients, institutions and template families and checks the one declared positive pair per repeat encounter group. The challenge pairs share a generated name surface across distinct fictional patients. The rejection suite has nine files outside the valid split counts and an expected disposition for each.

For the published FHIR JSON Schema check, obtain the [FHIR R4 4.0.1 JSON Schema archive](https://hl7.org/fhir/R4/fhir.schema.json.zip) from [HL7 downloads](https://hl7.org/fhir/R4/downloads.html), extract `fhir.schema.json` and install `jsonschema` in your evaluation environment if necessary.

```sh
python3 -B evaluation/robustness_v2.py validate "$dataset" --fhir-schema /path/to/fhir.schema.json
```

This checks the pinned schema and fixture reference, narrative and attachment integrity. Terminology validation, the full HL7 constraint engine and ABDM profiles require additional tooling. The files assert no ABDM conformance.

## Generation, annotation and limitations

The 17 families cover distinct chart, claims, referral, lab, transfer, telemedicine, pathology, imaging, caregiving and clinical-note layouts. Development and validation use disjoint families and institutions. The generator assigns quotas before rendering and varies source layouts, names, direct identifier labels and writing patterns across English, Hindi, Hinglish, Kannada and Tamil. Language tags primarily describe names and selected text. Much of the clinical text is English. The corpus includes quoted multiline cells, a BOM-tagged UTF-16 TSV, escaped pointers, unrecognized field names, rooted FHIR references, XHTML and plain-text attachments. FHIR includes collection Bundles and document Bundles. All contacts use `.invalid` domains and chart identifiers use a synthetic namespace. No real patient material or live identity services were used.

The open corpus uses authored templates and deterministic clinical variants. Scenario quotas describe the intended challenge, and coverage differs by format. The corpus does not estimate prevalence or clinical performance. The QA run verified generated truth against source text. Independent clinical review, near-duplicate adjudication, exhaustive manual annotations and the broader national identifier and quasi-identifier scenarios remain open. The generation seed, split definitions and family definitions can be shared for open evaluation. The teammate should keep sealed families, inputs, seed and truth out of this checkout.

## Reproduce open baseline

The counts-only [baseline](v1-baseline.json) compares V1 submission source from `095c854`, plus the separately reviewed indexing commit `d25e72a`. On each arm use the same generated inputs and a separate empty output directory. Run the benchmark CLI from this feature branch.

```sh
run=$(mktemp -d)
export RAKSHA_SECRET=practice
split=development
python3 -B /path/to/v1/submission/main.py --input "$dataset/$split/input" --output "$run/release"
python3 -B evaluation/robustness_v2.py release "$dataset/$split" "$run/release"
python3 -B evaluation/robustness_v2.py units "$dataset/$split" > "$run/units.json"
python3 -B evaluation/evaluate.py predict "$run/units.json" > "$run/predictions.json"
python3 -B evaluation/robustness_v2.py score "$dataset/$split" "$run/units.json" "$run/predictions.json"
```

For detector experiments, the `predict` command runs the detector in its own checkout against the same unit file. The occurrence scorer measures exact hits, typed overlap among known labels, protected overlaps and incomplete units. The release scorer measures coverage, record locators, literal residuals at the original channels, preservation and eligible linkage pairs. Literal residuals miss alternate representations and partial identifiers. The benchmark is preliminary and compares only the open corpus. The [shared example](shared-example.json) shows a generated occurrence used in two roles and an incomplete prediction.

The indexing slice exported identical sanitized bytes but indexed only 362 of 1,400 records on these unfamiliar schemas. It improved the prior regression corpus and organizer practice results, so keep both comparisons as acceptance checks. Open development examples can guide the next change. If validation structures inform rule changes, treat them as development evidence. Developer B's sealed benchmark remains reserved.
