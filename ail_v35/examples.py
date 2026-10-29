"""Constructed deterministic scenarios for invariants only; not customer evidence."""
from __future__ import annotations

def fixture():
    nodes=[
     {'id':'research','parents':[],'marginal_cost':[1,1], 'salvage_fraction':[0,0], 'planned_after_checkpoint':False,'already_avoided_by_incumbent':False,'allowed_to_skip_if_defective':False},
     {'id':'script','parents':['research'],'marginal_cost':[2,2], 'salvage_fraction':[0,0], 'planned_after_checkpoint':True,'already_avoided_by_incumbent':False,'allowed_to_skip_if_defective':True},
     {'id':'voice','parents':['script'],'marginal_cost':[4,4], 'salvage_fraction':[0,0], 'planned_after_checkpoint':True,'already_avoided_by_incumbent':False,'allowed_to_skip_if_defective':True},
     {'id':'visuals','parents':['script'],'marginal_cost':[9,9], 'salvage_fraction':[0,0], 'planned_after_checkpoint':True,'already_avoided_by_incumbent':False,'allowed_to_skip_if_defective':True},
     {'id':'mux','parents':['voice','visuals'],'marginal_cost':[2,2], 'salvage_fraction':[0,0], 'planned_after_checkpoint':True,'already_avoided_by_incumbent':False,'allowed_to_skip_if_defective':True},
     {'id':'distribution','parents':['mux'],'marginal_cost':[7,7], 'salvage_fraction':[0,0], 'planned_after_checkpoint':True,'already_avoided_by_incumbent':True,'allowed_to_skip_if_defective':True},
    ]
    return {'unit':'illustrative_cost_units','evidence_class':'CONSTRUCTED_TEST_ONLY',
            'nodes':nodes,'checkpoints':[{'id':'before_script','affected_ancestors':['research']},
                                      {'id':'before_mux','affected_ancestors':['voice','visuals']}]}

def unsupported_action():
    return {'id':'optional_source_check','defect_probability':[0,1],
            'causal_prevention_effect':[0,1], 'full_check_and_repair_cost':[1,3],
            'false_alarm_disruption_cost':[0,2], 'quality_loss_cost_proxy':[0,2],
            'quality_gate':'UNESTABLISHED'}
