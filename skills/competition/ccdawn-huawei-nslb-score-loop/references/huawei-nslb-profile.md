# Huawei NSLB Score Loop

## Contents

- BRT interface and harness boundaries
- Context and mutation matrix
- Worker execution and validation
- Search, recovery, and online calibration
- Epoch loop and promotion gate
- Feedback, packaging, command routing, and memory updates

This file is the full Huawei NSLB project profile for the generic `ccdawn-score-loop` model.

Default entrypoint: `../SKILL.md`. Load this profile only when project-specific commands, mutation families, worker prompts, score anchors, ledger paths, or online feedback rules are needed.

Use this profile only for a Huawei Algorithm Challenge 37 NSLB workspace resolved by `../SKILL.md`:

```text
<project-root> containing src/Solution.cpp and the score-loop ledgers
```

This is a leaderboard search skill, not a planning template. Its main job is to make agents continuously produce executable, isolated, evidence-rich code experiments.

Core operating model:

```text
bold code mutation -> isolated first-kill -> current evidence -> lesson or candidate -> memory/search-graph update -> next mutation
```

Bad outcome: agents write long proposals, role-play panels, or template essays while no compilable solver variant is produced.

Good outcome: each edit lane changes one concrete mechanism in `src/Solution.cpp`, compiles or records a hard blocker, runs the smallest decisive test, and leaves a recoverable diff plus `child_result.json`.

## 0. BRT Interface

- Context Boundary: resolved project root, score-loop ledger/search graph, current baseline hash, isolated worker workspace, and the selected command/lane.
- Output Contract: status, epoch, worker, gate, package, online feedback, or recovery artifact with machine-readable evidence.
- Success Evidence: command output, `child_result.json`, attempt card, ledger/search-graph update, compiled diff, gate decision, or registered short submission package.
- Stop Condition: source drift, stale baseline hash, overlapping ledger/pool write, missing child result, invalid package, online feedback ambiguity, or user pause.
- Route Out: continue score-loop command, launch/recover workers, parent promotion gate, online feedback wait, project memory sync, or BLOCKED with one required input.

## 1. Core Mandate

Optimize the online hidden score while keeping the execution harness strict.

Current known online-best anchor, unless the ledger says otherwise:

- baseline: `baseline-044-large-sparse-phase6-residual-target`
- online score: `344736301`
- source SHA256: `28b33d6d67d547fbc4415ec363a1c80db7a1f8e2fe1f308fd96a8a528a0441cb`

Do not force every idea to stay inside baseline-044's local envelope. Use 044 as a successful playbook: it won because it found a concrete hidden-aligned mechanism, not because all future search must be conservative.

Post-044 neutral/down families are negative controls, not creativity bans. Avoid repeating them with the same causal variable, but revive a direction if a new variable, new witness, new target shape, or new implementation strategy is explicit.

## 2. Hard Harness Boundaries

Harden the harness, not the imagination.

Hard stops:

- source drift in the main workspace is unexplained
- active source hash does not match the intended baseline
- a worker would edit the main project instead of an isolated workspace
- a worker lacks lane id, workspace, baseline hash, first-kill or stop condition, and result contract
- ledger, pool, weights, mutation space, dataset ledger, search graph, or submission map would be written in parallel
- promotion would use stale evidence, missing child result, unverified combined patches, or online-regressed source
- online feedback would move best-known online without a real score improvement
- upload zip name is long; use short names such as `sub053.zip`

Soft signals that must not block bounded execution by themselves:

- weak validation thesis
- uneven role coverage
- missing risk gatekeeper
- imperfect portfolio shape
- low idea-board score
- missing same-case witness for an unrelated edit lane
- dataset backlog

Soft signals may reduce confidence, change the first-kill test, or block promotion. They must not turn a runnable mutation into paperwork.

## 3. Required Context

Before meaningful optimization, read enough current state to avoid stale decisions:

```powershell
python $tool status --project $project
python $tool doctor --project $project --min-score 0
python $tool drift --project $project
```

Also inspect the latest relevant parts of:

