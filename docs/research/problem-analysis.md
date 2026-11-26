# Secret Wards problem analysis

## The problem in plain language

Four hospitals keep information about the same people in different systems. A research team needs to join those histories without learning who the patients are. A single name can appear in multiple scripts and spellings, while two different people can share the exact same name. Some identifying information can be obvious, like a government ID. Some is only revealing in combination, like age, a small village, and a rare diagnosis. Privacy and medical accuracy must hold together in the same release. [Original challenge brief](../PROBLEM_STATEMENT.md) · [Dataset and traps](../DATASET.md)

## Root causes and users

| Root cause confirmed by organizers | Effect on a stakeholder |
|---|---|
| Different hospital-local identifiers, re-registration, aliases, and cross-script names | Researchers need a coherent longitudinal history. Shared names and incomplete records make incorrect merges possible. |
| Medical and identifying text use overlapping names, abbreviations and numbers | Privacy reviewers want identifying data removed. Researchers need doses, vitals, conditions, and clinically meaningful time intervals preserved. |
| Free text, file and field names, and attachments are outside typical column-level masking | Data stewards need evidence that the entire release and its processing side channels were checked. |
| Patient histories contain unusual events and attribute combinations | Patients or relatives can be exposed through outside knowledge even after their direct identifiers are removed. |
| Historical export formats differ in encodings, layout, and validity | Operators need safe handling and accounting for broken inputs. Evaluators need a repeatable runner and an honest report. |

The challenge explicitly frames a public-health research database assembled by hospitals. Data stewards, clinicians who verify retained meaning, and patients represented by synthetic identities are inferred stakeholder roles. The immediate user of the submitted command is the organizer's evaluator. [Mission and deliverables](../PROBLEM_STATEMENT.md#1-mission-brief) · [Runner contract](../SPEC.md)

## Requirements and constraints

| Type | Requirement from the brief or contract |
|---|---|
| Ingest and export | Process heterogeneous CSV, TSV, JSON, FHIR R4, and text. Produce UTF-8 output preserving format, shape, and valid FHIR references. Account for every input. Quarantine files that cannot be safely processed. |
| Detect and protect | Identify direct identifiers of patients and relatives in English, Hindi and Hinglish, across content and structural channels. Keep clinically meaningful text including doctors, medicines, doses, diagnoses, vitals, and labs. |
| Resolve identity | Link records with sufficient evidence across files and hospitals. Use a keyed pseudonym within the release and write it into both the exported record and its index entry. Use `null` when evidence is insufficient. |
| Control disclosure | Treat quasi-identifiers under a justified release policy, preserve clinical intervals and truthful age bands, avoid side-channel leaks, and account for raw and intermediary data at rest in the security design. |
| Run reproducibly | Linux, CPU-only, 2 CPUs, 4,096 MB whole-process-tree RSS, 15-minute official ceiling, read-only input, zero runtime network. Prepare dependencies in setup, which allows internet and has 30 minutes. Same input and secret produce byte-identical releases within the specified scope. |
| Respect event rules | Synthetic data only. No generative or large language models and no pretrained transformers above 50M parameters. Declare models used. Hidden inputs contain new patients, and at least one introduces unseen formats. Core work is built during the event. |
| Submit and explain | A public event-created GitHub repository with a runnable root manifest, README, and a two-page PDF describing measured trade-offs, architecture, security, differentiation, and known limits. |

[Official problem statement](../PROBLEM_STATEMENT.md) · [Output and execution specification](../SPEC.md) · [Project Brief guidance](../PROJECT_BRIEF.md)

