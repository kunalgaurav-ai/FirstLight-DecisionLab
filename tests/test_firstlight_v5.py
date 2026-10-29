import json
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock
from firstlight_v5 import core
from firstlight_v5 import runner
from firstlight_v5 import package
from firstlight_v5 import dashboard


def fixture_row(n='simple_python_2'):
    return {'id':n,'question':[{'role':'user','content':'Compute the sum of two numbers 2 and 3.'}],
            'function':[{'name':'calc','parameters':{'type':'object','required':['a','b'],
                        'properties':{'a':{'type':'integer'},'b':{'type':'integer'}}}}]}


class CoreTests(unittest.TestCase):
    def test_ast_parse_is_safe(self):
        self.assertEqual(core.parse_call('calc(a=2, b=3)'),('calc',{'a':2,'b':3}))
        with self.assertRaises(ValueError): core.parse_call('__import__("os").system("echo pwned")')
    def test_never_put_gold_in_prompt(self):
        r=fixture_row();r['ground_truth']=['SECRET_NEVER_IN_PROMPT']
        self.assertNotIn('SECRET_NEVER_IN_PROMPT',json.dumps(core.prepare_prompt(r)))
        self.assertNotIn('SECRET_NEVER_IN_PROMPT',json.dumps(runner.prompt_messages(r)))
    def test_schema(self):
        specs=core.tool_specs(fixture_row())
        self.assertEqual(core.validate_call(('calc',{'a':2,'b':3}),specs),(True,'PASS_SCHEMA'))
        self.assertFalse(core.validate_call(('calc',{'a':'two','b':3}),specs)[0])
    def test_scorer_does_not_give_unscorable_pass(self):
        self.assertEqual(core.score_diagnostic(('calc',{'a':2,'b':3}),{'id':'x','ground_truth': ['calc(a=2,b=3)']})['pass'],True)
        self.assertEqual(core.score_diagnostic(('calc',{'a':2,'b':4}),{'id':'x','ground_truth': ['calc(a=2,b=3)']})['pass'],False)
        self.assertEqual(core.score_diagnostic(('calc',{'a':2,'b':3}),{'id':'x','ground_truth':[{'unknown':True}]})['status'],'NOT_SCORABLE_LOCAL')
    def test_unknown_guard(self):
        with self.assertRaises(ValueError):core.sample_rows({},0)
        with self.assertRaises(ValueError):core.prepare_prompt({'id':'x','question':'bad','function':[]})
    def test_sampler_deterministic(self):
        rows={'simple_python':[fixture_row(str(i)) for i in range(7)],'multiple':[fixture_row('m'+str(i)) for i in range(7)]}
        self.assertEqual([r['id'] for g,r in core.sample_rows(rows,6)], [r['id'] for g,r in core.sample_rows(rows,6)])
        self.assertEqual(len(core.sample_rows(rows,6)),6)
    def test_partial_claim_gate(self):
        summ=core.summarize([{'arms':{'COMPETENT_LLM_GUARDED':{'diagnostic':{'status':'NOT_SCORABLE_LOCAL'}},'FIRSTLIGHT_ADAPTIVE':{'diagnostic':{'status':'NOT_SCORABLE_LOCAL'}}}}])
        self.assertTrue(summ['commercial_gate'].startswith('HOLD'))