- `AGENTS.md`
- `.docs/project-memory/INDEX.md`
- `.docs/project-memory/memory.json`
- `docs/optimization-ledger.json`
- `docs/online-offline-weights.json`
- `docs/search-graph.json`
- `docs/attempt-cards/`
- `docs/failed-diffs-index.json` and `docs/failed_diffs/`
- `docs/nslb-history-for-ai-analysis.md`
- `docs/risk-resurrection-shortlist-*.json` when stagnating
- `<codex-home>\skills\ccdawn-huawei-nslb-score-loop\references\mutation_space.json`

Use logs, ledger, child results, and online feedback as primary evidence. Conversation memory is only a hint.

## 4. Code Mutation Matrix

Replace essay-style idea boards with a code-mapped mutation matrix. A lane is useful only if it maps a target component to an executable change or a diagnostic artifact.

Default lane artifacts are strictly stripped of conversational prose. The coordinator should produce raw JSON-compatible mutation rows; markdown explanations, role commentary, and "here is the plan" wrappers are execution noise. If a tool later extracts JSON from a noisy response, treat that as recovery, not compliance.

Minimum matrix row:

```json
{
  "laneId": "short-id",
  "attemptId": "short-attempt-id",
  "targetComponent": "chooseGreedyPort | improveHotPhasePorts | residual repair selector | scorer/proxy | dataset generator",
  "mutationType": "edit | architecture | controlled-risk | diagnostic | dataset | fusion",
  "hypothesis": "one causal mechanism only",
  "intendedMetric": "phase_inner | max_single | projected_global | job_between | runtime | legality | online-fit",
  "nonTransitionSignal": "what must move besides source_transition, or why this is a diagnostic lane",
  "smallestDecisiveTest": "single case, narrow suite, trace, or bounded enumeration",
  "killCondition": "flat/non-moving/regression/timeout/illegal output condition",
  "expectedDiffSurface": ["src/Solution.cpp"],
  "negativeControls": ["post-044 neutral family to avoid or compare"],
  "recoveryArtifact": "child_result.json plus diff/report paths"
}
```

Default candidate rows after the current Gemini/history review:

```text
chooseGreedyPort -> rank-basin tie-break / conflict trace -> max_single or projected_global
improveHotPhasePorts / residual repair -> O(1) micro-pass with <=32 candidate moves -> phase_inner or max_single
residual acceptance selector -> hard non-transition predicate -> reject pure source_transition smoothing
scorer/proxy lane -> adversarial large_sparse phase4-6 flow4096 fold -> online-fit calibration
risk resurrection lane -> revive previously blocked promising diff with new causal variable -> compile plus first-kill
```

Rules:

- No role quotas. No mandatory expert panel. No prose-only lane for edit/architecture work.
- A portfolio with fewer roles but more distinct causal mechanisms is better than a pretty template with repeated ideas.
- If the idea board produces stock lanes, manually rewrite it into mutation rows before dispatch.
- Proposal-only lanes are allowed only for diagnostics, dataset construction, or when the lane explicitly cannot edit code. They must still produce an artifact.

## 5. Worker Execution Contract

Each worker must be a diff-first executor.

Worker first actions:

1. Work only in the assigned isolated workspace.
2. Write `worker_started.json`.
3. Verify workspace `src/Solution.cpp` SHA256 equals the lane baseline.
4. Verify main project `src/Solution.cpp` has not changed.
5. Read the lane matrix row and implement exactly one mechanism.

Edit/architecture worker requirements:

- Modify only allowed files, normally `src/Solution.cpp`.
- Use absolute `apply_patch` paths under the isolated workspace.
- Compile once, then reuse the executable with `--exe` for later checks when supported.
- Run the smallest decisive first-kill before wider suites.
- Stop early on kill condition, but preserve diff and metrics.
- Update `worker_heartbeat.json` after patch, compile, first-kill, and screen.
- Write `child_result.json` before finishing.
- Parse binary/scorer output with explicit structured patterns or report paths. If expected score/runtime/component regex targets are missing, return `blocked-by-missing-target` instead of inventing metrics.

No-essay completion rule:

