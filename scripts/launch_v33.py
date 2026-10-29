#!/usr/bin/env python3
"""One-process test, execute, audit, archive, dashboard entry point."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ail_v33.benchmark import run_all
from ail_v33.dashboard import serve


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclusive_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, indent=2)
        f.write("\n")


def main() -> int:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = "v33_" + timestamp + "_" + uuid.uuid4().hex[:8]
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    print(f"New immutable run: {run_dir}", flush=True)
    # Test log recorded even when test suite fails.
    test = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                          cwd=ROOT, capture_output=True, text=True)
    with (run_dir / "tests_v33.txt").open("x", encoding="utf-8") as f:
        f.write("COMMAND: python -m unittest discover -s tests -v\n")
        f.write("EXIT_CODE: " + str(test.returncode) + "\n")
        f.write(test.stdout + test.stderr)
    print(test.stdout + test.stderr, flush=True)
    if test.returncode:
        print("FAIL CLOSED: tests failed, benchmark/dashboard not started. Share tests_v33.txt.", flush=True)
        return 2

    report = run_all(run_dir / "executed_cases")
    report["run_id"] = run_id
    report["run_timestamp_utc"] = timestamp
    output = run_dir / "results_v33.json"
    exclusive_json(output, report)
    event_path = run_dir / "events_v33.jsonl"
    with event_path.open("x", encoding="utf-8") as f:
        for event in report["events"]:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    hmm_path = run_dir / "hmm_gate_v33.json"
    exclusive_json(hmm_path, report["hmm_challenger"])

    # Optional source ZIP checksum provenance; never open/patch/execute an unknown base.
    base_zip = os.environ.get("AIL_V32_BASE_ZIP", "").strip()
    source = {"v32_source_accessible_in_this_build": False,
              "v32_source_mounted_or_patched": False, "external_v32_zip_sha256": None,
              "explanation": "Companion only: original v3.2 source was unavailable when package was built."}
    if base_zip:
        p = Path(base_zip).expanduser()
        if not p.is_file() or not zipfile.is_zipfile(p):
            raise ValueError("AIL_V32_BASE_ZIP specified but not a readable ZIP; fail closed")
        source.update(external_v32_zip_sha256=sha(p),
                      external_v32_zip_basename=p.name,
                      local_zip_available_for_followup=True)
    exclusive_json(run_dir / "source_provenance_v33.json", source)
    files = [output, event_path, hmm_path, run_dir / "tests_v33.txt", run_dir / "source_provenance_v33.json"]
    manifest = {"run_id": run_id, "software_version": "3.3.0-companion",
                "files_sha256": {f.name: sha(f) for f in files},
                "source_tree_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sorted(ROOT.rglob("*.py")) if "runs" not in p.parts},
                "report_invariants": {"packages_equal": report["parity_exact_package_sha_across_arms"],
                                      "all_authorized_technically_valid": all(r["technical_valid"] for r in report["task_rows"] if r["status"] != "BLOCKED_UNAUTHORIZED"),
                                      "unauthorized_executed_no_stage": all(r["stage_ops"] == 0 for r in report["task_rows"] if r["status"] == "BLOCKED_UNAUTHORIZED")},
                "commercial_effect": "NOT_ESTABLISHED"}
    exclusive_json(run_dir / "manifest_v33.json", manifest)
    if not all(manifest["report_invariants"].values()):
        print("FAIL CLOSED: execution parity/integrity invariant violated; no dashboard.", flush=True)
        return 3
    package = run_dir / f"UPLOAD_THIS_{run_id}.zip"
    with zipfile.ZipFile(package, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files + [run_dir / "manifest_v33.json"]:
            z.write(p, p.name)
    print("\nRESULTS:", flush=True)
    for key, a in report["per_arm"].items():
        print(f"  {key}: {a['stage_ops_executed']} physical stages, {a['early_check_calls']} early checks, "
              f"{a['late_check_calls']} late checks, {a['technically_passed']} technical passes", flush=True)
    print("  Independently approved outcomes: UNOBSERVED", flush=True)
    print("  Commercial/OSS incremental advantage: NOT ESTABLISHED", flush=True)
    print("\nUPLOAD THIS SINGLE ZIP TO CHATGPT:\n  " + str(package), flush=True)
    print("Result JSON: " + str(output), flush=True)
    serve(output, open_browser=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
