# Agent Intelligence Lab v4.5 — Matched Local Intervention Study

**Research purpose:** Instead of recording one failed local Qwen text draft, physically compare subsequent decisions on **the same observed initial draft**, alongside a competent tool-first comparator that can skip LLM inference. Also execute actual macOS speech and compare conventional exact caching with AIL's own cache policy. Preserve v4.4's six precommitted long-video campaigns, 19 missing generated shots, prior reports and all older modules byte-identically.

## Single Mac launcher

Download `agent-intelligence-lab-v4.5-matched-interventions.zip` into `~/Downloads`. Open a new Terminal/PyCharm Terminal and paste:

```bash
setopt interactivecomments
cd "$HOME/Downloads" || exit 1
ZIP="$HOME/Downloads/agent-intelligence-lab-v4.5-matched-interventions.zip"
if [ ! -f "$ZIP" ]; then echo "Download v4.5 ZIP first"; exit 1; fi
TARGET="$HOME/Downloads/AIL-v45-executions/source-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$TARGET"
unzip -q "$ZIP" -d "$TARGET" || exit 1
cd "$TARGET/agent-intelligence-lab-v4.5-matched-interventions" || exit 1
bash ./run_v45.sh
```

The launcher runs all inherited and new tests, executes four **new** actual local-model initial prompts, branches each outcome to strict model retry and conditional repair (and evaluates a no-call competent deterministic baseline), synthesizes three real audio instances in each of three experimental arms, creates checksummed results ZIP, then automatically opens a localhost dashboard where verified artifacts can be played or inspected. Review buttons record **self-review only**; no independent approval is implied. Press Ctrl+C to close and reseal the results ZIP.

Find ZIP afterward in a new terminal:

```bash
ROOT="$HOME/Downloads/AIL-v45-executions"
RESULT_ZIP="$(find "$ROOT" -type f -name 'UPLOAD_THIS_v45_*.zip' -print | sort | tail -n 1)"
if [ -n "$RESULT_ZIP" ] && [ -f "$RESULT_ZIP" ]; then echo "$RESULT_ZIP"; open -R "$RESULT_ZIP"; fi
```

No secrets are requested. No paid video or image provider is invoked. The launcher requires local `qwen2.5:1.5b` served by Ollama (previously installed), `say` and `ffprobe` for audio. If unavailable, corresponding arms explicitly HOLD; conventional tool-first cases still run. It does not pull new models or auto-trigger GPU requests.

## Experiment design, baselines and limitations

**Text B1 (competent checked-generation):** Generates once, evaluates strict word-count and **literal exact-fact** contract, retries once if needed. **AIL:** after the *same observed first generation*, runs deterministic targeted insertion/padding; if unsafe/unable to satisfy objective constraints, falls back to the verified canonical template. **B2 (strong competent tool-first):** Direct canonical output with **zero LLM calls**. AIL does NOT receive credit for standard deterministic assembly. Call receipts include actual Ollama reported tokens, call time, text write overhead and repair computation. Reusing the same initial text for B1 and AIL gives a paired downstream comparison, not a fully randomized prospective A/B trial. This design cannot establish a dollar saving beyond B2.

**Audio B1 (naive-no-cache reference):** Sends only speech content to Mac `say` three times, never the delivery instructions. **Audio B2 (competent exact cache):** Two actual syntheses, one exact-content/voice/instruction cache reuse. **AIL exact cache:** The same competent caching strategy and expected two syntheses; parity is the correct result, not invented incremental advantage. Different speech acts have different input text; two repeated briefs are exactly identical. No ASR, listener intelligibility or speech quality certification is claimed.

**Tool execution:** The inherited v4.4 controlled code-repair harness is retained as a regression, not represented as a fully autonomous agent. **Video:** Six long 24–32-second storyboard tasks and 19 shot plans remain present and *not generated* by this launcher. Image generation still needs authorized backend. Demonstrating large video-cost savings requires a sanctioned generative provider, independently accepted clips, billable receipts and an applicable capable OSS video optimizer comparison. Google Flow consumer credits are not an automation API. Provider quality and dollar cost remain unknown here.

**Quality definition:** Text literal sentence presence + word count is an objective narrow gate, *not* semantic factuality, creative quality, human acceptance or rights certification. Reviews in this dashboard are `SELF_REVIEW_NOT_INDEPENDENT`. Software-test success is not agent success. Numbers include local Ollama token counts, not cloud invoices. AIL tool-first fallback may tie B2 but should not be labeled novel. There is no claimed improvement over strongest applicable OSS in this release. Full historical SWE-bench observational work remains preserved, and prior contamination constraints continue to apply.

## Evidence and safety

- Frozen prompts/canonical outputs with SHA256, inherited source manifest checks, new additive release manifest.
- No outside provider billing, no secrets in reports, no fake generated media.
- Real output files remain locally under `runs/v45_*/artifacts`; upload ZIP intentionally excludes raw text/audio artifacts and includes their hashes and structured summaries. Inspect before sending; outputs may reflect your local model.
- Failure, unknown provider usage, audio unavailability and review absence are explicit.
- `docs/V44_MAC_ACTUAL_EVIDENCE_V45.json` contains a minimal audited summary of the user's preceding v4.4 run, not duplicated raw customer data.

**Not a claim of commercial superiority.** Incremental economic value is only established by the relative results under independent outcomes; weak baselines or ordinary caches do not suffice.