- `edit`, `architecture`, `controlled-risk`, and `fusion` lanes may not finish with analysis only.
- If implementation is impossible, output `blocked-by-missing-target`, `blocked-by-missing-witness`, or `needs-more-evidence` with concrete evidence and the smallest diagnostic artifact produced.
- If code was changed or compiled, the lane must leave a diff path or patch summary even when rejected.

Required `child_result.json` content:

```text
laneId, attemptId, baselineSha256, hypothesis, mutationType, changedFiles,
commandsRun, checksRun, smallestDecisiveTestResult, currentEvidence,
metricsBeforeAfter, promotionCandidate, result, summary, avoidNextTime,
budgetUsed, budgetExceeded, artifactPaths, diffSummary
```

For controlled-risk and architecture lanes also include `mutationAttempted=true` or `architectureAttempted=true`, unless blocked before editing with a clear reason.

## 6. Speed-First Validation

Use `smoke -> screen -> parent gate`.

Exploration stage:

- first-kill should be a single high-signal case, narrow suite, trace, or bounded enumeration
- kill flat or non-moving ideas quickly
- do not run broad suites before the target metric moves
- do not clone whole jobs or full-evaluate every candidate on large_sparse/PDF cases unless the lane is explicitly testing that runtime cost
- cache generated inputs, baseline outputs, trace reports, and compiled executables when safe

Screen stage:

- run 2-3 representative cases or one narrow suite for promising mutations
- include negative controls for post-044 neutral traps when cheap
- record runtime and worst case, not only score

Parent gate:

- full verification remains strict and belongs to the coordinator, not every worker
- workers should not burn their budget proving the whole submission unless the lane is already a top candidate

## 7. Anti-Smoothing And Component Discipline

Post-044 failures show that pure source-transition smoothing can look locally attractive while being online neutral.

Promotion-blocking decoy:

```text
source_transition improves, but phase_inner / max_single / projected_global / job_between / legality / runtime / online-fit do not improve
```

For solver-edit promotion, require at least one named non-transition component to improve or a diagnostic proof that changes the validation model. Do not require only `phaseInnerConflicts` to decrease; max-single, projected global, job-between, legality, and runtime can be legitimate non-transition wins.

Known engineering targets:

- Hard non-transition predicate: reject acceptance decisions whose only benefit is `sourceTransition`.
- O(1) micro-pass: keep candidate moves tiny, use delta state, and protect shadow peaks such as `phaseOut + addedLoad <= jobMaxOut` when claiming no projected-global change.
- Rank-basin probe: when top ports are near-tied, break ties with future conflict trace or lower historical load, not only port index.

## 8. Stagnation And Risk Resurrection

Global perspective rule:

- Before every epoch, inspect `stagnationMode.globalPerspective` from `idea-board` or `run-epoch`.
- If recent closed epochs spent most budget on residual-envelope, same-case, counterfactual, alternating-cycle, regret-shadow-price, exact-neighbor, or 044-style local probes with no promotion path, treat the current state as a local optimum basin.
- In that state, residual/same-case lanes are support lanes only. Materialize at most one such lane in the next batch unless it directly calibrates a broader pivot.
- The main budget must move outside the local basin: outside-residual-envelope mechanisms, PDF/legal materialized datasets, adversarial proxy construction, small enumerators, moonshot architecture, two-stage/shadow-assignment frontiers, fusion/synergy, objective reframe, or online/offline revalidation.
- Another empty same-case witness search is not progress unless it retires a global hypothesis, updates a dataset/proxy decision, or names a new causal variable that changes the search graph.
- A global breakout lane may fail locally and still be useful if it produces a reusable case, diff, discriminator, or proof that changes the next search region.

Trigger risk resurrection when either is true:

- two closed epochs produce no promotion path
- recent lanes repeatedly stop with proposals, missing witnesses, or template-shaped no-code outcomes
- the skill/tool contract has materially changed and older lanes were judged under weaker rules

Risk resurrection mode:

1. Bypass normal role-panel generation.
2. Do not invoke another open-ended exploratory thought loop.
3. Read `docs/risk-resurrection-shortlist-*.json`, attempt cards, failed/rejected diffs, search graph, and session lessons.
4. Hydrate 3-7 precise code recovery tracks into mutation rows.
5. For each revived direction, name the new causal variable that makes it non-duplicate.
6. Force raw isolated implementation attempts where possible: patch, compile, first-kill, `child_result.json`.
7. Archive rejected diffs and lessons, then retire completed/blocked lanes through `pool-retire`; do not destroy partial evidence.

