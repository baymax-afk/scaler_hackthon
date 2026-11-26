# Which privacy defense to test next

Test whether a patient name identified with strong role evidence can protect a second mention of the same full name within one Patient Record. In the earlier pre-patch open replay, 1,244 of 1,594 name occurrences and 163 of 343 relative-name occurrences remained fully or partly visible. Those counts establish the size of the name problem. The subsequent detector patch reduced residual names to 726 and residual MRNs to 610. The seed check below uses the patched baseline. Organizer practice independently found 218 patient-name and 55 relative-name literal residuals among 581 hits. The two audits use different units. [Open replay by identifier](detector-performance-report.md#open-robustness-results-by-identifier-type) · [Practice audit](submission-privacy-defense.md#evidence-from-the-packaged-cli)

## Evidence and scope

Clinical de-identification studies offer a precedent for a second pass. Neamatullah and colleagues rescanned notes for previously detected names and described errors from misspellings and broad context rules. Dehghan and colleagues built a patient-specific dictionary from high-confidence mentions to find additional mentions without explicit cues. Both used patient context. A single-record implementation needs less identity evidence and cannot recover a variant or isolated name that lacks a usable seed. Neither study estimates performance on this project's Hindi, Hinglish or unfamiliar layouts. [Neamatullah et al.](https://link.springer.com/article/10.1186/1472-6947-8-32) · [Dehghan et al.](https://pubmed.ncbi.nlm.nih.gov/26210359/)

A source role matters at both ends. A patient-name field can seed a repeat. The same string in a clinician field, an organization name or a diagnosis can carry a different meaning. Maintain original character boundaries and defer ambiguous matches. The repo's 16-case corroboration probe recovered five of eight unfamiliar-field targets, preserved all five controls and flagged three ambiguous cases. Those fixtures motivate a larger test with independently authored controls. [Role follow-up](generalization-role-followup.md#post-review-fixes) · [Organizer clinical scoring](../SCORING.md)

## Prioritized comparisons

| Priority | Intervention and scope | Paired test and decision evidence |
| --- | --- | --- |
| 1 | Exact, whole-name repeats within one record. This addresses direct exposure (A1) and removes one source of evidence pooled across records (A4). | On public development records, count residual occurrences with a trusted same-record seed. Compare the frozen baseline and candidate on the same files. Break out full, partial and unresolved occurrences, records with any leak, and clinical facts preserved across all inputs. Include earlier and later mentions, Unicode combining marks, adjacent doses, provider homonyms and identical strings in neighboring records. Reject a rule that damages a protected control. |
| 2 | Handle unseeded names and issuer-scoped medical record numbers separately. The patched open replay still contained 610 fully or partly visible medical record numbers. | Group by held-out layout and language. Include relative names, unknown field labels and synthetic order or accession numbers with the same shape. Compare exact typed spans and released occurrences with label support. Report protected-control outcomes on independently adjudicated negatives. |
| 3 | Coarsen age and locality where combinations are distinctive (A2–A5). For rare conditions, compare coarsening surrounding demographics before suppressing clinical facts. | On public synthetic profiles count small groups by age, sex and geography before and after release. Measure changes in retained age and geography resolution, rare-diagnosis coverage and record coverage. Small groups are a proxy. The organizer's illustrative reference still had 40.1% targeted success despite patient-level date shifts. |
| 4 | Introduce per-release keyed Patient Pseudonyms and patient-specific date shifts once linkage decisions are supported (A4–A7). | Exercise supported links, ambiguous matches, repeated releases and secret rotation. Count False Merges, Missed Links, Linkage Abstentions, preserved within-patient intervals and unchanged pseudonyms or dates across releases. Preserved intervals and rare diagnoses still carry identifying information. |

The priorities are engineering judgments based on the [local performance report](detector-performance-report.md), [organizer attack specification](../ATTACKS.md) and [scoring specification](../SCORING.md). A mapped name correction can coexist with residual identifiers elsewhere in the same record or its filename. Report release-wide side-channel checks alongside mapped outcomes. The organizer evaluates patient re-identification against an independent population registry and external facts. A local change in occurrence counts supplies no numerical estimate of that score. [Release scanner and its limits](generalization-role-followup.md#post-review-fixes) · [Organizer attack specification](../ATTACKS.md)

## Decision and paired release results

The first feasibility check changed the priority. Among 616 fully or partly visible patient-name occurrences on open development, zero matched an already detected, explicit patient-role full name in the same record's annotated source units. This checked case-folded exact matches using the existing name-shape guard and the pre-change source-only detector predictions. It excludes unannotated source channels, family-only matches and transliteration. A general patient dictionary would add homonym and cross-record risks for little demonstrated reach in that slice. The implemented alternative uses local language, structure and measurable clinical context.

In practice, names occurred in Hindi identity fields adjacent to age, romanized name columns and code-mixed clinical statements. The detector now handles additional explicit role cues, separates the new Hindi age boundary, and recognizes a line-initial title-case name followed by a possessive and a numerical blood-pressure reading. It guards against clinician titles and common measurement sites. Bare single names without supporting context remain ambiguous. Nested romanized name fields receive explicit patient, clinician or neutral context. An initial experiment broadening the age boundary exposed 12 additional MRNs. The shipped scope keeps the narrower boundary and independently recognizes labeled registration numbers. The paired test includes the age, registration number and adjacent dose.

| Public organizer practice metric | Before | Final candidate |
|---|---:|---:|
| Visible labeled identifiers in exported files | 581 / 2,940 | 529 / 2,940 |
| Visible patient-name labels across all inputs | 218 / 962 | 166 / 962 |
| Files with a visible labeled patient name | 115 / 168 | 101 / 168 |
| Files with both a visible labeled patient name and a geographic label | 40 / 168 | 29 / 168 |
| Visible labels by script or writing style, Latin / Devanagari / Hinglish | 387 / 114 / 80 | 366 / 95 / 68 |
| Exported files | 168 / 200 | 168 / 200 |
| Clinical probes preserved, all input | 4,382 / 4,855 | 4,382 / 4,855 |

The new practice file counts include each exported file once. Geography covers house, locality, village, landmark and PIN. A matching label anywhere in a file, including its designated path channel, can count. A multi-patient file can have a name and geography belonging to different people. These counts measure exposed material available to a recipient. Patient-level linkage success, false positives from clinical homonyms, and the official arena score need separate evidence.

The packaged CLI passed the organizer's three-run check. On the separate 1,400 open records, both versions fully transformed 2,892 of 4,391 labeled identifiers, left 1,494 visible and five partial, and preserved all 2,000 annotated clinical spans. The original 2,000-record audit reproduced byte for byte. Generalization to unseen records remains unresolved. The 600 sealed records stay with their custodian. The next comparison should use newly authored, independently annotated multilingual narratives with unseen names and non-person subjects, alongside demographic-combination exposure.

NIST recommends evaluating disclosure risk against a defined sharing model and measuring both disclosure and utility. An Indian clinical study also found material cross-institutional limitations when applying systems trained elsewhere. These findings support a release-level evaluation and external validation before interpreting a local practice improvement as transferable. [NIST SP 800-188](https://csrc.nist.gov/pubs/sp/800/188/final) · [Singh et al., BioNLP 2024](https://aclanthology.org/2024.bionlp-1.26/)

To reproduce, keep the two practice releases in separate directories. Run the following from the repository root for each. The file metrics are under `file_exposure`. No registry, annotated identity or evaluator-only flag enters the submission.

```sh
RAKSHA_SECRET=practice python3 submission/main.py --input dev/input --output "$release"
python3 validate_output.py --input dev/input --output "$release"
python3 evaluation/evaluate.py practice-audit "$release"
python3 check_dev.py --output "$release"
```
