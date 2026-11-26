# Secret Wards detector performance report

## Patch result

The patch at `a18c0c5` fully transformed **2,892 of 4,391 labeled identifiers (65.86%)**, up from **52.15%** at `21fb8bd`. That is **602 additional occurrences** and **13.71 percentage points** on the same 1,400 open records. Records with a fully or partly visible identifier fell from **1,160 to 906**. Both arms exported 1,400 records and preserved all 2,000 annotated clinical facts.

| Format | Fully transformed before | Fully transformed after | Labeled |
| --- | ---: | ---: | ---: |
| CSV | 280 | 460 | 840 |
| TSV | 210 | 210 | 630 |
| JSON | 360 | 440 | 840 |
| Plain text | 420 | 696 | 995 |
| FHIR | 1,020 | 1,086 | 1,086 |
| **Total** | **2,290** | **2,892** | **4,391** |

The earlier perfect regression result and lower robustness result came from different corpora. In the same-input baseline replay, the source-only predictor produced no selected span overlapping any of the 2,006 fully visible occurrences. Another 95 occurrences were partly visible, including 90 names. A minimized note reproduced the cause for reordered names. The label parser stopped at the comma and left the initials. Structured misses came from unfamiliar fields and paths. The chart detector also required one of a fixed set of prefixes even when the note supplied an explicit chart-number cue. FHIR narrative names could survive after their structured equivalents were removed because the original rewrite processed each XHTML text fragment in isolation.

The patch retains reordered initials within known name spans, expands explicit multilingual and relationship cues, and requires patient or chart evidence for new structured detections. The FHIR adapter corroborates isolated narrative names against the same resource's structured name. Independent test values verify that clinician homonyms, diagnosis text, specimen codes and nearby doses survive. The isolated corroboration applies to name-only blocks. Mixed prose and unsupported attachment content remain separate problems. [Detector](../../submission/rakshak/detection.py) · [Structured context](../../submission/rakshak/source_context.py) · [FHIR adapter](../../submission/rakshak/formats.py)

The suite passed 92 tests. The original 2,000-record historical audit reproduced byte for byte. Organizer practice logged 581 visible labeled mentions, 168/200 exported files, and 4,382/4,855 preserved clinical probes in both arms. The output validator passed the open, original and practice replays. Of the 1,499 remaining visible or partly visible open occurrences, 726 are names, 610 are MRNs and 163 are relative names. TSV remains the weakest format. The open data informed this investigation, so the patch effect is a paired development result. The sealed set remains in independent custody.

## Pre-patch analysis

Before this patch, the deterministic detector fully transformed **2,290 of 4,391 labeled Direct Identifier occurrences (52.15%)** on the 1,400-record open robustness corpus. At least one labeled identifier remained fully or partly visible in **1,160 of 1,400 Patient Records (82.86%)**. The release contained all 1,400 records and preserved all 2,000 annotated clinical facts. Names and medical record numbers accounted for **92.24%** of the occurrences still visible.