Revive especially:

- previously blocked architecture edits
- risky but bounded local-search variants
- fusion candidates with complementary non-transition signals
- dataset/proxy ideas that explain an online/local disagreement
- 044-style forensic-before-patch lanes that search for exact moving cases before editing

Do not let risk resurrection become a new bureaucracy. Its purpose is to turn "we almost tried this" into actual diffs and measurements.

Legacy false-negative rescue:

- If earlier epochs were run before the current Code Mutation Matrix / failed-diff furnace rules, do not trust old `rejected`, `cancelled`, or `needs-more-evidence` labels as final.
- First rebuild the failed-diff furnace from all historical child results:

```powershell
python $tool failed-diffs --project $project --rebuild-from (Join-Path $project "tmp\score-loop-epochs") --write
```

- Then select resurrection candidates from `docs/failed-diffs-index.json`, not from memory alone.
- Prioritize compiled diffs with `MOVED_POSITIVE`, `UNKNOWN`, `FAILED_RUNTIME`, `blocked-by-missing-witness`, or `needs-more-evidence` when they contain a new causal variable or a reusable code fragment.
- Do not blindly rerun old broad variants. Rewrite each rescued direction into a one-mechanism mutation row with a smaller first-kill, explicit non-transition signal, and a new reason it is not the same failed attempt.
- Treat old full-suite regressions as warnings, not automatic bans, when the candidate had a localized component improvement that was never isolated under the current first-kill rules.

## 9. Search Graph, Memory, And Partial Recovery

All attempts should become searchable memory:

- `docs/search-graph.json` stores parent/fusion relationships
- `docs/attempt-cards/*.json` stores plan, diff, metrics, online result, and lesson
- `docs/failed-diffs-index.json` and `docs/failed_diffs/*.patch` store failed solver diffs with lightweight static signatures: target functions, control tags, key constants, compile status, first-kill status, metric deltas, and reusable patch path
- `docs/optimization-ledger.json` stores baseline and online feedback
- `docs/online-offline-weights.json` stores validation trust updates
- `references/mutation_space.json` stores stable allowed/frozen families

Never discard partial work:

- If a worker has source diff, executable, report, heartbeat beyond startup, or session evidence, do not mark it `cancelled-no-worker`.
- Recover it into `child_result.json`, or rerun the smallest decisive test in the same isolated workspace.
- Preserve failed compiled diffs under the run directory, `failed_diffs/`, or an attempt card patch field before retiring the lane.
- A rejected diff is useful search material if it names the causal failure.
- Novelty rejection is based on lightweight static signatures, not full C++ AST: exact failed-diff signature repeats require a named new causal variable before dispatch; near-duplicates should be rewritten or used only as risk-resurrection material.
- Bandit allocation may tilt future worker slots toward family/mechanism lanes with positive or reusable failed-diff signals. It changes selection pressure only; it never bypasses source safety, isolation, first-kill, or parent gate.

After each epoch, run learning before opening the next one:

```powershell
python $tool learn-from-children --run-dir "<epoch-dir>" --project $project
python $tool learn-from-children --run-dir "<epoch-dir>" --project $project --write-index --write-search-graph --write-failed-diffs
```

Use `--write-mutation-space` only for stable lessons that should affect future search.

## 10. Online/Offline Calibration

Kaggle rule: trust validation only after making validation trustworthy.

Treat local suites as folds with trust weights. Treat online leaderboard feedback as a sparse, expensive validation fold, not as a magic oracle.

When online and local disagree:

1. Record online feedback.
2. Identify which local fold lied and why.
3. Update weights or dataset candidates.
4. Create adversarial/diagnostic folds that mimic the hidden trait.
5. Only then continue similar mutations.

Useful adversarial traits now:

- large_sparse
- phase 4-6
- flow4096
- residual repair cases
- PDF/legal runtime stress
- post-044 neutral source-transition traps

