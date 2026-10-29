# Agent Intelligence Lab v4.0 — visually grounded execution, not visual hallucination

**Purpose:** preserve v3.9 modules and benchmark reports, fix repeated unrelated footage, and physically execute a compact visually relevant multimodal editing experiment on an 8GB Mac with Ollama, macOS `say`, and FFmpeg.

## One command, Mac Terminal or PyCharm Terminal

After extracting project ZIP, from its root:

```bash
bash ./run_v40.sh
```

No API key, GPU or model download. Requires installed `qwen2.5:1.5b`, running Ollama, `ffmpeg`, `ffprobe`, `say`, network access to Commons for the 8 sample photos on the first run. Photos cached with content hashes + URL/provenance sidecars in `data/downloaded_cc0_v40/`. Download from Commons is free but might be blocked by local connection; do not override a blocked license/image gate by renaming Big Buck Bunny or substituting arbitrary photos.

Optional `--no-fetch` to use only previously verified cached photos; `--quick` executes 1 brief across 2 arms; `--no-dashboard` for automated smoke tests; `--task-limit 1..4`; `--asset-root /path/to/previously_verified_cc0_cache`. For a usable comparison default is all 4 tasks.

`run_v40.sh` verifies preserved v3.9 hashes + additive v4.0 hashes, runs all regression tests, checks dependencies, downloads/rechecks photographs, executes real Ollama storyboard and real speech and scene rendering when eligible, writes all stage receipts, packages `UPLOAD_THIS_v40_*.zip`, and automatically opens the local blind visual review dashboard. Press Ctrl+C to repack sealed review records. The ZIP excludes videos by design; video files and screenshots remain in `runs/v40_<id>/media/`.

## Real output distinctions

This release uses **8 human-curated preexisting Commons CC0 photos**, TWO PER THEME. They are illustrative museum/trail/library/glass B-roll. **They do not depict the fictional clients.** Each final video consists of two different animated still-image scenes with fact overlays and actual synthesized audio. This is **not** diffusion-based text-to-image or text-to-video generation and does not measure expensive paid image/video provider bills. Automatic topic-category matching cannot certify creative suitability. The video can be rejected by the human reviewer.

## Comparator design

- `B1_COMPETENT_TOOL_FIRST`: actual local LLM shot planning + source-preserving narration, standard curated shot admission, dual-scene encoding.
- `AIL_EXPERIMENTAL_CONDITIONAL_NARRATION`: same shot admission, actual LLM narration; when the exact source contract fails, choose a deterministic, auditable repair before speech and rendering. This is experimental action selection, and deterministic repair is not proprietary.

Both arms receive identical themes, assets, rights restrictions, exact-fact gate, and codec/pipeline. Execution order is deterministic shuffled within task. It is possible and plausible for AIL to be more expensive. Do not claim additive savings against OSS until approvals at parity, billing and applicable OSS execution exist.

## Evidence levels

- Actual local machine model input/output token receipts when Ollama executed, per-command wall times, actual media hashes and full decode results.
- Curated topic tags and caption overlays, NOT independent automated visual-semantic alignment.
- Review dashboard anonymous IDs, scoring of visual relevance/factual/creative/audio and accept/reject. A self-submitted score is not independently confirmed.
- Fictional input briefs and CC0 stock photos, not Driftwood customer work.
- Historical v3.8 and v2.7 negative/neutral results retained in docs, not superseded by fixture tests.

## Launch blocked? Check files

`runs/v40_*/source_audit_v40.json`, `download_visual_provenance_v40.json`, `benchmark_v40.json`. Missing Commons photos produce `BLOCKED_PRECOMMIT_VISUAL`, not substitute video. `FFmpeg` or Ollama missing produce `BLOCKED_DEPENDENCIES`, and results ZIP is still generated. No credentials accepted in chat; API keys never used.
