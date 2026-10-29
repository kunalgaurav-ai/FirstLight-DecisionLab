# First Light v5.0 — Competitive Benchmark Research Workbench

**Product:** First Light. **Source lineage:** Agent Intelligence Lab v4.6, preserved without modifying inherited source manifests.

## What is actually executable

- Fetches the **official BFCL V4** `simple_python` and `multiple` task files and possible-answer files over HTTPS from GitHub. Resolves `main` to a concrete 40-character commit hash and downloads all assets using that hash. SHA-256 per-file provenance is recorded. The Mac needs working GitHub HTTPS access the first time; cached source files can be reused after verification. This initial pilot does not reproduce the entire BFCL leaderboard.
- Precommits a deterministic, stratified task selection (24 default; up to 500 when requested; see note below). Preserves task IDs and prompts; the gold labels are never shown to Ollama.
- Runs **two actual inference policies** on identical cases: `COMPETENT_LLM_GUARDED` uses Qwen2.5:1.5B plus a single retry when JSON/schema invalid; `FIRSTLIGHT_ADAPTIVE` first uses Qwen2.5:0.5B and escalates to Qwen2.5:1.5B when the cheap response is malformed or violates declared tool schemas. The tools and model choices are selected *before* observing benchmark gold labels.
- Uses a **strict, local diagnostic scorer** for a subset of BFCL's possible-answer alternatives. It does not reproduce BFCL's official default-argument normalization and other category-specific evaluation rules. This diagnostic must not be called "BFCL V4 leaderboard accuracy." A raw mismatch may represent scorer limitations.
- Tracks per-case model responses, provider-reported token counts, elapsed model HTTP-call times, schema-validity, diagnostic pass/failure, McNemar paired test and Wilson intervals. No token-to-dollar conversion is fabricated.
- Generates an **offline-capable** responsive Research page with two data-driven frontier plots, an actual case ledger and downloadable raw JSON/CSV. No third-party CDN or JS dependency.
- Preserves old AIL source and prior results; per-run records in a new `runs/` path, checksum manifest and ZIP. No paid inference or external model download.

## Requirements

Mac Apple Silicon, working Ollama server, both `qwen2.5:1.5b` and `qwen2.5:0.5b` locally installed, Python 3.10+, HTTPS to GitHub. No paid API. If the small model is absent, install it yourself after confirming available disk/memory; the launcher does **not** silently pull it. On a missing model or blocked GitHub, a useful failed-dependency report and dashboard still launch, rather than fabricated scores.

## Single launcher

From the extracted project directory:

```bash
bash ./run_firstlight.sh
```

Default pilot runs **24 items** and can require minutes of local inference. Choose a larger precommitted local task limit with `FIRSTLIGHT_TASK_LIMIT=100 bash ./run_firstlight.sh`; monitor 8 GB memory and temperature. For recognized public leaderboard claims, running this pilot is **insufficient**. We must use the official full evaluator, validate data license and version, and repeat sufficient tasks with independent QC. This pilot does not test long multi-step enterprise workflows or video/image generation, though their code remains in the preserved project.

The launcher prints `UPLOAD_THIS_FIRST_LIGHT_V5_*.zip` and starts localhost Research. Press Ctrl+C to seal output; upload the result ZIP for analysis.

## Why not full SWE-bench on the 8 GB Mac?

The official SWE-bench Docker evaluation reference recommends **16 GB RAM**, **120 GB free storage**, **8 CPU cores**, and **x86_64** (arm64 support experimental), so running that full official harness here is not a defensible low-risk first-stage route: https://github.com/SWE-bench/SWE-bench/blob/main/docs/reference/harness.md. It remains our next priority on eligible compute. Public historical graded trajectories are not an AIL controlled execution or a causal savings study.

WorkBench is valuable for complete enterprise workflows and side-effect detection, and the 2026 evaluation reports saturation for top frontier agents, motivating quality-constrained economics: https://github.com/olly-styles/WorkBench. Need check the applicable task/data usage terms independently before external claims. This v5 pilot is narrower: official-source BFCL *single-turn* tasks.

## Proposed next high-impact validated experiment

1. Complete BFCL V4 official grading on an untouched subset (same task distribution, pinned model/version, and strong capable baseline), then entire relevant splits. Run a first public benchmark on comparable provider compute only when available.
2. Build an **agentic** WorkBench/τ-bench matched study, with multi-stage state transitions and observed logs, independently checked final state and harmful actions; compare strongest applicable OSS versus OSS+First Light.
3. Evaluate actual first-party multimodal stage graphs (speech, image, video, document, code) with modality-specific quality gates; cost shared stages, rework, checking, retry and human review. Never equate scene runtime with generative model GPU expense.
4. For the investor page, only promote speedup/efficiency multipliers when pass-quality is noninferior on a representative matched set and the measured denominator includes complete all-in expense. Show 95% uncertainty, coverage, per-category results and losses, not just headline maxima.

## Publication decision

As of this packaging: **HOLD**. No First Light BFCL official scores have yet been observed in this build environment, because it has no outbound DNS or your installed Ollama models. The v4.5 63.6% token reduction versus one-retry-only and the pre-written zero-model-token alternative are historically observed limited-scope results, not current First Light superiority. Commercial claims require permission/license verification and independent production quality.
