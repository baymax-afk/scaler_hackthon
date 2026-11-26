# Developer B handoff for remaining Version 2 work

The open dataset and evaluator are ready to build on. The shared generator produced 1,000 development and 400 validation Patient Records across 17 families. The original 2,000-record Secret Wards Blind corpus stays separate. The remaining deliverables are independent annotation review, a privately authored 600-record sealed split, and a frozen comparison. [Dataset card](datasets/robustness_v2/README.md) · [Verified open corpus](datasets/robustness_v2/verification.json)

## Start from the integrated commit

Fetch the team repository and branch from the main revision containing this handoff once it is published. In a checkout that already has that revision, run:

```sh
git worktree add -b feature/robustness-v2-review ../t3_scaler-v2-review main
cd ../t3_scaler-v2-review
git status --short --branch
```

Use an existing worktree if the branch already exists. Record your base SHA in review notes. Keep shared evaluator and annotation-policy changes in this branch. Keep sealed authoring and artifacts in teammate-controlled storage outside the team repository and detector workspace.

## Remaining work

| Order | Work | Acceptance evidence to share |
| --- | --- | --- |
| 1. Reproduce the open corpus | Regenerate with the default seed and compare both manifest hashes with the checked-in verification. Replay source spans, positive and different-patient challenge pairs, expected rejection dispositions, and the published FHIR schema check. Use [the example fixture](datasets/robustness_v2/shared-example.json) to agree the original-span and incomplete-result contract with A. | Aggregate counts, run command, SHA and differences from the baseline. |
| 2. Adjudicate labels and coverage | Review 100 development and 60 validation records sampled across formats, families, scripts and channels. Check label completeness, original coordinates, exact clinical facts, clinical plausibility, same-surface role contrasts and malformed dispositions. Improve weak open slices with independent templates and synthetic values, including local identifiers, linkage conflicts and date/age examples. Record disagreements and their resolution. | Reviewed scope and support by slice, coverage gaps and label version. Only compute precision and false-positive rate where adjudication and the declared negative unit universe support them. |
| 3. Author the sealed split in private | Allocate exactly 600 valid Patient Records to fresh patients, institutions, template families and document layouts. Reserve the sealed families and generator before seeing detector revisions. Group near-duplicates and variants within their own split. Independently adjudicate 140 sealed records and validate counts, original spans, references, supported attachment decoding and clinical facts. Keep rejection fixtures outside the quota. | Manifest digest plus aggregate allocation, lineage, annotation and schema validation results. Keep inputs, labels, rendering logic, seeds and case-level examples private. |
| 4. Prepare the common scoreboard | Extend the existing open evaluator with a split-neutral input contract so a private runner can apply the same checks. Add exhaustive-subset scoring, cluster metrics and pseudonym consistency, date/age policy checks, semantic clinical utility, run resources and offline R4/profile validation where claimed. Use synthetic test fixtures for the evaluator. | Verified scoring examples, metric denominators, unresolved cases and a pinned evaluator commit. The current open validator expects the two open splits. |
| 5. Run the frozen comparison | After A clears the open index coverage gate, freeze pipeline, scorer, configuration, schema assets and run limits. Run V1 and the approved candidate against identical sealed inputs. Use identical case definitions and report aggregate detection, linkage, clinical utility, coverage and resource results. | Frozen SHAs, input digest, run protocol, aggregate scores and uncertainties. If sealed observations guide tuning, classify that split as development evidence and establish a new sealed run. |

### Sealed allocation

| Format | Records |
| --- | ---: |
| CSV | 120 |
| TSV | 90 |
| JSON | 120 |
| FHIR R4 | 120 |
| Plain text | 150 |
| **Total** | **600** |

Use the [scenario quotas and custody protocol](research/dataset-v2-design.md#allocation). The shared qualification run checked generated FHIR against the published R4 JSON Schema and local structural checks. Full R4 rules, terminology and any ABDM conformance claims require separate validation. Independent clinical review and near-duplicate adjudication remain open.

## Integration gates with Developer A

- The indexing candidate `d25e72a` found 362 of 1,400 expected open locators, while V1 `095c854` found 1,400. Sanitized artifacts were byte-identical. Keep both the old practice/regression checks and this new generalization check. A owns the runtime fix. B owns the evidence and scorer. [Baseline](datasets/robustness_v2/v1-baseline.json)
- Before sealed evaluation, require zero extra locators on adjudicated metadata controls and agreement on required locator coverage over the open corpus. Share open development examples for debugging. Treat any validation cases used for rule development as development evidence.
- Keep model work behind dataset readiness and approval. Report generated and adjudicated evidence separately. Current identifier residuals count literal labeled surfaces in the mapped channels and cannot support a complete privacy claim.

[Earlier Developer B handoff](developer-b-v2-handoff.md) · [Development plan](development-plan.md#version-2-planning-and-handoff)
