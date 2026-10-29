# AIL v4.1 — Mac FFmpeg compatibility and truthful diagnostics

**Use `bash ./run_v41.sh`**. The previous v4.0 archive and its source integrity record are preserved; v4.1 is the compatibility-corrected successor. This is an offline-compatible code package that fetches the eight curated CC0 sample images on a first full run, if the network and public source pages permit.

## Root cause of user v4.0 failure

On macOS Homebrew FFmpeg 9.0.2, the bundled build did not include optional `drawtext`. Two inherited video tests failed; the v4.0 launcher correctly stopped executing the main workload but incorrectly opened a blank review page. The user's actual result ZIP reported `unit_tests_pass:false`, zero asset downloads, zero LLM calls and zero trial attempts. It was not a completed video benchmark.

## v4.1 changes

- The video-assembly code rasterizes required captions locally in Python to transparent RGBA PNG (Pillow if already installed; otherwise *pure Python standard library* built-in small bitmap glyphs). FFmpeg uses core `overlay` and `zoompan` rather than `drawtext`. No model API or additional font download required. The captions are still physically encoded and their hashes enter the receipts.
- A new test suite checks the PNG fallback, renders a real captioned two-scene MP4 and verifies the generated commands never require `drawtext`.
- The launcher explicitly checks that the installed FFmpeg exposes `overlay` and `zoompan`. Test failure prints actionable details and does NOT open the empty review dashboard. When visual assets or other dependencies are absent, the dashboard shows diagnostic state and failures rather than implying success.
- Source-integrity manifest v4.1 records all shipped source files. The original v4.0 `workflow.py`, `launch_v40.py`, and `dashboard_v40.py` are frozen at `docs/preserved_v40/` and checked against the original v4.0 manifest. v3.9 files remain unchanged.
- **No fabricated results:** Local Linux testing cannot establish full Apple Silicon runtime, model quality, film approval or customer dollars. Eight fixture briefs, two photo scenes each, two arms, real Qwen inference/say/FFmpeg on Mac only if external dependencies/assets are available. Both arms are legitimate but not evidence of advantage over best OSS video optimizers.

## One command on an 8 GB Apple Silicon Mac

Extract the entire ZIP into a new folder under `~/Downloads`, enter its `agent-intelligence-lab-v4.1-compatible-visual-workflow` directory and run:

```bash
bash ./run_v41.sh
```

The launcher runs all tests, probes dependencies, retrieves the eight curated image examples from Commons, executes real two-arm local video production when allowed, records per-task receipts, generates `runs/v41_*/UPLOAD_THIS_v41_*.zip`, and opens an informative localhost review/dashboard. `Ctrl+C` stops the dashboard and repackages review evidence.

Use `bash ./run_v41.sh --quick` for one task (two arms) to validate the local media path before the full test. That is a **smoke test, not a comparative economic experiment**. It still performs the full unit suite. The `--no-fetch` option only works with a previously verified asset-root cache; it does not make up assets.

## Research and product limits

- The video visuals are thematic *stock photography*, not footage of fictional client locations and not AI-generated motion; the model writes text, the local system synthesizes audio, and FFmpeg makes real slideshow-like video.
- Curated topic tags do not constitute computer-vision semantic validation, and license claims from the catalog require rights rechecking before external release.
- No independently approved commercial outcomes, cloud invoices, or legally usable external OSS comparison have been measured here. Do not claim a competitive cost advantage from these fixtures.
- User v4.0 run: `UPLOAD_THIS_v40_20261025T060809Z_2e22b3ab.zip`. Two failed tests were due to the absent `drawtext` filter. Preserve it for provenance.
- Next evidence: actual Mac v4.1 reports, blind video reviews, meaningful visually grounded end-to-end workflows and incremental action policy versus capable alternatives.
