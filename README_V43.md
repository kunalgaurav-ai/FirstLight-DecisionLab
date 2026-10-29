# Agent Intelligence Lab v4.3 — Prompt-first genuine video-generation pilot

## Important distinction

This is a **new external model invocation path**, not a new slideshow renderer. The only admitted video-generation backend in v4.3 is the public, official **Lightricks/LTX-2.5** Hugging Face Space. It runs the distilled model on Hugging Face-hosted ZeroGPU, not on the user's 8 GB Mac. A video is labeled generated only if the remote model actually returns an MP4, the file exists locally and FFprobe can validate it. For real temporal and semantic suitability, a human must rate the output against the frozen prompt. MP4 technical checks cannot infer whether a librarian gave a book to a student.

**Status at packaging:** real FFmpeg integration and full software regression suite passed locally; this environment has no outbound network and cannot run the remote LTX service. Mac provider inference, generated video quality, GPU quotas, and actual dollar economics are **unverified**. There are no recorded customer approval outcomes. Absence of a result is reported explicitly.

## Start on Mac (single launcher)

From the unpacked project directory:

```bash
bash ./run_v43.sh
```

The launcher creates an isolated `.venv` in this release (does not modify the historical project's venv), installs `gradio_client` if necessary (needs an internet connection), verifies inherited file integrity, runs the full `unittest` suite, creates timestamped report JSON/ZIP, opens the localhost review dashboard, and **automatically queues exactly one true video model attempt** for the frozen `VID-03-LIBRARY-HANDOFF` prompt. It does not silently switch to fake video if the HF Space is unavailable. All other GPU calls require explicit clicks.

Environment defaults: anonymous ZeroGPU (free shared quota, limited). No HF token required for public access, but HF can block unauthenticated use. To opt into authenticated use, set `AIL_USE_HF_TOKEN=1` and `HF_TOKEN` locally using environment variables. This could consume an account's quota and, for paid tiers, prepaid credits—*the default launcher intentionally does not authenticate or bill*. Never send tokens in chat.

Optionally:

```bash
bash ./run_v43.sh --prompt-id VID-05-NATURE-MOTION --max-generations 3
bash ./run_v43.sh --no-auto-generate
bash ./run_v43.sh --no-dashboard
```

`--no-dashboard` still generates a JSON report and ZIP. The first live request needs the public ZeroGPU server to be reachable; it can fail due to daily quota, server cold starts, space changes, network restrictions or model errors. A blocked request is not proof of effective video generation.

## Evaluation sequence

1. Actual B1 baseline: send the exact frozen prompt unenhanced to the official Space and save the provider's video receipt, prompt, seed and decoded frame checks; record unknown USD.
2. Watch the MP4 and annotate every required event, timing/order, actual subject motion, visual consistency and safety. Independent-review status remains **unverified**, even if a reviewer marks themselves external.
3. If all conditions are reviewed and pass, AIL recommends **stop**: do not spend another model call. If a video is deficient, B1 may run a review-guided competent full retry; AIL can propose a distinct structured correction. For the lion prompt, AIL only executes multi-shot repair if at least three GPU calls remain and concatenates actual model-generated moving clips, not photos.
4. Review each candidate using the same criteria. The original receipt is part of each compared arm's total cost. Compare final accepted quality and all provider calls. Lacking provider prices or reliable independent approval, cost per approved outcome is **undefined**; no savings claim allowed.

Model-generated footage is **not the same** as customer production footage. The test tasks are created by AIL for development and contain no sanctioned Driftwood examples. The public Space has its own usage/rights terms; check those terms before external redistribution or commercial use.

## Report and media paths

`runs/v43_<timestamp>_<id>/UPLOAD_THIS_v43_<timestamp>_<id>.zip`

The ZIP includes `tests_v43.txt`, `source_audit_v43.json`, `frozen_prompt_protocol_v43.json`, `generative_receipts_v43.json`, report checksums and logs. Large generated MP4 clips remain under `runs/.../media/<clip-id>/`; no videos, tokens or private data are falsely supplied when the remote provider fails.

## Inherited source

All v4.2 modules and original release manifests are preserved. Prior Mac v4.2 evidence of eight photo-montage outputs is retained as source evidence in `docs/V43_MEASURED_BASELINE_AND_LIMITATIONS.md` and is not misrepresented as model-generated video. The **original v3.2 project** is still not integrated as raw executable bytes, as its archival copy cannot be materialized from Project Library access. v4.3 extends the **available v4.2 lineage** only.

## Core references

- Official Space code and input schema: https://huggingface.co/spaces/Lightricks/LTX-2.5/blob/main/app.py
- Official ZeroGPU quota: https://huggingface.co/docs/hub/spaces-zerogpu
- Official Gradio API: https://huggingface.co/docs/hub/spaces-api-endpoints
- Official LTX desktop hardware needs: https://github.com/Lightricks/LTX-Desktop
- T2V-CompBench: https://openaccess.thecvf.com/content/CVPR2025/html/Sun_T2V-CompBench_A_Comprehensive_Benchmark_for_Compositional_Text-to-video_Generation_CVPR_2025_paper.html
