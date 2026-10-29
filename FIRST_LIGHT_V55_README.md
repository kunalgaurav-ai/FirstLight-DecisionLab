# First Light v5.5 — QuixBugs executed, matched checkpoint study

## What this is

An **actual local-inference experimental platform** for two competing program-repair continuations. It takes publicly sourced QuixBugs buggy Python programs (MIT license, source repository verified and pinned to actual commit), produces **one shared actual Ollama patch**, then forks and runs two independent continuing strategies. It uses separately authored, precommitted smoke tests before commit and publicly supplied QuixBugs JSON testcases **only after** both strategies finish. No gold labels are supplied to models, task-selection logic, or policy runtime.

Policies:
1. `COMPETENT_TEST_REPAIR`: same local Qwen initial patch, static AST check, one task-specific smoke probe, up to two corrective model calls.
2. `FIRSTLIGHT_PRECOMMIT`: identical initial patch, same static policy, task-class-gated second probe, up to two corrective model calls.

**Important limitation:** The extra probe choice is a fixed heuristic, not calibrated intelligence or a strong OSS optimizer. This is a controlled incremental-probe pilot, not a proof of the First Light differentiated economic value. The competitor is a competent *local reference policy*, not a directly executed named OSS system. Code is AI-generated and run with static allowlists (including selected list methods) and subprocess CPU/memory limits; **not** a hardened VM security sandbox. Do not substitute customer code or untrusted content into this experiment. Use a VM for production code execution.

Measures real reported Ollama input/output tokens, per-call wall time, executed probe time, errors before commit, actual corrective calls, final held-out public testcase acceptance, and true differences between executed policies. Grade-only verification time is distinguished from billable controller overhead. First Light may *lose* to the comparator; no positive claims will be fabricated. The model is not assumed to be competent.

**Not SWE-bench** (official SWE-bench evaluation needs far more memory and disk space), not customer outcomes, not official BFCL ranking, not provider invoices, not strong OSS optimized production system, not proven long-horizon cascading error prevention. The code produces no $ savings estimate in the absence of invoices. Six tasks are too few for statistical/commercial conclusions. QuixBugs is a public program-repair benchmark with relatively small functions, not real codebase-wide software engineering. Exact diagnostic passes are on the repository's published tests and could differ from a hidden test suite.

## Mac launcher (one executable entry point)

From inside extracted release, run:

```bash
bash ./run_firstlight_v55.sh
```

The launcher **does not pull additional Ollama models**. It uses the existing `qwen2.5:1.5b`, sourced locally from Ollama on `http://127.0.0.1:11434`. If available, a tested external Python with Pillow is reused (set `FIRSTLIGHT_PYTHON` explicitly), otherwise a small private `.venv` is prepared for inherited regression tests. It canonicalizes macOS temporary paths, runs the **entire inherited regression suite plus v5.5 tests**, clones the public QuixBugs repo into a unique run folder, produces JSON/CSV, packages a SHA-256 verified ZIP, and opens the localhost dashboard.

```bash
# Optional run-size control (pilot only)
FIRSTLIGHT_TASK_LIMIT=3 bash ./run_firstlight_v55.sh

# Optional existing legal QuixBugs source checkout (no network required):
FIRSTLIGHT_QUIXBUGS_DIR="$HOME/Downloads/QuixBugs" bash ./run_firstlight_v55.sh

# Optional model already installed:
FIRSTLIGHT_MODEL='qwen2.5:0.5b' bash ./run_firstlight_v55.sh
```

No automatic deletion/overwrite. Each launch obtains a new unique `runs/firstlight_v55_.../`. To find evidence archive: `find "$HOME/Downloads/FirstLight-v55-executions" -name 'UPLOAD_THIS_FIRSTLIGHT_V55_*.zip' -type f`.

## Research limitations and safety gates

- Published ground truth: source repo `jkoppel/QuixBugs` / MIT; exact resolved git commit and hashes recorded in results; no test labels available to policy before final scoring.
- Initial response shared: comparator and First Light begin at the exact same initial patch; two actual continuations diverge after policy checks.
- All inferred tokens are Ollama-provided counts. Every model call, including failed repairs, belongs to that arm; initial call is counted for **each** counterfactual path.
- Model runtime timing can vary due warm cache and OS scheduling; one run is not reliable for latency superiority.
- The fixed semantic probes may be considered a trivially reproducible optimization by competitors. A future **named and legally usable OSS** reference and statistically calibrated risk policy are still required.
- Data security: public source only. AI-generated code runs in constrained Python child; not a secure sandbox for adversarial code. CPU and wall limits are enforced; no shell/network tools given to the model.
- Green dashboard only visualizes executed records. If QuixBugs clone or Ollama fails, `BLOCKED` with a reason and zero scores.
- The prior v5.4.1 Mac zero-incremental-savings result is copied intact to `evidence/mac_v541_verified` and not rewritten.
- Source-integrity manifests for all prior versions are preserved unchanged. New manifest covers v5.5 code and documentation.
