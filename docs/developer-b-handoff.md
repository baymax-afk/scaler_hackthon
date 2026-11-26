# Developer B handoff

The dataset improvement is already yours to continue. The proposed next responsibilities are dataset lineage, the common evaluator, and a narrow CSV/text release slice. Confirm how much time you can commit to the last two items before we assign them. The source-unit format and the provisional evaluation gates are in the [development plan](development-plan.md). Our first comparison uses current synthetic material, so you can keep improving the corpus in parallel.

## Start with the data

1. Inventory the existing organizer practice input and Secret Wards Blind fixtures. Record which sources the team has already inspected, available label granularity, known templates and regeneration inputs. Keep the current checked-in datasets available for comparison. [Practice guide](DATASET.md) · [Team fixtures](datasets/README.md)
2. Design a small reserved preliminary slice across unfamiliar labels, Hindi and Hinglish, clinical hard negatives and multiple source channels. Group each patient, physical duplicate and derived variant with its source lineage. Hold out independently authored templates as well as patients. If existing fixtures have been viewed or share templates with development, create a small new synthetic slice. Keep held-out truth to yourself until predictions are frozen.
3. Draft one fully annotated source-unit example with the same surface in two roles. Record original code-point offsets, expected role/type and independent clinical protection. Include the annotation schema, input version and provenance. Share one development-safe example, aggregate split counts and confirmation of whether an independently reserved slice exists. The organizer's surface annotations and current team record truth can seed the labels. Verify exact occurrences before using span metrics.

## Worktree setup

Use your own checkout of the same team repository. The shared handoff branch is `docs/phase-a-handoff`. Fetch it and create a sibling worktree from that base so the plan and handoff travel with your first slice.

```sh
git status --short --branch
git fetch origin
git show --no-patch --oneline origin/docs/phase-a-handoff
git worktree add -b feature/data-evaluation ../t3_scaler-data origin/docs/phase-a-handoff
cd ../t3_scaler-data
```

If your branch already exists, use its existing worktree or attach it with `git worktree add ../t3_scaler-data feature/data-evaluation`. Start with the dataset inventory and preliminary fixture slice. Review the draft source examples with A before treating them as a stable contract. Keep dataset, evaluator and release-adapter changes in focused branches or PRs so each can be reviewed independently. [Git workflow](development-plan.md#git-collaboration)

## First integration

- **Before approval:** continue the delegated dataset improvement and share the inventory, sample annotation and coverage gaps. Confirm Linux runner access and your preferred responsibilities.
- **After approval:** build the evaluation harness against synthetic predictions, then plug in A's output after the interface checkpoint. Test correct matches, boundary/role mistakes, duplicate values, incomplete units and metrics with no positives or negatives. Provide a documented local run command and aggregate output.
- **If you own release integration:** build the CSV/text path with a fake detector, verify the output ledger and protected values, then connect the actual detector. Widen to JSON and FHIR once the initial seam is proven. Escalate unresolved format or locator decisions to the joint checkpoint.
- **For the later model:** report whether improved data has sufficient independently labeled groups before training. Keep final test inputs and truth distinct from development, preserve the common predictions contract and record artifact provenance. Training starts after dataset readiness and the Phase B decision.

When handing off a slice, include the base and branch, affected paths, the command and result for the checks you ran, and one integration example that uses synthetic values. A can proceed with development-safe fixtures and a stub adapter while you work. [Phase A experiments](research/candidate-pipelines.md#experiments-for-approval)
