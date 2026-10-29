# AIL v4.3.1 — Same-day evidence-ready recovery and actual prompt ledger

This is an **additive review/continuity release**. It preserves the complete v4.3 code, and uses the actual existing v4.3 Mac-generated MP4 without repeating the provider request.

## What it solves

- Previously the dashboard did not explain that only one of six frozen video tasks had been requested; this release labels each task with the correct status.
- A video plays only when the existing MP4 matches its recorded SHA-256; missing and altered files fail closed.
- Proper HTTP `Range`, `HEAD`, `206` and `416` handling supports browser media seeking.
- JS uses a separate file and can be syntax-checked (`node --check ail_v431/app.js`).
- Provider generation is **never** triggered at startup. Generating another missing prompt requires explicit click and a confirm dialog; it may consume a third-party shared-GPU quota and can fail. An attempt is counted even if provider generation fails.
- All raw prior files are preserved; a separate timestamped `runs/v431_*` folder stores review receipts and upload ZIP.

## Mac launch

After downloading the ZIP to Downloads:

```bash
setopt interactivecomments
cd "$HOME/Downloads" || exit 1
ZIP="$HOME/Downloads/agent-intelligence-lab-v4.3.1-evidence-ready.zip"
TARGET="$HOME/Downloads/AIL-v431-executions/source-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$TARGET"
unzip -q "$ZIP" -d "$TARGET" || exit 1
cd "$TARGET/agent-intelligence-lab-v4.3.1-evidence-ready" || exit 1
bash ./run_v431.sh
```

The default is a **no-provider-call startup**. It auto-discovers original complete v4.3 runs under `~/Downloads/AIL-v43-executions`, runs inherited plus new tests and source-integrity validation, creates the evidence ZIP, then opens the UI. Click "Generate this prompt" only if you explicitly want another real provider attempt.

Optional: `bash ./run_v431.sh --max-new-calls 0` is a strict review-only session.

On browser exit, press Ctrl+C. The Terminal prints the sealed `UPLOAD_THIS_v431_*.zip` path under the *new* project `runs/v431_*` folder. Original MP4 and original generated reports remain under the original v4.3 run.

## Evidence limitations

- Existing real source: one five-second LTX clip. Five other video prompts not generated. Video output is not necessarily prompt-compliant.
- Renderer code can be audited, but original generated MP4 bytes are present only on the user's Mac; this build environment cannot play that exact clip.
- Automated tests exercise deliberately created local MP4 fixtures and mocked model failures; they do not prove a fresh new provider run or customer quality.
- Do not share any generated video externally until its content and licensing are reviewed.
- No active Driftwood stage ingestion, no real billed provider tariffs and no demonstrated AIL economic advantage over strong OSS.

## Documentation

- `docs/VERIFIED_EVIDENCE_CARD_2026-10-25.md`
- `docs/DRIFTWOOD_OUTREACH_DRAFT_2026-10-25.md`
- `docs/A16Z_SPEEDRUN_SR008_APPLICATION_DRAFT_2026-10-25.md`
- `docs/PROJECT_CONTINUITY_MASTER_2026-10-25_V431_ADDENDUM.md`
