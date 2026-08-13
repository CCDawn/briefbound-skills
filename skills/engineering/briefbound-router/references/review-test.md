# Briefbound Router Review and Test Reference

Read this file when Briefbound Router needs a Review Matrix, evidence quality check, or test-level choice before routing to the next Briefbound stage.

## Review Matrix

Choose 2-4 perspectives from the current risk, not from a fixed role checklist:

- Core user: visible behavior, failure path, expectation mismatch.
- Maintainer: complexity, ownership, future change cost.
- Test/QA: observable contract, missing cases, flaky evidence.
- Security/privacy: permission, secrets, data retention, deletion, logging.
- Ops/support: rollout, rollback, diagnostics, recovery.
- Integrator/API user: compatibility, schema, state, public contract.

Each row must be short:

```text
Review Matrix:
- [Perspective]: Challenge: ...; Evidence: ...; Verdict: PASS / NEEDS_CLARIFICATION / NEEDS_CHANGE / ACCEPT_RISK
```

Verdict rules:

- `PASS`: evidence directly supports the behavior or route.
- `NEEDS_CLARIFICATION`: user choice or missing requirement can change behavior, scope, or risk.
- `NEEDS_CHANGE`: current contract, plan, task, or implementation is wrong.
- `ACCEPT_RISK`: residual risk is known, bounded, and explicitly accepted or recommended with clear tradeoff.

Unresolved `NEEDS_CLARIFICATION` or `NEEDS_CHANGE` blocks the next stage.

## Evidence Quality

Valid evidence comes from at least one source:

- user selection or confirmation;
- local code, docs, tests, logs, config, commit history, or project memory;
- executable test, build, lint, type check, smoke check, or structural inspection;
- reversible probe with expected observation signals;
- explicit assumption plus risk and later verification method.

Invalid evidence:

- "should work";
- "looks fine";
- "low risk";
- "will test later";
- repeating the recommendation as proof;
- saying the agent will be careful.

If evidence is thin but the risk is low and reversible, mark `ACCEPT_RISK` and state the verification anchor. If evidence is missing for a high-risk choice, mark `NEEDS_CLARIFICATION` or `NEEDS_CHANGE`.

## Test Level Choice

Use the lowest level that proves the behavior:

- Unit: rules, parsing, strategy, state decisions, pure logic.
- Integration: persistence, filesystem, multiple modules, agent workflow, config.
- End-to-end: only a real chain proves the user-visible behavior.
- Manual acceptance: visual quality, exploratory behavior, or temporarily non-automatable outcomes.

Testing anchor format:

```text
Test Anchors:
- Minimum proof: ...
- Command or check: ...
- Expected signal: ...
- Residual gap: ...
```

Do not route forward when the test anchor cannot prove the agreed behavior and no acceptable residual risk is recorded.