Dataset/proxy lanes succeed by producing reusable cases, traces, or empty-search proofs. They do not need local score gain, but they cannot promote solver code by themselves.

## 11. Autonomous Epoch Loop

Use tool primitives instead of handwritten state files.

Default flow:

```powershell
# Resolve $project and $tool once using ../SKILL.md.

python $tool doctor --project $project --min-score 0
python $tool run-epoch --project $project --run-id "<epoch-id>"
python $tool dispatch-epoch --run-dir "$project\tmp\score-loop-epochs\<epoch-id>" --phase auto --max-workers 6 --write
```

`run-epoch` now creates a divergent mutation-matrix idea board automatically when `--idea-board` is omitted. Do not use the legacy mutation-space stock lanes unless you explicitly pass `--mutation-space-only` for tool debugging.

Default worker cap:

- One epoch materializes at most 6 lanes and launches at most 6 active workers by default.
- `idea-board`, `prepare-epoch`, and `run-epoch` all cap lane count to the default batch limit, so a normal epoch has no tail backlog.
- `dispatch-epoch` writes only launchable workers into `tasks`; launch all of `tasks` once, then wait for the batch to finish.
- `heldReady` should normally be empty. If it appears, treat it as overflow from manual manifest edits or existing active slots; do not launch it in the same batch.
- If an agent tries `--max-lanes 8` or `--max-workers 8`, the tool caps it to the default policy and records the cap in `maxDispatchPolicy` / `maxWorkerPolicy`.

Launch workers only from `tasks[*].spawnAgent.launchMessage`, then immediately serialize pool state:

```powershell
python $tool pool-update --run-dir "$project\tmp\score-loop-epochs\<epoch-id>" --lane "<lane-id>" --status active --worker-id "<subagent-id>" --write
```

Collect and close:

```powershell
python $tool collect-epoch --run-dir "$project\tmp\score-loop-epochs\<epoch-id>" --write
python $tool learn-from-children --run-dir "$project\tmp\score-loop-epochs\<epoch-id>" --project $project --write-index --write-search-graph
python $tool pool-retire --run-dir "$project\tmp\score-loop-epochs\<epoch-id>" --completed --write
python $tool close-epoch --run-dir "$project\tmp\score-loop-epochs\<epoch-id>" --write
python $tool gate-decision --child-result "<top-child-result>"
```

If Phase B is gated behind diagnostics:

```powershell
python $tool phase-transition --run-dir "$project\tmp\score-loop-epochs\<epoch-id>" --to-phase B --reason "<current evidence>" --write
```

Do not open a new epoch while the latest epoch has active workers, ready lanes, missing child results, partial workers needing recovery, or invalid closeout. Finish, recover, or explicitly cancel with `pool-update --status cancelled --blocker "<reason>" --write`, then collect and close again.

Continuous mode stops only when:

- a short upload package is ready and online feedback is required
- source/tooling/budget is genuinely blocked
- the user asks to pause
- repeated epochs produce no new evidence and no safe new causal variable can be named

## 12. Parent Promotion Gate

Only the coordinator may apply a worker diff to the main workspace.

Before applying:

1. Confirm the candidate was based on the current baseline hash.
2. Inspect diff scope and mechanism.
3. Reject broad bundles unless the diff is tiny and causally clear.
4. Run `gate-decision` and the required parent gate commands.
5. Apply at most one candidate.

Promotion requires:

- official sample regression passes
- outputs are legal
- quick/full and relevant narrow suites are parsed
- no catastrophic critical regression
- runtime/PDF/legal risk is acceptable
- zip contains exactly root-level `Solution.cpp`
- ledger, search graph, attempt card, and project memory are updated

Pure smoothing cannot promote. Local gain without online-aligned component evidence is a candidate at most.

## 13. Online Feedback

If the user reports online feedback, parse the short package/result and update state. Use `online-feedback` when the package name maps to `docs/submission-map.json`; use `online-update` when the attempt/family/mechanism are known.

```powershell
python $tool online-feedback --project $project --submitted-package "sub053.zip" --online-score "<score>" --write --write-ledger
python $tool online-update --project $project --attempt "<attempt-id>" --online-score "<score>" --family "<family>" --mechanism "<mechanism>" --shape "<shape>" --predicted-direction up --hidden-hypothesis "<hypothesis>" --write --write-ledger
```

