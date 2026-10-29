# First Light — Economic Decision Research Kernel

**This is NOT another promotional release.** It is an additive, independently testable experimental decision-controller branch inside the preserved First Light v5.5.1 source tree. It builds on the two actual null results instead of overwriting them.

The root-cause study is `docs/ROOT_CAUSE_AND_DECISION_THEORY.md`.

### One Mac launcher

```bash
FIRSTLIGHT_MODEL=qwen2.5:1.5b FIRSTLIGHT_TASK_LIMIT=14 bash ./run_firstlight_decision.sh
```

The launcher checks all inherited manifests, runs the ~333 inherited tests and 19+ new kernel tests, executes the 6 previously examined development programs and **eight unseen model-repair holdout programs**, writes provenance-checked JSON/CSV results ZIP and opens a localhost research dashboard. If Ollama is unavailable, it reports BLOCKED; it does not show invented scores. Dataset is bundled under MIT with source commit provenance. It uses the preinstalled small Ollama model, no paid API and no extra 11-model downloads.

**Caution:** Three continuations per task may generate additional tokens and consume minutes. Their model calls are real. In this branch the default task limit is 14 to include all eight holdouts. A smaller value up to 6 runs only development cases and establishes no prospective evaluation.

Final testcase labels are not read until all three policies have completed. The eight holdout precommit inputs were independently authored from task specs and checked for non-overlap with official JSON testcases; correct reference implementations are *not shipped*. All model outputs can be saved in the evidence archive (share externally only after separate usage/content review). Static execution filtering is **not secure isolation of untrusted code**.

The dashboard truthfully distinguishes real holdout measurements from historical offline diagnostic replay. Production value-of-information decision gating remains fail-closed without calibration and cost data. No actual official SWE-bench or strong third-party OSS performance is claimed.