The baseline is `21fb8bd` on `feature/generalization-first-slices`, with runtime changes through `e5d8a11` and evaluator changes through `811d36b`. This configuration uses deterministic rules and format adapters. The sealed 600-record set and any learned model are outside the measured scope. [Paired replay, digests and fixture details](generalization-role-followup.md#post-review-fixes)

## Pre-patch benchmark results

| Evaluation set | Coverage | Identifier outcome | Clinical preservation |
| --- | ---: | --- | ---: |
| Original synthetic regression corpus | 2,000 / 2,000 records | Zero visible among 7,917 source-present labels under the historical audit | 10,000 / 10,000 exact probes |
| Robustness development | 1,000 / 1,000 records | 1,531 / 3,157 fully transformed · 48.50% | 1,448 / 1,448 facts |
| Robustness validation | 400 / 400 records | 759 / 1,234 fully transformed · 61.51% | 552 / 552 facts |
| Organizer practice | 168 / 200 files · 166 / 192 required files | 581 / 2,940 labels in exported files still visible under the practice audit | 4,382 / 4,855 input probes · 90.26% |

The original corpus informed rule development. The current original-corpus replay reproduced the historical counts-only output byte for byte. The robustness audit aligns annotated occurrences at their mapped output locations and distinguishes full visibility, partial visibility and complete transformation. The original and practice audits use literal visibility under their own rules. Combining these denominators would obscure the result. The toolkit output validator passed on all three corpora. [Original counts](results/v1-blind-record-audit.json) · [Open replay](generalization-role-followup.md#post-review-fixes) · [Practice and original audit methods](generalization-analysis.md#frozen-reference)

### Open robustness results by format

| Format | Fully transformed / labeled | Fully visible | Partly visible | Records with any visible label |
| --- | ---: | ---: | ---: | ---: |
| CSV | 280 / 840 · 33.33% | 559 | 1 | 280 / 280 |
| TSV | 210 / 630 · 33.33% | 418 | 2 | 210 / 210 |
| JSON | 360 / 840 · 42.86% | 478 | 2 | 280 / 280 |
| Plain text | 420 / 995 · 42.21% | 485 | 90 | 324 / 350 |
| FHIR | 1,020 / 1,086 · 93.92% | 66 | 0 | 66 / 280 |
| **Total** | **2,290 / 4,391 · 52.15%** | **2,006** | **95** | **1,160 / 1,400** |

Only 240 records had every annotated Direct Identifier fully transformed at its mapped location. The open run had zero unresolved or unexported identifier occurrences. Of the 95 partly visible occurrences, 90 were in plain text. FHIR supplied more usable structural context in these fixtures. Separate probes still found residual names in split XHTML, name components and a supported attachment. The toolkit validator covers output structure checks. Full FHIR profile conformance and privacy outcomes require separate checks. [Occurrence audit](../../evaluation/robustness_v2.py) · [FHIR adapter](../../submission/rakshak/formats.py)

### Open robustness results by identifier type

| Identifier | Labeled | Exact typed span detected | Fully transformed in output | Fully or partly visible |
| --- | ---: | ---: | ---: | ---: |
| Name | 1,594 | 306 · 19.20% | 350 · 21.96% | 1,244 |
| Medical record number | 974 | 280 · 28.75% | 280 · 28.75% | 694 |
| Relative name | 343 | 180 · 52.48% | 180 · 52.48% | 163 |
| Email | 1,480 | 1,400 · 94.59% | 1,480 · 100% | 0 |
| **Total** | **4,391** | **2,166 · 49.33%** | **2,290 · 52.15%** | **2,101** |

One-to-one typed overlap matched 2,172 of 4,391 positive labels (49.46%). Exact detection scores require the correct original span and category. A serialized edit can fully cover a label without an exact typed detector span. The two metrics therefore answer different questions. The generated corpus has incomplete negative annotations and zero explicit role targets. Overall precision, false-positive rate, accuracy and role recall are undefined here. The 2,000 preserved facts describe checked clinical spans and leave effects on other clinical content unmeasured. [Span scoring contract](../GENERALIZATION_SPEC.md#evaluator-and-pinned-replay)

## Generalization and privacy gaps

- **Unfamiliar layouts.** All 220 validation names in CSV, TSV and JSON remained visible, including 18 exact name surfaces absent from development. The validation split reused 412 of 454 exact name surfaces overall. That overlap and the different mix of layouts limit conclusions about unseen names. A separate 16-case probe found that same-record corroboration recovered 5 of 8 unfamiliar-field patient names, spared 5 of 5 protected controls and flagged 3 of 3 ambiguous cases. Its three misses remain relevant to a broader evaluation. [Vocabulary evidence](generalization-and-regularization.md#measurements-on-current-main) · [Field-role probe](generalization-role-followup.md#post-review-fixes)
- **Organizer practice differs by script and release coverage.** Literal visibility hits were 114/143 Devanagari, 80/111 Hinglish and 387/2,976 Latin across all input labels in each script. These denominators include labels on unexported files, and script, format and identifier mix can vary together. The 19 FHIR date-guard quarantines accounted for 19 of 32 files withheld. The exported-label visibility rate was 581/2,940 (19.76%). [Practice audit](../../evaluation/evaluate.py) · [Date guard](../../submission/rakshak/formats.py)
- **Linkage and temporal privacy.** The open benchmark linked 0 of 78 eligible pairs, and the original regression audit linked 0 of 1,502 same-patient pairs. The runtime writes null patient assignments, so pair precision is undefined. All 954 open event-date annotations remained visible. The original audit also reproduced 3,950 unchanged observed date fields and 1,950 unchanged ages. Date and age policy needs a separate evaluation against privacy risk and clinical relationships. [Record index writer](../../submission/rakshak/release.py) · [Requirements audit](generalization-analysis.md#requirements-traceability)
- **Release integrity.** The current rejection replay met 7 of 9 fixture expectations. The detector exported the fixture designated invalid UTF-8 through the cp1252 fallback and indexed a metadata-only file as a Patient Record. The independent release scan found 807 unique known surfaces in development artifacts and 186 in validation artifacts. These diagnostic counts can include legitimate occurrences with the same text. [Rejection fixtures](../datasets/robustness_v2/generate.py) · [Release scan](../../evaluation/release_scan.py)

## Change over the prior baseline

On the same 1,400 records and mapped occurrence scorer, the historical V1 runtime and pre-fix main each fully transformed 2,285 of 4,391 labels. The current branch transformed five more, a gain of **0.11 percentage points**, all in plain text. Compared with the immediate prior branch at `a243a45`, the aggregate identifier, coverage and clinical counts were identical. Targeted tests verified improvements to whitespace handling, adjacent dose boundaries and structured role interpretation. The replay shows their benefit on those defects and leaves broader unfamiliar-field generalization open. [Historical paired replay](generalization-first-slices.md#paired-replay) · [Latest paired replay](generalization-role-followup.md#post-review-fixes)

## Runtime and repeatability

The current CLI processed the combined 1,400 open records across 639 files five times on Linux x86-64 with Python 3.12.3 and affinity restricted to two logical CPUs. Median end-to-end runtime was **1.50 seconds**, with a range of **1.46–1.65 seconds**, or about **933 records per second** at the median. Maximum measured peak RSS was **21.84 MiB**. The five runs produced byte-identical sanitized files and Patient Record indexes with the same synthetic secret. Semantic report fields also matched across runs. The timings include input enumeration, detection, transformation and release writing. Larger inputs and the organizer sandbox require separate measurements. [Execution contract](../SPEC.md#2-execution-environment)

## Implications for the next comparison

Prioritize name and MRN recognition under independently authored layouts. Those two categories leave the most observed exposure. Compare patient and clinician homonyms, issuer-scoped MRNs, names under unseen labels, and adjacent clinical values before widening rules. Use the same grouped fixtures to test exact typed spans, released occurrences, protected facts and coverage. A learned comparator can test whether context features recover ambiguous names after independent annotation. Linkage, temporal policy and release validation require their own measurable improvements. [Generalization specification](../GENERALIZATION_SPEC.md) · [Dataset and experiment plan](generalization-solution-plan.md)

## Reproduce

Generate only the open splits with seed `20261127`. Run the versioned CLI with the same synthetic secret, verify outputs with `validate_output.py`, and score with the same evaluator. For the record-level table, group the mapped occurrence outcomes by input record and count a record once when at least one labeled Direct Identifier is fully or partly visible. Retain identifier type and format for the cross-tabs. The historic original and practice audits remain separate. [Open generation and scoring commands](../datasets/robustness_v2/README.md) · [Original replay command](generalization-analysis.md#replay) · [Pinned run manifests and predictions](generalization-role-followup.md#post-review-fixes)