Use `--accept-best-update` only when the score strictly improves and the coordinator accepts it as the new online-best. Neutral or worse scores update calibration but do not move online-best.

If online regresses, restore online-best:

```powershell
python $tool restore-online-best --project $project --write --update-ledger
```

## 14. Packaging

Before giving the user a submission:

```powershell
python tools\run_regression.py
python $tool register-submission --project $project --package "subNNN.zip" --attempt "<attempt-id>" --family "<family>" --mechanism "<mechanism>" --shape "<shape>"
```

The uploaded file name must be short, normally `subNNN.zip`. Put long baseline names and metadata into `docs/submission-map.json`, not the zip name.

## 15. Command Router

When the user invokes `$ccdawn-huawei-nslb-score-loop` or asks for status, epoch work, online update, gate, ranking, packaging, or worker recovery, route through this skill. Do not create a plugin.

Core command map:

```text
status: show active baseline, online-best, recent attempts, and pending submissions
doctor: audit readiness; warnings do not block creativity unless they are hard harness failures
drift: classify main source hash drift
restore-online-best: restore source from best-known online baseline
init-weights: initialize online/offline weights
online-feedback: parse reported submission package score and update mapped attempt
online-update: update weights and ledger for a known attempt
register-submission: map a short zip to attempt metadata

index: list historical fingerprints and duplicates
check: check one proposed family/mechanism/shape against history
suggest-lanes: propose non-duplicate lanes from mutation space
idea-board: create an idea board; convert it to Code Mutation Matrix before dispatch
epoch-board: inspect epoch lane state
prepare-epoch: prepare workspaces and manifest
run-epoch: doctor/status/prepare in one command
dispatch-epoch: create prompts, workspaces, launchMessage, and pool_state
phase-transition: move from diagnostic Phase A to edit Phase B
pool-update: serialize worker status changes
pool-retire: retire completed workers
collect-epoch: validate and rank child results, detect partial work
rank-children: rank completed child results
validate-child: strict schema and lane validation
learn-from-children: extract lessons and update index/search graph/mutation space
close-epoch: close the manifest with top decision
gate-decision: produce parent-gate requirements for one child result
archive-attempt: write attempt card, ledger record, and search graph node
attempt-card: create or inspect durable attempt card
search-graph: inspect attempt graph and fusion/revival candidates
failed-diffs: inspect or rebuild the failed diff furnace; use it for novelty checks, risk resurrection candidates, and patch retrieval
reweight-mutations: update mutation-space weights from online/offline trust

dataset-status: inspect dataset/proxy candidates
dataset-suggest: suggest folds/cases from online disagreement
dataset-validate: validate candidate datasets or generated cases
dataset-promote: promote stable dataset candidates into the local validation model

audit-skill: verify this SKILL.md mentions all tool commands
```

## 16. Minimal Worker Prompt

When launching a worker, prefer `spawnAgent.launchMessage` from `dispatch-epoch`. If handoff text is needed, use this compact contract:

```text
You are an isolated Huawei NSLB worker.
Main project is read-only: <project-root>
Work only in assigned workspace: <workspace>
Lane matrix row: <paste row>
Baseline SHA256: <sha256>

First write worker_started.json, verify workspace hash, then implement one code mutation or produce a concrete blocker.
For edit/architecture/controlled-risk lanes, prose-only completion is invalid.
Compile once, run the smallest decisive first-kill, preserve diff/report artifacts, update worker_heartbeat.json, and write child_result.json.
Do not edit main workspace, ledger, memory, dist, submission-map, or online state.
```

## 17. Memory Update

After meaningful work, update project memory and render the HTML overview unless the user explicitly says to skip:

```powershell
$memorySkill = Join-Path $codexHome "skills\ccdawn-dawn-agent-html-memory\scripts"
python (Join-Path $memorySkill "sync_project_memory.py") $project --lane "competition-huawei-nslb" --focus "<current focus>" --update "<what changed>"
python (Join-Path $memorySkill "render_overview.py") $project
```

Memory sync is part of done. Record both promotions and rejected lessons.
