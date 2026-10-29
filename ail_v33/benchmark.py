"""Physical local execution benchmark using deliberately constructed cases.

Actual local text/SVG/WAV/JSON files are produced and SHA256-ed. Resource
exposure in the controller remains a constructed decision unit, not a bill.
No customer workflow, model inference, generated motion video or human approval.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from html import escape
from typing import Any

from .core import DecisionInput, OptionalCheckEstimate, decide, example_graph, strict_fingerprint, VERSION

ARMS = ("B0_LATE_CORRECT_REPAIR", "B1_COMPETENT_EARLY_CHECK", "AIL_V33_FIXTURE_POLICY")

# Constructed, independent-of-user-data scenarios. This is a software testbed.
SCENARIOS: list[dict[str, Any]] = [
    dict(id="C01_healthy_high", reference="Orion has three moons", claim="Orion has three moons", hint="high", defect="none", permission="ALLOW", provenance="VALID"),
    dict(id="C02_healthy_low", reference="Vela has blue dunes", claim="Vela has blue dunes", hint="low", defect="none", permission="ALLOW", provenance="VALID"),
    dict(id="C03_bad_upstream_high", reference="Pavo has amber lakes", claim="Pavo has purple lakes", hint="high", defect="upstream", permission="ALLOW", provenance="VALID"),
    dict(id="C04_bad_upstream_low", reference="Lyra has five rings", claim="Lyra has nine rings", hint="low", defect="upstream", permission="ALLOW", provenance="VALID"),
    dict(id="C05_local_audio", reference="Aquila has silver trees", claim="Aquila has silver trees", hint="low", defect="audio", permission="ALLOW", provenance="VALID"),
    dict(id="C06_missing_rights", reference="Draco has warm clouds", claim="Draco has warm clouds", hint="high", defect="none", permission="UNKNOWN", provenance="UNKNOWN"),
    dict(id="C07_explicit_denial", reference="Cygnus has glass rivers", claim="Cygnus has glass rivers", hint="high", defect="none", permission="DENY", provenance="VALID"),
    dict(id="C08_bad_upstream_high_2", reference="Carina has white storms", claim="Carina has violet storms", hint="high", defect="upstream", permission="ALLOW", provenance="VALID"),
]


def h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assumptions(hint: str) -> OptionalCheckEstimate:
    # Values are invented design assumptions for a deterministic testbed.
    return OptionalCheckEstimate(prior_defect_lower=.5 if hint == "high" else .005,
                                 prior_defect_upper=.6 if hint == "high" else .03,
                                 sensitivity_lower=.95,
                                 false_positive_upper=.01,
                                 avoidable_units_lower=12., test_units_upper=.15,
                                 false_alarm_disruption_units_upper=.2,
                                 repair_units_upper=.4)


class Engine:
    def __init__(self, target: Path):
        self.target = target
        self.target.mkdir(parents=True, exist_ok=False)
        self.events: list[dict] = []
        self.counts: dict[str, int] = {}
        self.bytes_written = 0
        self.wall_seconds = 0.0
        self.attempts: dict[str, int] = {}

    def emit(self, operation: str, data: bytes, ext: str, parents: dict[str, str], *, metadata: dict | None = None) -> dict:
        t0 = time.perf_counter()
        n = self.attempts.get(operation, 0) + 1
        self.attempts[operation] = n
        file = self.target / f"{operation}_{n}.{ext}"
        # Exclusive create means no silent raw-file overwrite.
        with file.open("xb") as out:
            out.write(data)
        measured = time.perf_counter() - t0
        self.bytes_written += len(data)
        self.wall_seconds += measured
        self.counts[operation] = self.counts.get(operation, 0) + 1
        receipt = {"operation": operation, "attempt": n, "relative_artifact": file.name,
                   "sha256": h(data), "bytes": len(data), "measured_write_seconds": measured,
                   "parent_sha256": parents, "artifact_content_identity": strict_fingerprint("fixture_tenant", "rights_valid",
                                        parents, data, "AIL_V33_LOCAL_STD_LIB"),
                   "measurement_scope": "REAL_LOCAL_FILE_WRITE_ONLY", "metadata": metadata or {}}
        self.events.append(receipt)
        return receipt


def make_voice(text: str, silence: bool) -> bytes:
    """Produce genuine deterministic WAV bytes (not AI speech)."""
    import io
    import struct
    pcm = bytearray()
    for i in range(2400):
        val = 0 if silence else int(2300 * math.sin(2 * math.pi * 340 * i / 8000))
        pcm.extend(struct.pack("<h", val))
    b = io.BytesIO()
    with wave.open(b, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(bytes(pcm))
    return b.getvalue()


def validate_voice(data: bytes) -> bool:
    import io
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            raw = audio.readframes(audio.getnframes())
            return audio.getnframes() == 2400 and any(raw)
    except (wave.Error, EOFError):
        return False


def execute_scenario(arm: str, scenario: dict, root: Path) -> dict:
    start = time.perf_counter()
    engine = Engine(root / arm / scenario["id"])
    outcome = {"task_id": scenario["id"], "arm": arm,
               "scenario_label": "DELIBERATELY_CONSTRUCTED", "final_human_approval": None,
               "customer_cost_usd": None, "model_tokens": None,
               "generator": "PYTHON_STDLIB_TEXT_SVG_WAV_NOT_AI_VIDEO"}
    permissions = scenario["permission"] == "ALLOW" and scenario["provenance"] == "VALID"
    if not permissions:
        d = decide(DecisionInput(task_id=scenario["id"], tenant_id="fixture_tenant",
                                 permission=scenario["permission"], provenance=scenario["provenance"],
                                 irreversible=False, baseline_action="CONTINUE_WITH_SAFETY_CHECK",
                                 stage_id="brief", budget_units=100, experimental_fixture=True))
        outcome.update(status="BLOCKED_UNAUTHORIZED", decision=d, technical_valid=False,
                       stage_counts={}, stage_ops=0, bytes_written=0, check_calls=0,
                       early_check_calls=0, late_check_calls=0, audio_repairs=0, upstream_repairs=0,
                       elapsed_seconds=time.perf_counter() - start, events=[])
        return outcome

    exposure = example_graph().marginal_at_risk("brief")
    if arm == "AIL_V33_FIXTURE_POLICY":
        d = decide(DecisionInput(task_id=scenario["id"], tenant_id="fixture_tenant", permission="ALLOW",
                                 provenance="VALID", irreversible=False,
                                 baseline_action="CONTINUE_WITH_SAFETY_CHECK", stage_id="brief",
                                 evidence=assumptions(scenario["hint"]), budget_units=100,
                                 experimental_fixture=True))
        early = d["decision"] == "OPTIONAL_EARLY_CHECK"
    else:
        early = arm == "B1_COMPETENT_EARLY_CHECK"
        d = {"decision": "FIXED_EARLY_CHECK" if early else "FIXED_LATE_CHECK",
             "reason": "COMPETENT_STATIC_BASELINE", "support": "FIXTURE_ONLY",
             "commercial_effect_established": False}
    checks_early = 0
    checks_late = 0
    repairs_upstream = 0
    repairs_audio = 0
    used_claim = scenario["claim"]
    if early:
        checks_early += 1
        if used_claim != scenario["reference"]:
            used_claim = scenario["reference"]
            repairs_upstream += 1

    def build(claim: str, *, fail_audio: bool = False) -> tuple[dict, dict, dict, bytes]:
        script_data = ("Fictional scene note: " + claim + ".\n").encode()
        script = engine.emit("script", script_data, "txt", {"brief": h(scenario["claim"].encode())})
        art_data = (f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">'
                    f'<rect width="640" height="360" fill="white"/>'
                    f'<text x="20" y="180" font-size="20" fill="black">{escape(claim)}</text></svg>').encode()
        art = engine.emit("art", art_data, "svg", {"script": script["sha256"]})
        voice_data = make_voice(claim, fail_audio)
        voice = engine.emit("voice", voice_data, "wav", {"script": script["sha256"]},
                            metadata={"non_speech_tone": True})
        return script, art, voice, voice_data

    script, art, voice, voice_data = build(used_claim, fail_audio=scenario["defect"] == "audio")
    if not early:
        checks_late += 1
        if used_claim != scenario["reference"]:
            used_claim = scenario["reference"]
            repairs_upstream += 1
            # Correct stage invalidation: dependent script, art AND voice rebuild.
            script, art, voice, voice_data = build(used_claim, fail_audio=False)

    if not validate_voice(voice_data):
        repairs_audio += 1
        voice_data = make_voice(used_claim, False)
        # Local defect repairs voice only; don't regenerate script or art.
        voice = engine.emit("voice", voice_data, "wav", {"script": script["sha256"]},
                            metadata={"repaired_after_pcm_validation": True})

    package_obj = {"task_id": scenario["id"], "script_sha256": script["sha256"],
                   "art_sha256": art["sha256"], "voice_sha256": voice["sha256"],
                   "claim": used_claim, "asset_rights": "CONSTRUCTED_RIGHTS_ASSUMED_ALLOWED"}
    package_raw = json.dumps(package_obj, sort_keys=True, separators=(",", ":")).encode()
    package = engine.emit("package", package_raw, "json",
                          {"art": art["sha256"], "voice": voice["sha256"]})
    technical_valid = used_claim == scenario["reference"] and validate_voice(voice_data)
    outcome.update(status="TECHNICAL_PASS" if technical_valid else "TECHNICAL_FAIL",
                   decision=d, frontier=exposure, technical_valid=technical_valid,
                   stage_counts=engine.counts, stage_ops=sum(engine.counts.values()),
                   bytes_written=engine.bytes_written, check_calls=checks_early + checks_late,
                   early_check_calls=checks_early, late_check_calls=checks_late,
                   audio_repairs=repairs_audio, upstream_repairs=repairs_upstream,
                   package_sha256=package["sha256"], elapsed_seconds=time.perf_counter() - start,
                   events=engine.events)
    return outcome


def run_all(output_root: Path) -> dict:
    output_root.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    rows = [execute_scenario(arm, item, output_root / "artifacts")
            for arm in ARMS for item in SCENARIOS]
    by_arm = {}
    for arm in ARMS:
        items = [r for r in rows if r["arm"] == arm]
        by_arm[arm] = {"total_cases": len(items),
                       "technically_passed": sum(r["technical_valid"] for r in items),
                       "blocked_rights": sum(r["status"] == "BLOCKED_UNAUTHORIZED" for r in items),
                       "stage_ops_executed": sum(r["stage_ops"] for r in items),
                       "bytes_written": sum(r["bytes_written"] for r in items),
                       "early_check_calls": sum(r["early_check_calls"] for r in items),
                       "late_check_calls": sum(r["late_check_calls"] for r in items),
                       "audio_repairs": sum(r["audio_repairs"] for r in items),
                       "upstream_repairs": sum(r["upstream_repairs"] for r in items),
                       "wall_elapsed_seconds": round(sum(r["elapsed_seconds"] for r in items), 6),
                       "independent_approved_count": None, "cost_per_approved_outcome": None,
                       "usd_spend": None, "real_model_tokens": None}
    same_final = all(
        len({r["package_sha256"] for r in rows if r["task_id"] == c["id"] and "package_sha256" in r}) <= 1
        for c in SCENARIOS)
    return {"schema_version": "ail.v33.companion.report.1", "software_version": VERSION,
            "study_kind": "ACTUAL_LOCAL_EXECUTION_ON_CONSTRUCTED_FIXTURES",
            "source_integration": "V32_NOT_AVAILABLE_NOT_PATCHED",
            "license_comparator": "NO_THIRD_PARTY_OSS_EXECUTED",
            "arms": list(ARMS), "scenarios": [{k: v for k, v in c.items() if k != "reference"} for c in SCENARIOS],
            "per_arm": by_arm, "task_rows": [{k: v for k, v in r.items() if k != "events"} for r in rows],
            "events": [dict(event, task_id=r["task_id"], arm=r["arm"]) for r in rows for event in r["events"]],
            "parity_exact_package_sha_across_arms": same_final,
            "hmm_challenger": {"status": "HOLD_NO_SEQUENTIAL_TRAJECTORY_DATA",
                               "trained": False, "reason": "No sufficiently labeled chronological agent trajectories; no deployment"},
            "commercial_gate": "HOLD_NO_CUSTOMER_APPROVAL_COSTS_OR_ACTUAL_OSS_COMPARATOR",
            "technical_coverage": "STRUCTURAL_VALIDITY_ONLY_NOT_CREATIVE_APPROVAL",
            "counterfactual_effect_established": False,
            "elapsed_experiment_wall_seconds": round(time.perf_counter() - start, 6),
            "safety_policy": "MANDATORY_PERMISSION_GATE_BEFORE_EXECUTION",
            "notes": ["All references fictional and author constructed", "All WAV files are tones, not generated human speech",
                      "All SVG files are drawings, not AI-generated video footage",
                      "Stage-op counts are actual Python file-generation operations, not provider calls",
                      "Check probability and cost parameters are constructed heuristics, not calibrated from agent traces",
                      "B1 competent baseline includes early source verification and selective recovery",
                      "No model, inference API, hosted tools, or external OSS optimizer executed",
                      "No independent creative acceptance and no cloud invoices; commercial KPI undefined"]}
