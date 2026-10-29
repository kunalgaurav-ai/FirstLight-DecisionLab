import unittest
from dataclasses import replace
from ail_v33.core import (Node, StageGraph, PolicyError, OptionalCheckEstimate, DecisionInput,
                          decide, example_graph, strict_fingerprint)


def valid_req(**kwargs):
    d = dict(task_id="test", tenant_id="tenantA", permission="ALLOW", provenance="VALID",
             irreversible=False, baseline_action="CONTINUE_WITH_SAFETY_CHECK",
             stage_id="script", budget_units=10, experimental_fixture=True,
             evidence=OptionalCheckEstimate(.5,.6,.95,.01,12,.15,.2,.4))
    d.update(kwargs)
    return DecisionInput(**d)


class GraphTests(unittest.TestCase):
    def test_unique_shared_descendant(self):
        g = StageGraph([Node("r"),Node("a",("r",),3),Node("b",("r",),5),Node("joint",("a","b"),9)])
        self.assertEqual(g.marginal_at_risk("r")["future_exposure_units"],17)
        self.assertEqual(len(g.downstream("r")),3)
    def test_reject_cycle(self):
        with self.assertRaises(PolicyError): StageGraph([Node("a",("b",)),Node("b",("a",))])
    def test_reject_missing_parent(self):
        with self.assertRaises(PolicyError): StageGraph([Node("a",("gone",))])
    def test_reject_duplicate(self):
        with self.assertRaises(PolicyError): StageGraph([Node("a"), Node("a")])
    def test_reject_negative(self):
        with self.assertRaises(PolicyError): StageGraph([Node("a",marginal_units=-1)])
    def test_committed_is_not_future_savings(self):
        g=StageGraph([Node("r"),Node("a",("r",),10,committed=True),Node("b",("a",),3)])
        self.assertEqual(g.marginal_at_risk("r")["future_exposure_units"],3)
    def test_salvageable_excluded(self):
        g=StageGraph([Node("r"),Node("a",("r",),10,salvageable=True),Node("b",("a",),3)])
        self.assertEqual(g.marginal_at_risk("r")["future_exposure_units"],0)
    def test_reversible_excluded(self):
        g=StageGraph([Node("r"),Node("a",("r",),10,reversible=True)])
        self.assertEqual(g.marginal_at_risk("r")["future_exposure_units"],0)
    def test_default_graph(self):
        self.assertEqual(example_graph().marginal_at_risk("brief")["future_exposure_units"],12)

class ControllerTests(unittest.TestCase):
    def test_positive_fixture_check(self):
        x=decide(valid_req())
        self.assertEqual(x["decision"],"OPTIONAL_EARLY_CHECK")
        self.assertEqual(x["support"],"FIXTURE_ONLY")
        self.assertFalse(x["evaluator_invoked"])
    def test_negative_voi_no_optional_call(self):
        low=OptionalCheckEstimate(.005,.03,.95,.01,12,.15,.2,.4)
        x=decide(valid_req(evidence=low))
        self.assertEqual(x["decision"],"CONTINUE_WITH_SAFETY_CHECK")
        self.assertFalse(x["evaluator_invoked"])
    def test_denied_permission(self):
        self.assertEqual(decide(valid_req(permission="DENY"))["decision"],"BLOCK")
    def test_unknown_permission(self):
        self.assertEqual(decide(valid_req(permission="UNKNOWN"))["decision"],"BLOCK")
    def test_unknown_provenance(self):
        self.assertEqual(decide(valid_req(provenance="UNKNOWN"))["decision"],"BLOCK")
    def test_irreversible_requires_human(self):
        self.assertEqual(decide(valid_req(irreversible=True))["decision"],"HUMAN_GATE")
    def test_unknown_budget(self):
        self.assertEqual(decide(valid_req(budget_units=None))["decision"],"HOLD")
    def test_insufficient_budget(self):
        self.assertEqual(decide(valid_req(budget_units=.01))["reason"],"CHECK_EXCEEDS_BUDGET")
    def test_unsafe_incumbent(self):
        self.assertEqual(decide(valid_req(baseline_action="SKIP_ALL_VALIDATIONS"))["decision"],"BLOCK")
    def test_missing_evidence(self):
        self.assertEqual(decide(valid_req(evidence=None))["support"],"HOLD")
    def test_constructed_prior_production_hold(self):
        x=decide(valid_req(experimental_fixture=False))
        self.assertEqual(x["reason"],"CONSTRUCTED_PRIORS_NOT_DEPLOYABLE")
        self.assertNotEqual(x["decision"],"OPTIONAL_EARLY_CHECK")
    def test_inverted_bounds_rejected(self):
        e=OptionalCheckEstimate(.8,.2,.95,.1,12,.15,.1,.2)
        self.assertEqual(decide(valid_req(evidence=e))["reason"],"BAD_FORECAST_INPUT")
    def test_invalid_probability_rejected(self):
        e=OptionalCheckEstimate(-1,.4,.95,.1,12,.15,.1,.2)
        self.assertEqual(decide(valid_req(evidence=e))["reason"],"BAD_FORECAST_INPUT")
    def test_early_decision_respects_nonnegative_units(self):
        e=OptionalCheckEstimate(.5,.6,.95,.1,-1,.15,.1,.2)
        self.assertEqual(decide(valid_req(evidence=e))["reason"],"BAD_FORECAST_INPUT")
    def test_cross_tenant_cache_different(self):
        a=strict_fingerprint("A","right",{"p":"sha"},b"hello","rev")
        b=strict_fingerprint("B","right",{"p":"sha"},b"hello","rev")
        self.assertNotEqual(a,b)
    def test_cache_requires_byte_identity(self):
        a=strict_fingerprint("A","right",{"p":"sha"},b"hello","rev")
        b=strict_fingerprint("A","right",{"p":"sha"},b"hellO","rev")
        self.assertNotEqual(a,b)
    def test_cache_requires_version_identity(self):
        a=strict_fingerprint("A","right",{"p":"sha"},b"hello","rev1")
        b=strict_fingerprint("A","right",{"p":"sha"},b"hello","rev2")
        self.assertNotEqual(a,b)
    def test_cache_requires_parent_identity(self):
        a=strict_fingerprint("A","right",{"p":"shaA"},b"hello","rev")
        b=strict_fingerprint("A","right",{"p":"shaB"},b"hello","rev")
        self.assertNotEqual(a,b)
    def test_cache_requires_permission_namespace(self):
        a=strict_fingerprint("A","rightsA",{},b"hello","rev")
        b=strict_fingerprint("A","rightsB",{},b"hello","rev")
        self.assertNotEqual(a,b)

if __name__=='__main__': unittest.main()
