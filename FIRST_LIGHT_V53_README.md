# First Light v5.3 | Named multi-model comparison

This version preserves ALL previous releases and the original v5.2 Mac observation ZIP, unchanged. It adds a **local model × policy matrix** using two official BFCL V4 single-turn subgroups. It is not an official BFCL leaderboard result, and not a full-workflow or customer-cost benchmark.

## One Mac launcher

Run from project directory:

```bash
bash ./run_firstlight_v53.sh --install-models
```

The `--install-models` flag is an explicit opt-in for downloading missing Ollama models. Without the flag, missing models are reported and the study is held; it does not silently run an incomplete comparison. No paid model APIs or video-generation backends are called.

Default named models, run serially: Qwen2.5 0.5B, Qwen2.5 1.5B, Qwen3 0.6B, Llama3.2 1B, and Gemma3 1B. These are different model families, but all **small local models**, not a comparison to Claude, GPT, Gemini, ReasonBlocks or frontier providers. Model usage and applicable licenses remain the user's responsibility. Installation may download several GB and requires available disk space and internet. Use an 8 GB RAM Mac; only one model call runs at a time, but memory pressure still matters.

Set `FIRSTLIGHT_TASK_LIMIT=48` (default) or 96 to change study size. Set `FIRSTLIGHT_MODELS` to a comma-separated 2–8 member list **including `qwen2.5:0.5b`** for another predeclared study (e.g. larger Qwen). Keep those configuration changes in the resulting report, do not pool incomparable studies.

## Policies per model

- `SINGLE`: one regular JSON-tool-generation request using the model.
- `GUARDED`: schema-aware prompt, one corrective retry when JSON/tool schema invalid.
- `FIRSTLIGHT`: preflight route to target model when available tool count >= 2, else cheap local Qwen2.5 0.5B first, escalating on schema-invalid output. **No assertion of novelty or advanced failure prediction**; the existing strategy is a candidate execution policy and must beat the competent guarded baseline.

All arms run on identical selected BFCL task IDs. Gold answers are never passed to the candidate agent. The diagnostic scorer parses only supported one-call answers and is not identical to official BFCL evaluation. Missing or blocked branches are never silently dropped. No prewritten canonical answers used.

## Evidence and quality limits

Outputs: `matrix_results.json`, `matrix_rows.csv`, `official_data/SOURCE_PROVENANCE.json`, `UPLOAD_THIS_FIRSTLIGHT_V53_*.zip`, and a local research dashboard with measured quality–tokens and quality–wall-time diagrams. The ZIP is hashed and contains errors even for blocked tasks. Historical v5.2 evidence remains under `evidence/mac_v52_verified/`, not mixed into the new study.

Meaningful cross-model token and time comparisons require care: tokenizers differ; model warmup/load time and inference environment can differ; elapsed call time is not the whole workflow time; zero provider USD means **USD unmeasured**, not free production. No independently approved outcomes, official BFCL grades, or commercial cost-per-approved-outcome conclusions.

For public superiority marketing, additionally require official scorer, larger frozen held-out test set, a capable OSS comparator stack, independent success/quality, all overhead, audited permissions and confidence bounds. Longer multi-stage agent and media tasks remain essential and have not been replaced by BFCL.

For 8 GB Macs, the controller batches calls by target model and rotates policy order across cases. Runtime totals still include Ollama model-loading effects; they are not cross-provider speedup claims.
