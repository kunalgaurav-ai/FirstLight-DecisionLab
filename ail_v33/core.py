"""AIL v3.3 independent, local-only early intervention controller.

This is a deterministic engineering reference implementation. Forecast parameters
are fixture assumptions unless supported by explicitly tagged real calibration.
No customer invoices, learned policy effects or independent approvals are implied.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Mapping, Optional, Sequence

VERSION = "3.3.0-companion"


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    id: str
    parents: tuple[str, ...] = ()
    marginal_units: float = 0.0
    committed: bool = False
    salvageable: bool = False
    reversible: bool = False


class StageGraph:
    def __init__(self, nodes: Sequence[Node]):
        self.nodes = {node.id: node for node in nodes}
        if len(self.nodes) != len(nodes):
            raise PolicyError("duplicate stage ids")
        if any(node.marginal_units < 0 for node in nodes):
            raise PolicyError("negative marginal units")
        for node in nodes:
            if not node.id or node.id in node.parents:
                raise PolicyError("invalid stage self-edge/id")
            for parent in node.parents:
                if parent not in self.nodes:
                    raise PolicyError("missing dependency: " + parent)
        visited: set[str] = set()
        visiting: set[str] = set()
        def visit(identifier: str) -> None:
            if identifier in visiting:
                raise PolicyError("cyclic stage dependencies")
            if identifier in visited:
                return
            visiting.add(identifier)
            for parent in self.nodes[identifier].parents:
                visit(parent)
            visiting.remove(identifier)
            visited.add(identifier)
        for identifier in self.nodes:
            visit(identifier)

    def downstream(self, source: str) -> list[str]:
        if source not in self.nodes:
            raise PolicyError("unknown defect ancestor")
        found = {source}
        while True:
            new_nodes = {n.id for n in self.nodes.values() if n.id not in found and any(p in found for p in n.parents)}
            if not new_nodes:
                break
            found.update(new_nodes)
        return sorted(found - {source})

    def actual_dirty_descendants(self, source: str) -> list[str]:
        """Invalidating a true input change dirties all descendants, even if cached.

        A cache may only reuse an output if its dependency identity remains valid.
        Salvageable means independently proven usable, not an ordinary cached node.
        """
        # Propagate only through truly invalidated parents. A proven salvageable
        # intermediate is a validity boundary: its unchanged descendants survive.
        dirty = {source}
        pending = set(self.nodes) - {source}
        while True:
            gained = {key for key in pending
                      if not self.nodes[key].salvageable
                      and any(parent in dirty for parent in self.nodes[key].parents)}
            if not gained:
                break
            dirty.update(gained)
            pending.difference_update(gained)
        return sorted(dirty - {source})

    def marginal_at_risk(self, source: str) -> dict:
        """Unique FUTURE, unsalvageable, nonreversible descendant work.

        Used for diagnostic decision design, never billed-dollar accounting.
        """
        nodes = [self.nodes[k] for k in self.actual_dirty_descendants(source)]
        eligible = [n for n in nodes if not n.committed and not n.reversible]
        return {"source": source,
                "descendants_unique": [n.id for n in nodes],
                "uncommitted_nonreversible": [n.id for n in eligible],
                "future_exposure_units": round(sum(n.marginal_units for n in eligible), 8),
                "evidence_class": "CONSTRUCTED_STAGE_UNITS_NOT_DOLLARS"}


@dataclass(frozen=True)
class OptionalCheckEstimate:
    prior_defect_lower: float
    prior_defect_upper: float
    sensitivity_lower: float
    false_positive_upper: float
    avoidable_units_lower: float
    test_units_upper: float
    false_alarm_disruption_units_upper: float
    repair_units_upper: float
    evidence_class: str = "CONSTRUCTED_FIXTURE_ASSUMPTIONS"

    def validate(self) -> None:
        for field in ("prior_defect_lower", "prior_defect_upper", "sensitivity_lower", "false_positive_upper"):
            value = getattr(self, field)
            if not 0 <= value <= 1:
                raise PolicyError("probability outside [0,1]: " + field)
        if self.prior_defect_lower > self.prior_defect_upper:
            raise PolicyError("inverted probability bounds")
        for field in ("avoidable_units_lower", "test_units_upper", "false_alarm_disruption_units_upper", "repair_units_upper"):
            if getattr(self, field) < 0:
                raise PolicyError("negative resource estimate: " + field)
        if self.evidence_class not in {"CONSTRUCTED_FIXTURE_ASSUMPTIONS", "CALIBRATED_EXTERNAL"}:
            raise PolicyError("unknown evidence class")

    def conservative_net_value(self) -> float:
        self.validate()
        p = self.prior_defect_lower
        gross = p * self.sensitivity_lower * self.avoidable_units_lower
        risk_false_alarm = (1 - p) * self.false_positive_upper * self.false_alarm_disruption_units_upper
        # Use upper prevalence for cost of repairs, conservatively.
        cost_repair = self.prior_defect_upper * self.repair_units_upper
        return round(gross - self.test_units_upper - risk_false_alarm - cost_repair, 8)


@dataclass(frozen=True)
class DecisionInput:
    task_id: str
    tenant_id: str
    permission: str
    provenance: str
    irreversible: bool
    baseline_action: str
    stage_id: str
    evidence: Optional[OptionalCheckEstimate] = None
    budget_units: Optional[float] = None
    experimental_fixture: bool = False


def decide(req: DecisionInput) -> dict:
    """Fail closed and never auto-select unlicensed/disallowed actions.

    Optional evaluator decision uses fixture assumptions ONLY inside an explicitly
    enabled fixture experiment; never leak constructed priors to production.
    """
    base = {"policy": VERSION, "task_id": req.task_id, "stage_id": req.stage_id,
            "incumbent": req.baseline_action, "allowed_action": req.baseline_action,
            "estimated_incremental_units": None, "evaluator_invoked": False,
            "commercial_effect_established": False}
    if not req.task_id or not req.tenant_id:
        return {**base, "decision": "BLOCK", "reason": "MISSING_IDENTITY", "support": "HOLD"}
    if req.permission != "ALLOW" or req.provenance != "VALID":
        return {**base, "decision": "BLOCK", "reason": "PERMISSION_OR_PROVENANCE_NOT_VALID", "support": "HOLD"}
    if req.irreversible:
        return {**base, "decision": "HUMAN_GATE", "reason": "IRREVERSIBLE_ACTION_NO_AUTHORIZED_APPROVAL", "support": "HOLD"}
    if req.baseline_action not in {"CONTINUE_WITH_SAFETY_CHECK", "MANDATORY_CHECK"}:
        return {**base, "decision": "BLOCK", "reason": "UNSAFE_OR_UNKNOWN_INCUMBENT", "support": "HOLD"}
    if req.budget_units is None or req.budget_units < 0:
        return {**base, "decision": "HOLD", "reason": "BUDGET_UNKNOWN", "support": "HOLD"}
    if req.evidence is None:
        return {**base, "decision": req.baseline_action, "reason": "NO_SUPPORTED_OPTIONAL_CHECK_ESTIMATE", "support": "HOLD"}
    try:
        net = req.evidence.conservative_net_value()
    except PolicyError:
        return {**base, "decision": req.baseline_action, "reason": "BAD_FORECAST_INPUT", "support": "HOLD"}
    if req.evidence.evidence_class == "CONSTRUCTED_FIXTURE_ASSUMPTIONS" and not req.experimental_fixture:
        return {**base, "decision": req.baseline_action, "reason": "CONSTRUCTED_PRIORS_NOT_DEPLOYABLE", "support": "HOLD"}
    if req.evidence.test_units_upper > req.budget_units:
        return {**base, "decision": req.baseline_action, "reason": "CHECK_EXCEEDS_BUDGET", "support": "HOLD"}
    evidence_type = "FIXTURE_ONLY" if req.experimental_fixture else "SUPPORTED_EXTERNAL_ESTIMATE_UNVERIFIED_CAUSALLY"
    if net <= 0:
        return {**base, "decision": req.baseline_action, "reason": "NO_POSITIVE_CONSERVATIVE_VOI", "support": evidence_type,
                "estimated_incremental_units": net}
    return {**base, "decision": "OPTIONAL_EARLY_CHECK", "reason": "POSITIVE_CONSTRUCTED_LCB_VOI" if req.experimental_fixture else "POSITIVE_ESTIMATED_LCB_VOI",
            "support": evidence_type, "estimated_incremental_units": net,
            "evaluator_invoked": False}  # executor must issue and receipt the check


def strict_fingerprint(tenant: str, permission_namespace: str, parents: Mapping[str, str], raw_input: bytes,
                       executor_digest: str) -> str:
    if not all((tenant, permission_namespace, executor_digest)):
        raise PolicyError("cache identity is incomplete")
    if not isinstance(raw_input, bytes):
        raise PolicyError("raw_input must be bytes")
    body = {"tenant": tenant, "permission": permission_namespace,
            "parents": sorted(parents.items()), "bytes_sha256": hashlib.sha256(raw_input).hexdigest(),
            "executor_digest": executor_digest}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def example_graph() -> StageGraph:
    return StageGraph([
        Node("brief"), Node("script", ("brief",), 1.0),
        Node("art", ("script",), 5.0), Node("voice", ("script",), 4.0),
        Node("package", ("art", "voice"), 2.0),
    ])
