# First Light v5.4 | 11-model public benchmark screening and conditional runtime decisions
**Release: 2026-10-25. Actual evidence classification: Local public BFCL V4 diagnostic. No official leaderboard, SWE-bench repairs, live customer outcomes, or invoice-backed cost claims.**

## What v5.4 ACTUALLY does
- Preserves all inherited AIL and First Light v5.0–v5.3 source and user-supplied historical evidence unchanged (verified prior hashes).
- Freezes an **eleven named-model candidate registry**, then detects which models are actually installed. It never silently displays unexecuted models as if they were measured.
- Pulls missing models serially only with the explicit `--install-models` flag; the Mac needs **at least 12 GB free disk** for this flag to proceed. A 4B model MAY fail under 8GB RAM; no guarantees of availability. Every inference is serialized and requests `keep_alive=0` to unload model weights after each call. Large experiments still take time.
- Reuses the already downloaded official BFCL dataset from your earlier v5.2 experiment ONLY after verifying source SHA hashes; downloads and pins the source if no local copy is found. No questions are paired with gold answers in the model prompt.
- Runs a fixed **24-case screening cohort** across all *installed* candidate models. Selects up to three finalists by scored quality with stage-time tie breaker, including a cheap model anchor. Uses a completely **disjoint 24-case held-out set** across the four actual runtime policies below. Larger source counts can be configured.
- Collects Ollama-reported input/output tokens, complete model call time **including model loading**, per-call detailed provider time and attempts; does not equate model tokens with billed USD.
- Generates a real evidence-led localhost research page with two frontiers, all scores including losses, a per-task table, and a downloadable evidence ZIP with official source and SHA provenance.
- Records **single-turn precommit schema warnings**. This is NOT a validated long-trajectory predictor; stage lead time and causal downstream savings are not claimed.
- Optional: evaluates a separate *user-supplied* dataset of annotated trace prefixes. Retrospective prefix analysis is not causal outcome-cost savings.

## Policies, comparators and fail-closed action
1. `SINGLE_TARGET`: one target-model inference call; model quality reference.
2. `GUARDED_TARGET`: target model and one ordinary schema-retry. **Competent baseline.**
3. `COMPETENT_CHEAP_FIRST`: cheap Qwen 0.5B and schema-check, escalate to the SAME target model if invalid. **Primary economic comparator.**
4. `FIRSTLIGHT_CONSTRAINED`: same competent cheap-first workflow unless the **separate screening split** shows at least 12 paired graded cases for a task class, a nondegenerate cheap-model success mix, and >=20 percentage point target-model improvement in that class. If so, preflight route to the target model. This is an uncalibrated precommitted screening rule, **not** a learned failure predictor and not guaranteed to save resources. Missing credible support => baseline fallback.

All rules use the user question, tools and frozen *screen-only* statistics. Gold labels are used only for evaluation and screening, not injected into model prompts or online decisions. Inherited BFCL grading is a known **local diagnostic subset** of the official evaluator. Full all-in provider bills, task-independent QA, external OSS package execution, and cross-modal generalization are not established.

## Exactly one Mac launcher
The user saves `first-light-v5.4-rigorous-benchmarks.zip` into `~/Downloads` and runs:

```bash
setopt interactivecomments
cd "$HOME/Downloads" || exit 1
ZIP="$HOME/Downloads/first-light-v5.4-rigorous-benchmarks.zip"
[ -f "$ZIP" ] || { echo "Download v5.4 ZIP first"; exit 1; }
TARGET="$HOME/Downloads/FirstLight-v54-executions/source-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$TARGET"
unzip -q "$ZIP" -d "$TARGET" || exit 1
cd "$TARGET/first-light-v5.4-rigorous-benchmarks" || exit 1
bash ./run_firstlight_v54.sh
```

The default does NOT download models: runs all already installed models from the 11-model registry (at least two, including the Qwen 0.5B anchor). To explicitly authorize missing pulls and request a broad matrix: `bash ./run_firstlight_v54.sh --install-models`. **This opt-in can download multiple gigabytes and may fail when the Mac or network is resource constrained.** A blocked pull is recorded and the runner will still use installed candidates. Do not assume 11 models were installed or run unless the actual report confirms it. To select known installed candidates use `FIRSTLIGHT_MODELS="qwen2.5:0.5b,qwen2.5:1.5b" bash ./run_firstlight_v54.sh`.

You may set `FIRSTLIGHT_SCREEN_LIMIT=24 FIRSTLIGHT_EVAL_LIMIT=48 FIRSTLIGHT_FINALISTS=3` for more distinct tasks. Every model, policy and stage consumes genuinely measured local inference calls.

After the localhost dashboard opens, press `Ctrl+C` to stop it. The `UPLOAD_THIS_FIRSTLIGHT_V54_*.zip` path is printed in terminal and stored inside `runs/firstlight_v54_*/`. Results contain research JSON/CSV, evaluated model outputs, initial logs, and pinned dataset bytes where available. **Do not publish raw proprietary data if you replace the public dataset.**

## Optional annotated prefix analysis
Supply your own **legally usable, independently annotated** JSONL file. Each record needs `trace_id`, `terminal_success`, `failure_step` (null for safe, positive integer for failed), and an ordered array `events` of `{ "step": positive_integer, "precommit_risk_score": number_in_[0,1], "detector_wall_ms": number }`. Scores must have been generated from that prefix only; the file parser rejects common future-label fields inside events, but cannot establish actual upstream label independence or data rights. Set `FIRSTLIGHT_ANNOTATED_TRACES_JSONL=/absolute/path/to/trace.jsonl` at launch. Output is **retrospective**, not a randomized or real continued agent economics study.

## Known blocked inputs and follow-on milestones
- Official BFCL grading: official evaluator integration/validation required before an official leaderboard claim. Small local diagnostic is not identical to Berkeley's grader; evaluation flaws identified in community audits may matter.
- **SWE-bench Verified / Pro**: genuine patch agents + official container execution require sanctioned hardware well beyond Mac 8GB for normal full runs. No SWE-bench benchmark results are created by this release.
- Real multi-step error localization, calibrated safe/failed trajectory labels, and checkpoint-randomized **executed** baseline-vs-intervention continuations: **not provided** by 24 single-turn BFCL calls. Separate prospective study is necessary.
- Routing/compression/cache comparisons to RouteLLM, FrugalGPT, LiteLLM and other OSS: competent **reference implementation** is included; these OSS packages are **not run in v5.4**, so no claim of beating best OSS is supported.
- Billing/cost of locally hosted models: unmeasured electricity/capex/hosting; no USD savings, only observed tokens and latency.
- Multi-modal workflows remain preserved in archived modules; the runtime decision law is intended to be modality agnostic, but **only tool-use calls are evaluated in this public benchmark**.

## Website publication gate
No multiplier, no comparative superiority, no independently approved outcome / dollar figure unless the report's original task evidence, official scoring, final quality constraints, and complete costs support it. Negative/tied experiments stay visible.
