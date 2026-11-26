# Generalization first slices

The implementation covers the approved source-input/scoring and release CLI seams. It leaves the historical benchmark reports intact. [Specification](../GENERALIZATION_SPEC.md) · [Counts-only replay](results/first-slices-open-replay.json)

## Developer A

The inline label recognizer now treats non-breaking and narrow non-breaking spaces as ordinary spaces in its comparison view. Each substitution is one code point, so findings still point to the original source. Labeled name and relative candidates stop at an adjacent numeric dose with a recognized unit. The renderer keeps the original label, dose, and same-surface clinician occurrence. Red–green component tests reproduced both defects, and a CLI test exercises them together.

A throwaway field-role probe combined a subject cue, a clinical sibling field and a person-like value. It found two of two unknown-label names and misclassified one of four protected controls, a condition that also looked person-like. This is too little evidence to activate the heuristic. Typed FHIR context remains useful where the input supplies it. Broad Unicode folding and wider schema role inference need independent paired fixtures.

## Developer B

The open corpus command `units` enumerates raw input files and their supported fields without truth or a manifest. The scorer joins independently derived coordinates to annotations after prediction. The release audit checks actual files and the report, and attributes original occurrences by anchored text alignment. Forward and reverse alignment must agree. Cases without a reliable mapping remain unresolved. Artifact reconciliation catches reused and unreported files and the rejection audit now detects an index entry for metadata-only output. Longest-locator linkage uses the eligible pair list when supplied. The strict span benchmark keeps unmatched predictions in partially adjudicated units out of its precision denominator.

The baseline and candidate still use category-only prediction snapshots. Role-sensitive verification is implemented at the release audit. This first audit checks mapped units and gives bounded alignment outcomes. Changed key paths, indistinguishable duplicates or long changed fields may require more context or private provenance. Full side-channel and alternate representation scanning remain separate. The existing open annotations are generated and still need independent adjudication before reporting headline precision or overall accuracy.

## Paired replay

The 1,400-record replays used the same generated inputs and corrected evaluator. Declared file and record coverage matched across all three arms. The original 2,000-record corpus was replayed with its historical audit because that truth does not support the same reviewed occurrence contract.

| Arm | Fully visible | Partly visible | Transformed in mapped units | Protected facts preserved |
| --- | ---: | ---: | ---: | ---: |
| V1 `095c854` | 2,015 | 91 | 2,285 | 2,000 / 2,000 |
| Pre-fix main `d8973ab` | 2,015 | 91 | 2,285 | 2,000 / 2,000 |
| Candidate | 2,006 | 95 | 2,290 | 2,000 / 2,000 |

There were 4,391 generated identifier labels per arm, with zero unresolved and zero unexported in these particular runs. The old literal report could not separate the 91 partial occurrences from complete transformations. The paired results support the two reproducible defect fixes. They show a small net change in open-corpus coverage of labeled identifiers. The broader generalization target remains open.

Organizer practice retained the pre-fix 168/200 exported files, 581 literal residual labels and 4,382/4,855 all-input clinical probes. The rejection replay still shows two gaps in the current runtime: its ambiguous-encoding fixture is exported and metadata receives a Patient Record index entry. Keep these separate from the detector fixes. No sealed inputs or annotations were used. Open vocabulary overlap is now reproducible as an aggregate command. Independent new layouts, adjudication and CRF training readiness remain outstanding.

## Reproduce

Generate the default open corpus into a fresh scratch directory. For each split, run the runtime from each pinned checkout with identical input and environment. Use the new evaluator from this feature branch for all arms. [Corpus generation](../datasets/robustness_v2/README.md)

```sh
python3 -B evaluation/robustness_v2.py vocabulary "$dataset"
python3 -B evaluation/robustness_v2.py units "$dataset/development" > "$scratch/units.json"
python3 -B evaluation/evaluate.py predict "$scratch/units.json" > "$scratch/predictions.json"
python3 -B evaluation/robustness_v2.py score "$dataset/development" "$scratch/units.json" "$scratch/predictions.json"
python3 -B evaluation/robustness_v2.py release "$dataset/development" "$scratch/release"
```
