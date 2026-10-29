# AIL v4.4 · Multimodal long-workflow study (October 25, 2026)

**Executive scope.** This is an executable integrated, safety-gated workbench with **11 frozen prompts** and **six distinct, longer video stories (24–32 seconds / 19 generated-motion shots)**. It preserves all v4.3.1 modules, old release manifests and raw result archives. It is *not* a claim that all eleven generative models execute in an 8 GB Mac or that customers approved an output.

## Evidence that the launcher actually produces

`bash ./run_v44.sh` automatically: checks integrity of inherited v4.3 and v4.3.1 releases plus the v4.4 files; runs the complete Python regression suite (including a genuine FFmpeg test); makes a local **Ollama text-generation attempt**, a real **macOS `say` speech-synthesis attempt**, and an explicitly **controlled deterministic coding repair/test experiment**; records image-model unavailability instead of generating fake images; writes JSON, checksums and `UPLOAD_THIS_v44_*.zip`; and opens the browser dashboard. It makes **zero remote video calls at startup**. Missing tools are classified BLOCKED. Text model `qwen2.5:1.5b` must already be available at `http://127.0.0.1:11434`.

**No assumption about provider access:** Longer cinematic video needs sanctioned video-generation capacity. We currently have two public-HF LTX 5.04s proof clips but the public HF Space is quota-constrained and v4.3's published contract only accepts 1–5s. To compare longer creative workflows use manually created **genuine moving clips** from Flow/Veo, Runway, a commercially approved image/video provider, or your own legally installed model. Those clips require import records; user-supplied provider identity is **attested, not independently verified**. We do NOT automate free consumer Flow via browser scraping. A sanctioned billable API may be integrated after authorization, with local keys through environment variables only.

## Mac installation and one launcher

Download `agent-intelligence-lab-v4.4-multimodal-workflow.zip` into `~/Downloads`, then paste:

```bash
setopt interactivecomments
cd "$HOME/Downloads" || exit 1
ZIP="$HOME/Downloads/agent-intelligence-lab-v4.4-multimodal-workflow.zip"
[ -f "$ZIP" ] || { echo "Download the ZIP first"; exit 1; }
TARGET="$HOME/Downloads/AIL-v44-executions/source-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$TARGET"
unzip -q "$ZIP" -d "$TARGET" || exit 1
cd "$TARGET/agent-intelligence-lab-v4.4-multimodal-workflow" || exit 1
bash ./run_v44.sh
```

The launcher prints its unique `RUN DIRECTORY`, ZIP and dashboard URL. Close the dashboard with `Ctrl+C` to reseal the ZIP after any reviews.

To find the ZIP afterward:

```bash
ROOT="$HOME/Downloads/AIL-v44-executions"
RESULT_ZIP="$(find "$ROOT" -type f -name 'UPLOAD_THIS_v44_*.zip' -print | sort | tail -n 1)"
if [ -f "$RESULT_ZIP" ]; then echo "$RESULT_ZIP"; open -R "$RESULT_ZIP"; fi
```

## Video creation: six benchmark stories, not one lion example

`data/workflow_suite_v44.json` stores prompts and hashes. Video briefs: lion wildlife temporal continuity, glassblowing material physics, library object handoff, warehouse robot avoidance, deer locomotion, and museum visit. They target **24, 24, 24, 32, 24, 24 seconds** respectively (3–4 planned 8s model-generated shots per story). Even when a completed MP4 technically encodes, its motion, prompt adherence, order, continuity and creative quality remain unknown until actually reviewed. Compilation rejects missing, tampered, under-duration or unreviewed segments. Caching cannot cross permission scope, task prompt hashes or model identity without separate validation.

### Import one genuine model-generated video shot

Use Flow or another authorized generation interface manually to generate a short **moving** clip for its shot prompt in the dashboard. Save the *actual generated MP4* to your Mac. Then, with the launcher running or after it closes, in a separate Terminal in the project root:

```bash
RUN="$(find "$PWD/runs" -mindepth 1 -maxdepth 1 -type d -name 'v44_*' -print | sort | tail -n 1)"
python3 -m ail_v44.cli --run "$RUN" import-video \
  --task VID-03-LIBRARY-HANDOFF \
  --shot VID-03-LIBRARY-HANDOFF-S01 \
  --file "$HOME/Downloads/my-real-generated-scene.mp4" \
  --provider "Google Flow (manual export)" \
  --model "Veo-model-as-shown-in-your-account" \
  --rights AUTHORIZED_NONCONFIDENTIAL_TEST
```

**Replace** the filename and model with real details, not placeholders. The CLI checks the file, copies it under its SHA256, and reports the duration gate. Provenance is `USER_ATTESTED_NOT_PROVIDER_VERIFIED` unless a directly integrated provider receipt exists. Repeat for each shot. The dashboard exposes one form per imported video for actual manual review; only reviewed shots meeting their duration and review rules can be assembled using the real FFmpeg function.

**Use v4.4's explicit free HF LTX 5-second capability probe only when deliberately spending quota, not as a full-story replacement**:

```bash
python3 -m ail_v44.cli --run "$RUN" ltx-proof \
  --task VID-03-LIBRARY-HANDOFF \
  --shot VID-03-LIBRARY-HANDOFF-S01 \
  --ack-quota --ack-short-clip
```