class IntegrationTests(unittest.TestCase):
    def test_dataset_hash_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); (p/'file.json').write_text('BAD')
            core.json_dump(p/'SOURCE_PROVENANCE.json',{'files':[{'local':'file.json','sha256':'0'*64}]})
            with self.assertRaises(ValueError):runner.fetch_official(p)
    def test_branch_real_choice_codepaths(self):
        row=fixture_row()
        outputs=[{'status':'OK','raw':'bad','input_tokens':10,'output_tokens':5,'wall_s':0.1,'model':'qwen2.5:0.5b'},
                 {'status':'OK','raw':'{"name":"calc","arguments":{"a":2,"b":3}}','input_tokens':20,'output_tokens':12,'wall_s':0.2,'model':'qwen2.5:1.5b'}]
        with mock.patch.object(runner,'call_ollama',side_effect=outputs):
            b=runner.branch(row,'qwen2.5:0.5b','qwen2.5:1.5b',True)
        self.assertEqual(len(b['calls']),2)
        self.assertEqual(b['decision'],'ESCALATE_AFTER_SCHEMA_FAILURE')
        self.assertEqual(b['input_tokens']+b['output_tokens'],47)
    def test_pack_and_real_http(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)
            core.json_dump(run/'benchmark_results.json',{'state':'BLOCKED','results':[],'blocking_error':'NO_API'})
            z=package.pack(run)
            with zipfile.ZipFile(z) as f:
                manifest=json.loads(f.read('EVIDENCE_MANIFEST.json'))
                for n,dig in manifest['sha256_by_path'].items():self.assertEqual(core.sha(f.read(n)),dig)
            server=dashboard.ThreadingHTTPServer(('127.0.0.1',0),dashboard.Handler);server.run_path=td
            th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
            url=f'http://127.0.0.1:{server.server_address[1]}'
            try:
                with urllib.request.urlopen(url+'/api/state',timeout=3) as f:
                    obj=json.load(f)
                self.assertEqual(obj['brand'],'First Light')
                self.assertEqual(obj['benchmark']['state'],'BLOCKED')
                for uri in ('/','/app.js','/style.css','/download/benchmark.csv'):
                    with urllib.request.urlopen(url+uri,timeout=3) as f:self.assertEqual(f.status,200)
            finally:server.shutdown();server.server_close()
    def test_offline_blocked_gives_json_not_fake_score(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(runner,'fetch_official',side_effect=RuntimeError('DNS_DOWN')):
                runner.main(['--run',td,'--limit','2'])
            st=json.loads((Path(td)/'benchmark_results.json').read_text())
            self.assertEqual(st['state'],'BLOCKED')
            self.assertEqual(st['results'],[])
            self.assertIsNone(st['summary'])

if __name__=='__main__':unittest.main()

class OfficialShapeTests(unittest.TestCase):
    def test_actual_official_question_nested_turn(self):
        x=fixture_row();x['question']=[[{'role':'user','content':'Compute the sum of two numbers 2 and 3.'}]]
        self.assertEqual(len(core.prepare_prompt(x)['messages']),1)
    def test_actual_official_gold_aliases(self):
        g={'id':'simple_python_0','ground_truth':[{'calculate_triangle_area':{'base':[10],'height':[5],'unit':['units','']}}]}
        self.assertTrue(core.score_diagnostic(('calculate_triangle_area',{'base':10,'height':5}),g)['pass'])
        self.assertTrue(core.score_diagnostic(('calculate_triangle_area',{'base':10,'height':5,'unit':'units'}),g)['pass'])
        self.assertFalse(core.score_diagnostic(('calculate_triangle_area',{'base':10,'height':4}),g)['pass'])
        self.assertFalse(core.score_diagnostic(('calculate_triangle_area',{'base':10,'height':5,'extra':1}),g)['pass'])
    def test_actual_multiple_choice(self):
        g={'id':'multiple_0','ground_truth':[{'triangle_properties.get': {'side1':[5],'side2':[4],'side3':[3],'get_area':['',True]}}]}
        self.assertTrue(core.score_diagnostic(('triangle_properties.get',{'side1':5,'side2':4,'side3':3}),g)['pass'])
        self.assertFalse(core.score_diagnostic(('triangle_properties.get',{'side1':5,'side2':4,'side3':2}),g)['pass'])

class PairedStatsTests(unittest.TestCase):
    def test_paired_mcnemar(self):
        rows=[]
        for a,b in [(True,True),(False,True),(False,True),(True,False)]:
            rows.append({'arms':{
                'COMPETENT_LLM_GUARDED':{'status':'COMPLETED','diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':a}},
                'FIRSTLIGHT_ADAPTIVE':{'status':'COMPLETED','diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':b}}}})
        s=core.summarize(rows)
        self.assertEqual(s['paired_uncertainty']['firstlight_only_passes'],2)
        self.assertEqual(s['paired_uncertainty']['baseline_only_passes'],1)
        self.assertEqual(s['paired_uncertainty']['exact_mcnemar_two_sided_p'],1)
        self.assertEqual(s['commercial_gate'],'HOLD_OFFICIAL_EVALUATION_AND_COST_NOT_VERIFIED')
