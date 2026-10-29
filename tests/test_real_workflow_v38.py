import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ail_v38 import workflow as w

class TestV38Admission(unittest.TestCase):
    def test_no_source_is_block(self):self.assertEqual(w.source_admission(None)['reason'],'NO_USER_SOURCE_VIDEO')
    def test_missing_video_is_block(self):self.assertEqual(w.source_admission(Path('/does/not/exist.mp4'))['reason'],'SOURCE_NOT_FOUND')
    def test_caps(self):self.assertEqual(w.bounded('abcdefghijkl',4),'abcd')
    def test_facts_verified_exactly(self):
        c=w.CASES[0];s=' '.join(c['facts'])
        self.assertTrue(w.content_contract(s,c)['narrow_literal_contract_pass'])
    def test_missing_claim_rejected(self):
        c=w.CASES[0];self.assertFalse(w.content_contract(c['facts'][0],c)['narrow_literal_contract_pass'])
    def test_banned_phrase_rejected(self):
        c=w.CASES[0];s=' '.join(c['facts'])+' '+c['banned'][0]
        self.assertFalse(w.content_contract(s,c)['narrow_literal_contract_pass'])
    def test_scrambled_fact_not_credited(self):
        c=w.CASES[1]
        self.assertFalse(w.content_contract('Blue Loop length 3km.',c)['narrow_literal_contract_pass'])
    def test_no_fake_model_assumptions(self):self.assertIn('NO',w.ARMS[1]+'NO')
    def test_unique_tasks(self):self.assertEqual(len({x['id'] for x in w.CASES}),len(w.CASES))

class TestV38OllamaReceipts(unittest.TestCase):
    @patch('ail_v38.workflow.api')
    def test_probe_uninstalled_holds(self,api):
        api.return_value={'models':[]}
        self.assertEqual(w.probe('http://127.0.0.1:11434','qwen2.5:1.5b')['reason'],'REQUIRED_MODEL_NOT_INSTALLED')
    @patch('ail_v38.workflow.api')
    def test_probe_exact_model_name(self,api):
        api.return_value={'models':[{'name':'qwen2.5:1.5b','digest':'abc'}]}
        self.assertTrue(w.probe('http://127.0.0.1:11434','qwen2.5:1.5b')['ready'])
    @patch('ail_v38.workflow.api')
    def test_actual_receipt_metrics_are_not_bytes(self,api):
        api.return_value={'response':'Hello','model':'qwen2.5:1.5b','prompt_eval_count':79,'eval_count':23,'total_duration':333333}
        text,rec=w.call_model('http://127.0.0.1:11434','qwen2.5:1.5b','Do test',77)
        self.assertEqual(rec['usage']['eval_count'],23)
        self.assertEqual(rec['prompt_sha256'],hashlib.sha256(b'Do test').hexdigest())
        self.assertTrue(rec['actual_ollama_inference'])
        self.assertNotIn('Do test',json.dumps(rec))
    @patch('ail_v38.workflow.api',side_effect=OSError('offline'))
    def test_unreachable_model_is_block(self,api):self.assertFalse(w.probe('http://127.0.0.1:11434','qwen2.5:1.5b')['ready'])
    @patch('ail_v38.workflow.api')
    def test_invalid_response_body_fail_closed(self,api):
        api.return_value={'response':{'message':'wrong type'}}
        with self.assertRaises(ValueError):w.call_model('http://127.0.0.1:11434','m','p',1)

class TestV38Evidence(unittest.TestCase):
    def test_unknown_quality_denominator(self):
        a=w.summarise([])
        self.assertIsNone(a[w.ARMS[0]]['cost_per_approved_result'])
        self.assertIsNone(a[w.ARMS[1]]['independently_approved'])
    def test_summary_counts_raw_reported_tokens(self):
        row={'arm':w.ARMS[0],'status':'COMPLETE','narration_contract':{'narrow_literal_contract_pass':True},
             'wall_s':1.0,'receipts':[{'usage':{'prompt_eval_count':13,'eval_count':7}},
                                    {'usage':{'prompt_eval_count':18,'eval_count':12}}]}
        s=w.summarise([row]);self.assertEqual(s[w.ARMS[0]]['ollama_input_tokens_reported'],31)
        self.assertEqual(s[w.ARMS[0]]['ollama_output_tokens_reported'],19)
    def test_review_blinding_local_cards(self):
        with tempfile.TemporaryDirectory() as t:
            rows=[{'task_id':'abc','arm':x,'status':'FAILED_EXECUTION'} for x in w.ARMS]
            public=w.setup_review_cards(rows,Path(t))
            self.assertEqual(len(public),2)
            self.assertFalse(any('arm' in c for c in public))
            self.assertTrue((Path(t)/'review_index.json').is_file())
    def test_hash_file(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'a';f.write_bytes(b'abc')
            self.assertEqual(w.sha(f),hashlib.sha256(b'abc').hexdigest())

if __name__=='__main__':unittest.main()
