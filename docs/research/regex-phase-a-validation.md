# Phase A regex integration evidence

The runnable package is in [submission](../../submission/README.md). It reads supported CSV, TSV, JSON, FHIR and text inputs, detects sensitive spans with scoped rules and writes a reconciled output directory. The [evaluation driver](../../evaluation/evaluate.py) keeps trusted source units, predictions and optional occurrence truth separate. The [lineage splitter](../../evaluation/splits.py) keeps connected patient, file and template families together.

## Preliminary measurements

These are open development runs on Linux with Python 3.12. The two corpora informed rule and adapter development. Neither supplies an independent holdout. The two corpus truth schemas have different coverage and the visibility audits use normalized substrings over files. Treat the counts as regression indicators. The format checker does not verify clinical equivalence, FHIR profiles or official privacy scores.

| Dataset | Exported files | Visible labeled identifier mentions | Visible Canaries | Clinical probes preserved over all input | Wall time and max RSS |
| --- | ---: | ---: | ---: | ---: | --- |
| Organizer practice | 187/200 | 631/3,230 | 0/4 | 4,701/4,855 | 1.06 s and 22,060 KiB |
| Secret Wards Blind fixtures | 558/562 | 0/7,966 | 0/7 | 10,000/10,000 | 1.42 s and 23,680 KiB |

Both runs produced `CONTRACT OK`. The public practice checker found all 4,701 clinical probes in the exported files. The denominator in the table also includes 154 probes associated with quarantined files. Practice coverage was 185/192 required files. Five files were quarantined for ambiguous identifiers and eight for other input or format issues. The starter showed 2,718/3,230 visible mentions and 4/4 visible Canaries on practice. [Starter baseline](codebase-overview.md#baseline-measured-in-this-checkout)

An initial Blind fixture run quarantined 338 files. Most were triggered by ambiguous `C/O` phrases. Scoped care-of cues and English, Hindi and Hinglish complaints brought that down to four malformed, oversized-depth or unsupported fixture inputs. Add new templates and preserve a separate slice before measuring generalization. Unknown patient names, locale labels and privacy-sensitive context are still visible in the practice release.

The production detector scored 15 exact true positives, zero false positives and five misses on the 28 open prototype cases. Five units went to review, including three gold matches. No protected ranges overlapped automatic findings. This comparison used the prototype's occurrence truth and source-unit format, independent of the corpus visibility audit.

Nine focused assertions passed across the runtime and evaluation suites. Organizer preflight checked deterministic reruns, an unchanged input tree and secret hygiene. A rotated secret changed only keyed paths in the current package. Linkage uses explicit abstention. Generalization and patient date shifting remain outside the Phase A package.

## Replay

Run from the team checkout root.

```sh
export RAKSHA_SECRET=practice
practice_out=$(mktemp -d)
blind_out=$(mktemp -d)
blind=docs/datasets/secret_wards_blind
python3 submission/main.py --input dev/input --output "$practice_out"
python3 validate_output.py --input dev/input --output "$practice_out"
python3 check_dev.py --output "$practice_out"
python3 evaluation/evaluate.py practice-audit "$practice_out"
python3 evaluation/evaluate.py verify-corpus "$blind/input" "$blind/manifest.json"
python3 submission/main.py --input "$blind/input" --output "$blind_out"
python3 validate_output.py --input "$blind/input" --output "$blind_out"
python3 evaluation/evaluate.py blind-audit "$blind_out" "$blind/truth/fixtures.json" "$blind/manifest.json"
PYTHONPATH=submission python3 -m unittest discover -s submission/tests
python3 -m unittest discover -s evaluation
python3 check_submission.py --repo submission --run
```

For the independent split, supply a JSON array of opaque `id` values and `patient_group`, `file_family` and `template_family` lineage. `evaluation/splits.py` freezes a digest and seed, and refuses to partition a single connected group. For each designated evaluation input, keep truth with the evaluator. `evaluate.py predict` accepts a JSON array of opaque IDs, original text and optional field context and writes an input-digested snapshot. `evaluate.py score` joins the same input with occurrence truth and the frozen snapshot. Use exact typed half-open original code-point ranges, plus independently marked protected spans. Count review and input coverage alongside accuracy. The improved dataset still needs independently adjudicated occurrences and disjoint lineage groups.