**Derived engineering requirements.** Separate clinical text from the normalized evidence used to find and match identifiers. Track original and released record locations when edits change structure. Budget memory per parser and per linkage stage. Check metrics by language, format, scenario, and channel, because aggregate scores can hide failures on rare cases. These are research conclusions to test against alternatives. [Scoring model](../SCORING.md) · [Observed starter gaps](codebase-overview.md#bottlenecks-and-technical-debt)

## Scoring and evidence

| Official category | Weight | Complementary signal for local comparison |
|---|---:|---|
| Privacy | 25% | Distinct canaries and direct identifiers leaking per channel. Measure the fraction of patients with rare combinations after grouping their records. Disclose the fields and denominator used. |
| Multilingual detection | 20% | Recall by language, channel, and type. Track protected clinical examples, including same-token role conflicts. |
| Clinical utility | 20% | Preserve probes divided by the number in the input, with missing records reported separately. Check interval and stay-length preservation, truthful age bands, and cohort statistics. |
| Identity resolution | 15% | Pairwise precision, recall and F0.5, B-cubed, counts of false merges and ambiguous abstentions, and recall among pairs that share cross-script evidence. |
| Integrity | 10% | Parse and validate outputs, resolve FHIR references, verify locators and actual pseudonym presence, reconcile manifest counts with physical inputs. |
| Reliability and speed | 10% | Read-only input, no runtime connections, per-format failures, process-tree peak RSS, wall time, repeated bytes with the same secret and changed identifiers with a different secret. |

Critical leaks, raw copies, false successes and input changes deduct points from the total. Official privacy credit depends on clinical utility. The local checks offer directional measurements and differ from the hidden evaluator. The rubric describes the automated weights and the contents of the human-facing brief. Any additional demo judging process is unconfirmed. [Scoring](../SCORING.md) · [Practice checker](../../check_dev.py#L84) · [Brief guidance](../PROJECT_BRIEF.md)

## Where existing approaches struggle

| Approach | Gap worth testing |
|---|---|
| Pattern matching or general PII services | Identifier forms may be unfamiliar. Names and abbreviations can change roles by context. Generic detectors do not establish format fidelity or longitudinal disclosure. |
| Name dictionaries or a transliterator by itself | Dictionaries miss unseen or synthetic names. Transliteration can collapse distinct spellings or fail to recognize nicknames. A name resemblance alone is weak identity evidence. |
| Linkage optimized for clean tables | A matching model needs field-level evidence. Raw notes, missing values, shared family data, and contradictory records can undermine it before scoring begins. |
| Direct-identifier removal and keyed pseudonyms | A patient can remain recognizable from released characteristics. Aggregating longitudinal records can increase the information available about one person. |
| Black-box suppression or aggregate-only release | Medical and research information can disappear, and the file-oriented contest contract requires a useful record-level release. |

The organizers' calibration reports 84.84 for their reference on standard normal data and 50.33 on standard unseen-format data. These are published organizer results. Only the practice baseline was reproduced here. [Calibration table](../SCORING.md#calibration) · [Existing solutions and privacy approaches](existing-solutions.md) · [Technology candidates](tools-and-technologies.md)

## Differentiation hypotheses

- **Learn field roles from labels, values and neighbors.** A novel name label might still be inferable from nearby age and registration fields. Measure gains on held-out label families and added damage to clinical tokens.
- **Separate the matching view from the release view.** Apply script folding and aliases to evidence while retaining precise spelling and spans for editing only confirmed sensitive content. Test transliteration collisions and line-offset stability.
- **Use conflict-aware patient grouping.** Preserve a high-precision evidence path and require compatibility before joining groups. Measure how weak fragment recall trades off against false merges under shared family contacts.
- **Measure rarity at both encounter and patient levels.** Explore whether broadening the riskiest allowable fields only where needed gives better utility than a uniform policy. Use explainable, predeclared safety and preservation measures.
- **Treat the unfamiliar input benchmark as a deliverable for ourselves.** Use fresh synthetic names, hidden headers/dates, format shifts, paired meaning examples, and format-level holdout. Compare several approaches on the same mutations before selecting a stack.

The first interview decision prioritizes hidden-set robustness, with one measurable strength to explain to judges. The feature to put in the brief remains open. [Open questions and decision frontier](open-questions.md) · [Comparative feasibility](feasibility-analysis.md)
