# Open questions for Secret Wards

## Agreed direction

The team chose to prioritize robustness on the unfamiliar hidden dataset and reported 24 hours shared across two people, with ChatGPT Plus subscriptions available. The feasibility estimates interpret this as 24 total person-hours and can be revised if 24 hours is the event duration. The recommended judging narrative is one measurable strength demonstrated on deliberately unfamiliar fixtures. The architecture, toolchain, feature to showcase, and release policy remain open. The bundled brief is the working authority and the configured GitHub tracker returned no issues when queried. The submission still has to run offline and without LLMs. [Problem statement](../PROBLEM_STATEMENT.md) · [Calibration](../SCORING.md#calibration)

## Interview frontier

| Order | Decision | Why it matters | Depends on |
|---|---|---|---|
| Active | **Parallel ownership and skills.** Confirm familiarity with Python data processing, Hindi/Hinglish, data linkage, and FHIR, plus available Linux hardware. | Someone must own end-to-end compatibility and metric interpretation even if implementation is split. | Two-person team and working time budget recorded |
| 3 | **Measurable differentiator.** Choose which capability should anchor the brief after comparing experiments on unfamiliar inputs. | Context inference, cross-script linkage, and disclosure-aware policy may show different gains per day. | Capacity, available data, and prototype evidence |
| 4 | **Safety and utility thresholds.** Agree on minimum preservation and false-merge tolerances, and how to evaluate uncertain records or newly seen formats. | Establishes when to abstain, quarantine, or retain information despite ambiguity. | Contract clarifications and holdout evidence |
| 5 | **Final experiment scope.** Decide how much of optional OCR, trainable detection, complex FHIR, or adaptive generalization is justified. | Keeps extension work proportional to measured benefit and the schedule. | Capacity, clarifications, and experiments |

## Organizer clarifications worth obtaining

| Priority | Open question | Working treatment in research |
|---|---|---|
| High | Does the existing clone qualify as the event-created submission repository? Confirm event work window, deadline, and any team-specific requirements. | The brief and starter guide describe an event-created repository. Keep project research here, and treat submission eligibility as unconfirmed for this checkout. [Original brief](../PROBLEM_STATEMENT.md#7-ground-rules) · [Starter workflow](../../START_HERE.md#then-make-your-own-repository) |
| High | How should a locator be reported when a JSON key itself contains PII? Can the parent locator stand in, and how do renamed keys affect `out`? How should a multi-patient Bundle be indexed? | Use fabricated examples to enumerate the conflict. The contract makes `loc` an input pointer and prohibits PII in `records.jsonl`. Practice Bundles contain one Patient each. [Record locator rules](../SPEC.md#6-recordsjsonl) · [Side channels](../SPEC.md#7-behaviour-that-is-scored) |
| High | What record fields may carry an embedded pseudonym without schema penalty? Are new CSV columns and JSON keys allowed for records without a suitable existing field? | The contract asks for unchanged schema and in-record pseudonyms, with examples that could imply additions. Check multiple placements before design. [Output format](../SPEC.md#4-output-layout) · [Pseudonym consistency](../SPEC.md#6-recordsjsonl) |
| Medium | Which ranking wording governs if it affects a tie? | The brief and fairness page give a per-dataset >1-point rule for three datasets. The scoring page gives paired significance with a 0.5-point minimum. [Problem statement](../PROBLEM_STATEMENT.md#6-evaluation--scoring) · [Fairness](../FAIRNESS.md#5-statistics-ties-are-honest) · [Scoring](../SCORING.md#multi-dataset-ranking) |
| Medium | Does the large scoring profile ever receive its listed 1,800 s for this track? | Plan around the documented 900 s hard cap. The standard target for full time credit is 60 s. [Execution limit](../SPEC.md#2-execution-environment) · [Published profiles](../../scoring.toml#L85) |
| Medium | What external non-patient resources, models trained during the event, or pretrained small assets are allowed? Is there any live demo rubric besides the brief? | Keep shortlisted options conditional on the rules and their licenses. [Ground rules](../PROBLEM_STATEMENT.md#7-ground-rules) · [Brief](../PROJECT_BRIEF.md) |

## Terminology under discussion

- **Patient record vs. scoring unit.** A patient record is about a patient. A file-level annotation such as `@header` is a scoring unit and may have no patient. [Dataset answer key](../DATASET.md#the-answer-key-truthjson)
- **Unknown vs. unlinked.** `patient: null` covers deliberate abstention. The evaluator distinguishes ambiguous evidence from a link the data supports. Keep those measures separate. [Linkability](../DATASET.md#when-must-two-records-be-linked)
- **Privacy vs. pseudonymization.** A patient pseudonym gives a research release continuity. Disclosure risk needs its own evaluation. [Scoring](../SCORING.md#3-privacy-attack-arena-25)
- **Quarantine vs. suppression.** Quarantine follows unsafe processing of an input. Suppression is a release-policy choice to withhold data. The file manifest uses both statuses. [Manifest](../SPEC.md#5-reportjson)

Organizer-defined terms are in the [glossary](../../GLOSSARY.md). Decisions about policy behavior remain in research notes until resolved. There are no architecture decisions that meet the ADR criteria yet.
