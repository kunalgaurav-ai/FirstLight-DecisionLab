import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from firstlight_v53.matrix import (DEFAULT_MODELS,STRATEGIES,key,score_summary,
  evaluate_strategy,reuse_verified_dataset,discover_dataset_paths,write_csv,wilson)
from firstlight_v53.research import html_page,serve
from firstlight_v53.pack import pack
from firstlight_v5.core import sha

ROW={'id':'simple_python_1','question':[[{'role':'user','content':'Calculate sum of 1 and 2'}]],
     'function':[{'name':'add','parameters':{'type':'object','properties':{'x':{'type':'integer'},'y':{'type':'integer'}},'required':['x','y']}}]}

def call(model,row,strict,corrective=False):
    return {'status':'OK','model':model,'call':{'name':'add','arguments':{'x':1,'y':2}},
            'input_tokens':40,'output_tokens':6,'wall_s':0.2,'parse_status':'PASS_SCHEMA'}

class MatrixTests(unittest.TestCase):
    def test_five_different_named_models(self):
        self.assertGreaterEqual(len(DEFAULT_MODELS),5)
        self.assertGreaterEqual(len({x.split(':')[0] for x in DEFAULT_MODELS}),4)
    def test_three_policies_per_model(self):
        self.assertEqual(STRATEGIES,('SINGLE','GUARDED','FIRSTLIGHT'))
    def test_single_model_correct(self):
        res=evaluate_strategy(ROW,'qwen2.5:1.5b','SINGLE',fn=call)
        self.assertEqual(res['status'],'COMPLETE');self.assertEqual(len(res['calls']),1)
    def test_guarded_uses_full_model(self):
        seen=[]
        def f(m,*a,**k):seen.append(m);return call(m,*a,**k)
        evaluate_strategy(ROW,'qwen2.5:1.5b','GUARDED',fn=f)
        self.assertEqual(seen,['qwen2.5:1.5b'])
    def test_firstlight_cheap_first(self):
        seen=[]
        def f(m,*a,**k):seen.append(m);return call(m,*a,**k)
        a=evaluate_strategy(ROW,'gemma3:1b','FIRSTLIGHT',fn=f)
        self.assertEqual(seen,['qwen2.5:0.5b']);self.assertEqual(a['decision'],'CHEAP_FIRST_ACCEPT')
    def test_escalate_from_failed_schema(self):
        seen=[]
        def f(m,*a,**k):
            seen.append(m)
            d=call(m,*a,**k)
            if m=='qwen2.5:0.5b':d['call']=None
            return d
        a=evaluate_strategy(ROW,'gemma3:1b','FIRSTLIGHT',fn=f)
        self.assertEqual(seen,['qwen2.5:0.5b','gemma3:1b']);self.assertEqual(a['tokens'],92)
    def test_failed_llm_call_no_false_pass(self):
        def f(*a,**k):return {'status':'BLOCKED_MODEL_CALL','wall_s':0.01,'call':None}
        self.assertEqual(evaluate_strategy(ROW,'gemma3:1b','FIRSTLIGHT',fn=f)['status'],'BLOCKED_MODEL')
    def test_no_gold_in_policy_input(self):
        # The policy must not take a gold parameter. It receives only a row and model names.
        import inspect
        self.assertNotIn('gold',inspect.signature(evaluate_strategy).parameters)
    def test_summary_all_policy_names_and_missing_arms(self):
        arms={}
        for m in DEFAULT_MODELS:
            for s in STRATEGIES:
                a=evaluate_strategy(ROW,m,s,fn=call)
                a['diagnostic']={'status':'SCORED_DIAGNOSTIC','pass':True}
                arms[key(m,s)]=a
        z=score_summary([{'id':'x','group':'simple_python','arms':arms}],DEFAULT_MODELS)
        self.assertEqual(len(z['arms']),15)
        self.assertEqual(z['paired_comparisons']['gemma3:1b']['scored_pairs'],1)
        self.assertIsNone(z['arms'][key('gemma3:1b','FIRSTLIGHT')]['usd'])
    def test_wilson_uncertainty(self):
        a=wilson(18,24);self.assertLess(a[0],.75);self.assertGreater(a[1],.75)
    def test_bad_sha_rejects_dataset_cache(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'src';src.mkdir();(src/'a.json').write_text('foo')
            (src/'SOURCE_PROVENANCE.json').write_text(json.dumps({'files':[{'local':'a.json','sha256':'bad'}]*4}))
            self.assertIsNone(reuse_verified_dataset(Path(t)/'dest',[src]))
    def test_good_dataset_cache_sha(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t)/'src';src.mkdir()
            files=[]
            for i in range(4):
                (src/f'{i}.json').write_text('data'+str(i))
                files.append({'local':f'{i}.json','sha256':sha(('data'+str(i)).encode())})
            (src/'SOURCE_PROVENANCE.json').write_text(json.dumps({'files':files}))
            reused=reuse_verified_dataset(Path(t)/'dst',[src])
            self.assertEqual(reused,str(src));self.assertEqual((Path(t)/'dst'/'2.json').read_text(),'data2')
    def test_no_points_when_no_scores(self):
        s=html_page({'state':'BLOCKED','rows':[],'requested_models':DEFAULT_MODELS})
        self.assertIn('Awaiting actual model',s);self.assertNotIn('100×',s)
    def test_real_points_when_complete(self):
        s=html_page({'state':'COMPLETE','rows':[{'id':'x'}],'requested_models':DEFAULT_MODELS,
          'summary':{'arms':{'x':{'model':'gemma3:1b','strategy':'GUARDED','rate':.5,
            'passes':1,'scored':2,'attempted':2,'completed':2,'reported_tokens':100,'summed_call_wall_s':2.0,'calls':2}}}})
        self.assertIn('gemma3:1b',s);self.assertIn('<circle',s)
    def test_zip_contains_reproducible_metadata(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/'matrix_results.json').write_text('{}');(p/'matrix_rows.csv').write_text('header\n')
            out=pack(p)
            import zipfile
            with zipfile.ZipFile(out) as z:
                man=json.loads(z.read('EVIDENCE_MANIFEST.json'))
                self.assertEqual(man['sha256_by_path']['matrix_results.json'],sha(z.read('matrix_results.json')))
    def test_unsafe_published_claims_are_blocked(self):
        self.assertEqual(score_summary([],list(DEFAULT_MODELS))['publication_gate'],
                         'HOLD_NO_OFFICIAL_BFCL_OR_APPROVED_OUTCOME_INVOICES')

if __name__=='__main__':unittest.main()
