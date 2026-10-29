# AIL v4.6 — Runtime bottleneck recovery and multimodal generation

**2026-10-25.** Source-preserving successor to validated v4.5. No claims of provider access, commercial savings, or video quality are made without receipts.

## Mac: ONE launcher

Download `agent-intelligence-lab-v4.6-execution-recovery.zip` into `~/Downloads`, then paste into Terminal (zsh):

```bash
setopt interactivecomments
cd "$HOME/Downloads" || exit 1
ZIP="$HOME/Downloads/agent-intelligence-lab-v4.6-execution-recovery.zip"
test -f "$ZIP" || { echo 'DOWNLOAD ZIP FIRST'; exit 1; }
DEST="$HOME/Downloads/AIL-v46-executions/source-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$DEST"
unzip -q "$ZIP" -d "$DEST" || exit 1
cd "$DEST/agent-intelligence-lab-v4.6-execution-recovery" || exit 1
bash ./run_v46.sh
```

The launcher uses its **own local `.venv`**, installs lightweight official Gradio/Hugging Face Python clients if needed (no video weights), verifies historical v4.5 source hashes and v4.6 source hashes, runs all regressions, attempts a genuine local Qwen/speech comparison if available, packages run evidence, and opens the localhost dashboard automatically. Environment keys **must be supplied only through the local Terminal**, not chat or browser forms.

The dashboard **automatically recovers your prior genuine v4.3/v4.3.1 five-second lion/library MP4s**, if their local source files and original SHA-256 receipts are still under `~/Downloads/AIL-v43-executions` or `~/Downloads/AIL-v431-executions`. It shows them in a separate *Previously generated real videos* section without re-running the provider, changing the original source files, or pretending that their original full prompts equal a newly planned 8-second shot. If the files were moved/deleted or tampered, it shows why no video is available.

The dashboard lets you:
- Submit any new prompt for **real local Ollama text** and **macOS speech**, see failures and play output.
- View each of 19 ungenerated/generated 8-second moving shots across six 24–32s campaigns.
- Explicitly request a real **five-second LTX public Space probe** (limited/no-cost shared GPU; may fail; cannot meet an eight-second shot) or an **eight-second LTX v2 production shot** (paid; explicit consent and rate confirmation; requires locally configured `LTXV_API_KEY`).
- Import genuine MP4 shot results created externally (e.g. creator applications) or original generated images **from your Downloads directory** with provider/model and rights declarations. These are USER-ATTESTED and are not represented as verified remote provider receipts.
- Generate an image through the HF inference provider only if `HF_TOKEN` and explicit `AIL_ALLOW_BILLED_IMAGE=1` exist locally; model availability/fees unknown; this can fail or cost money. There is no free guarantee.
- Review actual video actions/motion/continuity, then assemble only SHA-verified, duration-valid, reviewed moving shots. Clips that merely pan over a static photograph cannot pass meaningful human motion review.
- Review actual job failures (`QUOTA`, `BLOCKED`, `FAILED_PROVIDER`), remote job IDs, model receipts and missing artifacts. Never auto-resubmit interrupted paid jobs.

Once dashboard closes with `Ctrl+C`, upload the newest `UPLOAD_THIS_v46_*.zip` found under `~/Downloads/AIL-v46-executions`. Raw media stay in each run folder, not the evidence ZIP. Raw prior releases and results are preserved; this release does not replace them.

## External providers and costs

Official LTX v2 adapter uses asynchronous `/v2/text-to-video` and a locally loaded API key. The rate field is a **user-confirmed estimate**, **not an invoice**. Confirm service/model pricing and permitted use before any billable request. To configure a key safely, set it in your own Mac environment, e.g. `export LTXV_API_KEY="..."` in the Terminal **without pasting the key here**, before `bash ./run_v46.sh`. Paid requests always require a separate dashboard click and confirmation; launching the script never consumes paid video/image API services.

Google Flow is a manual creative interface; it does not provide this release with authorized automated free video inference. Source scenes must be actually generated and user-attested after download and be compatible with the plan. A 24–32-second project is a multi-shot deliverable. The count of planned shots is not the count of generated clips.

External image generation with the official Hugging Face inference client requires the account's supported model/provider, availability, token and possible credits. `HF_TOKEN` alone doesn't guarantee generation. Use `AIL_ALLOW_BILLED_IMAGE=1` only after assessing provider costs.

## Experimental economics

The incumbent comparison remains v4.5's four fixed-fact text briefs and three speech tasks, with critical limitations (prewritten canonical text and standard exact caching). It isn't customer success or OSS superiority. The new `ail_v46.controller.bound_action` requires at least 30 independent, prospective, paired, independently quality-graded actual executions with bounded **all-in USD** costs, all comparable approvals, and a tail-risk budget before even producing a qualified economic hypothesis. Lacking data, the controller must HOLD. `workflow_action` can propose permission-scoped exact reuse, stop further regeneration for a reviewed shot, or require review before downstream spend. These are **safety/economic decisions, not proven proprietary gains**.

For real testing against competent open-source optimizers, use matched tasks, held-out prospective assignments, all-in provider + verification + labor + editing and monitoring costs, independent blinded quality review, actual licensed OSS implementations where applicable, failure mode analysis and noninferiority/risks. Do not convert local Ollama tokens or public quota consumption to hypothetical invoices.

## Troubleshooting

`BLOCKED_DEPENDENCY`: Provider/auth/quota unavailable. Read the job reason in the ledger. Do not retry indiscriminately.

`UNGENERATED`: The shot has not yet been requested or imported. It has no MP4 to display; that is not a browser bug.

`SHORT_FOR_TARGET`: Model returned a valid short moving video that cannot satisfy the eight-second requirement. Review/provenance are preserved but this clip cannot complete the campaign.

`FAILED_ARTIFACT` / unavailable player: Missing output, decoding failure, rights mismatch or SHA mismatch. Check full report; never substitute stock footage silently.

`INTERRUPTED`: The process stopped during an action. Reconcile the provider job ID before starting a new billable request, or you might pay twice.

`EXPLICIT_IMAGE_PROVIDER_ACK_REQUIRED` / `LTXV_API_KEY_NOT_SET`: Client has not authorized or configured provider access. Free access doesn't magically substitute paid generation.

`SOURCE INTEGRITY FAILED`: Release files changed. Use a clean extracted ZIP instead of modifying inherited sources.

**Validation boundary:** Automated live FFmpeg tests, model stub contract tests, real HTTP range responses and Chromium DOM tests have been executed. The chat build sandbox has no actual Mac Ollama/macOS say or authorized paid provider access, nor can its Chromium directly navigate localhost; a browser DOM test uses real HTTP state data through injected fetch and checks zero JS errors, while standalone HTTP tests validate real range transport. Mac test run is required for physical multimodal outputs. Evidence in the dashboard is not independently approved creative quality.
