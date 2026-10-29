"""Fail-closed wrapper: legacy v3.3 constructed-policy math isn't calibrated deployment."""
from __future__ import annotations
from ail_v33.core import DecisionInput,decide


def decide_v34(req:DecisionInput, *, evidence_receipt=None):
    if req.evidence is not None and req.evidence.evidence_class=='CALIBRATED_EXTERNAL':
        # No calibrated artifact has demonstrated action-conditioned causal uplift.
        # A user-supplied string "CALIBRATED_EXTERNAL" is not provenance.
        out=decide(DecisionInput(task_id=req.task_id,tenant_id=req.tenant_id,permission=req.permission,
                  provenance=req.provenance,irreversible=req.irreversible,baseline_action=req.baseline_action,
                  stage_id=req.stage_id,evidence=None,budget_units=req.budget_units))
        if out['decision'] not in ('BLOCK','HUMAN_GATE','HOLD'):
            out['reason']='EXTERNAL_CALIBRATION_TAG_NOT_VERIFIED_AND_POLICY_VALUE_UNKNOWN'
            out['support']='SHADOW_ONLY'
        return out
    # Construced fixture decisions are allowed only for explicit, unit-tested experiments.
    return decide(req)
