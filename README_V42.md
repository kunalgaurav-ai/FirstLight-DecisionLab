# Agent Intelligence Lab v4.2 — Wikimedia thumbnail host compatibility

**Fix:** v4.1 rejected all actual Commons thumbnail redirects. `thumb.wikimedia.org` is a legitimate Commons-hosted thumbnail CDN and is now allowed using **exact HTTPS hostname matching** with no arbitrary hosts.

This is an additive source release with v4.1 and preceding modules preserved, not a new generative-video optimizer. Includes the actual negative v4.1 Mac finding in `docs/V42_TRANSPORT_AND_EVIDENCE_DECISION.md`, new redirect-host security tests and inherited real two-scene FFmpeg tests.

**Mac setup:** FFmpeg/FFprobe and Ollama with `qwen2.5:1.5b` already installed, Apple Silicon 8GB, macOS `say`; online Wikimedia Commons retrieval is required. No paid API; no user secrets. No photos bundled; if images cannot be accessed due to network policy or other failure, gate blocks and records detailed diagnostics; do not interpret blocked as product performance.

### Run — copy/paste without comment lines

```bash
setopt interactivecomments
cd "$HOME/Downloads" || exit 1
ZIP="$HOME/Downloads/agent-intelligence-lab-v4.2-wikimedia-thumbnail-recovery.zip"
[ -f "$ZIP" ] || { echo 'Download the v4.2 ZIP first'; exit 1; }
TARGET="$HOME/Downloads/AIL-v42-executions/source-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$TARGET"
unzip -q "$ZIP" -d "$TARGET" || exit 1
cd "$TARGET/agent-intelligence-lab-v4.2-wikimedia-thumbnail-recovery" || exit 1
bash ./run_v42.sh
```

After reviewing dashboard videos, press Ctrl+C. Find latest results ZIP:

```bash
ROOT="$HOME/Downloads/AIL-v42-executions"
RESULT_ZIP="$(find "$ROOT" -type f -name 'UPLOAD_THIS_v42_*.zip' -print | sort | tail -n 1)"
if [ -n "$RESULT_ZIP" ] && [ -f "$RESULT_ZIP" ]; then echo "$RESULT_ZIP"; open -R "$RESULT_ZIP"; fi
```

Optional limited run: `bash ./run_v42.sh --quick` tests one case and two real policy arms; default runs four cases and two arms. For preserved previous downloads: `bash ./run_v42.sh --no-fetch` blocks unless verified sidecars exist in `data/downloaded_cc0_v42/`.

### Evidence semantics
Tests measure software and static-media plumbing, not real customer quality. Two source photos per fictional brief are theme-associated illustrative images, not the named venues. Each human approval is a blind review, but evaluator independence is not guaranteed by the system. No evidence yet of incremental commercial economics relative to OSS. If the asset source fails again, the upload ZIP retains the `fetch` message, `resolved_host` where available, and requested URLs for diagnosis.
