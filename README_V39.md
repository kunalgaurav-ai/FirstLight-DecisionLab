# AIL v3.9 — Precommit Quality Gate and Competing Repair Actions

**Evidence label: EXPLORATORY LOCAL MODEL / LOCAL MEDIA ONLY.** This version extends the preserved v3.8 companion code; original v3.2 source remains unavailable as raw bytes in this environment. v3.9 does not claim to be an integrated v3.2 release, a generative image/video model, or customer-cost savings.

## Why v3.9 exists

The uploaded v3.8 Mac run (20261025T050730Z_a4652c4f) ran 8 real video-editing attempts using Ollama Qwen 2.5 1.5B, macOS `say`, and FFmpeg. Both arms created 4 technically valid MP4s but each only 1/4 final narrations passed narrow literal source-fact checks. A code defect permitted TTS and FFmpeg after a failed retry. 6/8 media attempts therefore followed a *known failing exact-fact gate*. v3.8 AIL had 5,459 Ollama tokens vs 4,434 for B1; no independent human approval.

## What runs

`bash ./run_v39.sh --source "$HOME/Downloads/agent-intelligence-lab-rigorous/data/open_media/bbb_480p_30s.mp4"`

The launcher checks the source manifest and inherited regression tests, runs true on-device Qwen2.5:1.5b storyboard generation and stage-appropriate source verification, optionally model narration, real macOS speech generation, physical FFmpeg encoding and full technical decode. All model calls, retries, blocked commitments and local resource receipts are retained. The dashboard opens on 127.0.0.1 after creating a report ZIP. Ctrl+C seals new review data and reveals the ZIP.

Default four constructed briefs, with the following separate executable arms (randomized per-task order, shared case-specific seed; outputs may still be stochastic):

- `B1_STRICT_REASK`: competent LLM storyboard/narration; if narration fails literal gate, attempt one LLM reask; if still bad, stop **before** speech/encode.
- `B2_TOOL_FIRST`: competent algorithmic source assembly for narration. Calls model for storyboard but **does not call model for narration**. Literal correctness is cheap; creative preference must be independently reviewed.
- `AIL_CONDITIONAL_REPAIR_EXPERIMENTAL`: attempts a model narration, then if it fails the exact-fact gate, switches to deterministic source assembly **without another model reask**. This is a *real action-changing heuristic*, not an empirically calibrated intervention policy. Must be compared against B2, not only against an inferior failure-prone baseline.

The storyboard does NOT have to repeat the source statements verbatim, because its role is a visual plan, not factual narration. A banned/contradictory statement in the storyboard is still blocked.

## Quality and scope limitations

Passing the contract means both author-provided factual sentences appear verbatim after normalization, and banned phrases do not. It is **not** semantic truth, visual relevance, creative quality or customer acceptance. The supplied 30s Big Buck Bunny video footage is a real moving clip but likely a poor aesthetic/semantic match to the fictional businesses. It is not generative video. Image-generation and generative-video API arms remain not tested.

An experiment may have zero completed videos in a strict arm. That is a fail-closed behavior, not completed success. Compare policy arms by expected **independently approved outcomes**, not mere token cost, technical decode or narrow fact checks. Approval stays UNKNOWN until separate, qualified blinded reviewers score the output. The built-in review UI captures assessments but does not establish reviewer independence automatically.

All runs are local Mac CPU/GPU/metered Ollama tokens and FFmpeg seconds, not billed provider USD. The historical SWE-bench grade parser still lacks recognized `outcome_source` provenance for 441 rows (a nested object rather than the expected string); the new `grade_schema_probe_v39.json` reports only safe key/type information. No training or causal savings claim is made from that dataset.

## Mac prerequisites

Apple Silicon 8 GB RAM; Ollama running locally with `qwen2.5:1.5b`; `ffmpeg`, `ffprobe`, macOS `say`; rights-cleared moving video (for internal research, source rights require verification before external distribution). Launcher does not download models, request API keys or silently substitute fake outputs.

## Files

Root launcher: `./run_v39.sh` (single command). Generated reports under `runs/v39_<UTC>_<id>/`. Upload this exact resulting file: `UPLOAD_THIS_v39_<UTC>_<id>.zip`, created automatically. It contains `runtime_evidence_v39.json`, `source_audit_v39.json`, `historical_observed_v39.json`, `grade_schema_probe_v39.json`, `tests_v39.txt`, `review_cards_public.json`, `frozen_briefs_v39.json`, `manifest_v39.json`, and optional independent `reviews.jsonl`. Raw model output and MP4/AIF media remain LOCAL under the same run's `media` folder.

## Next falsifiable decision

If B2 is cheaper and matches or exceeds creative approval, the adaptive policy should not be shipped. If AIL offers superior blinded acceptance at justified extra inference cost, characterize where, quantify uncertainty with independent tasks and stage-cost receipts, and then prospectively evaluate with new task families and commercially representative video assets. If all arms fail creative acceptance because the source media are unrelated, replace the cohort with authorized relevant assets rather than optimizing an irrelevant test.