This will normally be `SHORT_FOR_TARGET` and will not pass the 8-second shot gate. **Never attempt this expecting a free 24-second finished film.** The call may fail due shared ZeroGPU quota. The original 2026-10-25 real lion and library video receipts are preserved separately; they should not be silently assigned to differently frozen new shot prompts.

### Import a real text-to-image output

`python3 -m ail_v44.cli --run "$RUN" import-image --task IMG-01-COMPOSITION --file "$HOME/Downloads/generated-canoe.png" --provider "actual-provider" --model "actual-model" --rights AUTHORIZED_NONCONFIDENTIAL_TEST`

Imports must decode as images; an asset with user-declared model provenance is not independently proven AI-generated, and the imported image is not automatically approved. The executable image-generation API adapter remains blocked pending authorized local or hosted backend; no fake sample is substituted.

## Controller and economics

At each commitment boundary, the controller considers `CONTINUE`, `VERIFY`, `REUSE`, `SELECTIVE_REPAIR`, `REGENERATE`, `ESCALATE`, or `STOP`. It refuses auto action when post-output quality is unknown, a mandatory constraint fails, permissions are unknown, or action-effect evidence is missing. Baseline = competent manual preflight, known-safe exact reuse, normal retry/review and targeted scene repair. AIL challenger = same baseline plus **evidence-qualified** conditional decision; it cannot claim novel savings merely for caching or early checks already available to the baseline.

Research formula for positive action-specific value of information: `p_lower * verified_avoidable_loss_lower - check_cost - instrumentation_cost > 0`, with probability and avoidance bounds learned only from admissible data. CVaR is calculated only on ≥20 actual nonnegative cost observations; such a small sample is still **not an external validation certificate**. Hard approval constraints override the economic score. Cost per approved outcome remains undefined without independent final approvals and real all-in prices. A causal policy comparison requires prospective matched randomized episodes or credible action-overlap with sequential causal identification; historical replays of one policy cannot create missing alternate-action outcomes.

## Honest limitations

- No inference that 19 video shots are already generated. The launcher runs prompt planning, real local modalities where available, and optional imports. It will display missing video shots explicitly.
- The controlled coding task uses a deterministic regression-test harness, **not a general-purpose coding agent**. Tool results establish only the narrow task's tests. The local Qwen task is real inference if accessible, but not independently approved.
- The macOS `say` path is real native TTS, **not** a separately measured high-quality neural speech generator or an independently assessed transcript.
- External video credits, API prices, provider usage terms and rights remain specific to each provider/account.
- Most v4.3.1 outputs are two short generated videos with zero independently approved output; no commercial incremental value is established.
- The latest original v3.2 executable ZIP is listed in the user's Project Library but remains unavailable as an authorized raw file in this build environment; this release **preserves the inherited v4.3.1 companion**, not a falsely asserted true v3.2 integration.
- Final creative quality must be rated by independent reviewers; the dashboard can collect self reviews but labels them correctly as not independent.

## Research references

- Sun et al., *T2V-CompBench* (CVPR 2025): compositional prompt binding, interactions and motion: https://openaccess.thecvf.com/content/CVPR2025/html/Sun_T2V-CompBench_A_Comprehensive_Benchmark_for_Compositional_Text-to-video_Generation_CVPR_2025_paper.html
- Lightricks, **LTX-2.5 official duration and model support matrix**: https://docs.ltx.io/models/ltx-2-5
- Conformal Policy Control (ICML 2026): https://proceedings.mlr.press/v306/prinster26a.html (assumptions matter; not implemented as deployable safe-policy certificate here)
- Safe Policy Improvement with Baseline Bootstrapping (ICML 2019): https://proceedings.mlr.press/v97/laroche19a.html
- OpenAI benchmark contamination caveat on SWE-bench Verified: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/ — reinforces the need for fresh independent coding-agent tasks rather than relying only on repeatedly inspected historical SWE trajectories.

### Optional: sanctioned, billable 8-second video-model API

The v4.4 source also includes a **gated** official LTX v2 asynchronous adapter for 8-second portrait shots. It is not used by the launcher and **you have not told us you have paid API credentials**. The interface will refuse to call the API unless a local `LTXV_API_KEY` environment variable is set, the rate is entered, and `--ack-billed-call` is supplied. The model call may cost money; the entered price creates an *estimate*, never an invoice.

```bash
python3 -m ail_v44.cli --run "$RUN" ltx-paid \
  --task VID-03-LIBRARY-HANDOFF \
  --shot VID-03-LIBRARY-HANDOFF-S01 \
  --model ltx-2-5-fast \
  --confirmed-price-usd-per-second "$LTX_CONFIRMED_RATE_USD_PER_S" \
  --ack-billed-call
```

**The rate variable above must be set from your real account tariff; no rate or cost is assumed.** Do not execute if it is unset. API credentials belong in your private local environment, never in this chat or a committed file. This code follows the official job-submit/poll/download pattern and has safety tests, **but it cannot be end-to-end tested against a billed service without authorization**. Sources: https://docs.ltx.io/quickstart and https://docs.ltx.io/models/ltx-2-5 .
