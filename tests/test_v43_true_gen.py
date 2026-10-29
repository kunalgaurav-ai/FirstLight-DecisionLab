import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ail_v43.engine import task_index,validate_review,decision,action_prompt,write_zip,CRITERIA,file_sha,media_probe
from ail_v43.backend import unwrap_video,generate,GenerationUnavailable
from ail_v43.server import Session
ROOT=Path(__file__).resolve().parents[1]

class PromptFirstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.t=task_index(ROOT/'data'/'frozen_prompt_first_v01.json')
    def review(self,id='VID-03-LIBRARY-HANDOFF',score=2):
        t=self.t[id]
        return {'scores':{k:score for k in CRITERIA},'events':{e:'missing' for e in t.get('events_in_order',[])},
                'reviewer_kind':'self_reported'}
    def test_all_sha_digest(self):self.assertEqual(len(self.t),11)
    def test_original_three_prompt_events(self):
        self.assertEqual(len(self.t['VID-01-LION-TEMPORAL']['events_in_order']),3)
    def test_no_slideshows_accepted_as_video_generation(self):
        doc=json.loads((ROOT/'data'/'frozen_prompt_first_v01.json').read_text())
        self.assertIn('PHOTO_SLIDESHOW',doc['not_allowed_as_video_generation'])
    def test_invalid_hash_fails(self):
        with tempfile.TemporaryDirectory() as d:
            j=json.loads((ROOT/'data'/'frozen_prompt_first_v01.json').read_text());j['tasks'][0]['prompt']+=' hidden edit'
            p=Path(d)/'tampered.json';p.write_text(json.dumps(j))
            with self.assertRaisesRegex(ValueError,'FROZEN_PROMPT_HASH_MISMATCH'):task_index(p)
    def test_review_requires_event_scores(self):
        with self.assertRaisesRegex(ValueError,'REVIEW_REQUIRES_ALL_CRITERIA'):
            validate_review({'scores':{},'events':{}},self.t['VID-03-LIBRARY-HANDOFF'])
    def test_invalid_scores_rejected(self):
        r=self.review();r['scores']['visual_quality']=5
        with self.assertRaisesRegex(ValueError,'INVALID_REVIEW_SCORE'):
            validate_review(r,self.t['VID-03-LIBRARY-HANDOFF'])
    def test_no_review_hold(self):
        self.assertEqual(decision(self.t['VID-03-LIBRARY-HANDOFF'],None)['action'],'HOLD_REVIEW_UNKNOWN')
    def test_pass_stops_regeneration(self):
        r=self.review(score=4);r['events']={x:'present' for x in r['events']}
        self.assertEqual(decision(self.t['VID-03-LIBRARY-HANDOFF'],r)['action'],'STOP_NO_REGEN')
    def test_failed_still_expensive_lion_hold(self):
        self.assertEqual(decision(self.t['VID-01-LION-TEMPORAL'],self.review('VID-01-LION-TEMPORAL'),1)['action'],'HOLD_BUDGET_MULTISHOT')
    def test_lion_multishot_allowed_when_three_calls(self):
        self.assertEqual(decision(self.t['VID-01-LION-TEMPORAL'],self.review('VID-01-LION-TEMPORAL'),3)['action'],'GENERATE_MULTISHOT')
    def test_action_prompts_different(self):
        a=self.t['VID-03-LIBRARY-HANDOFF'];r=self.review()
        self.assertNotEqual(action_prompt(a,r,'B1_COMPETENT_RETRY'),action_prompt(a,r,'AIL_STRUCTURED_REPAIR'))
    def test_budget_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            s=Session(Path(d)/'r',ROOT/'data'/'frozen_prompt_first_v01.json',max_calls=1)
            s.calls_started=1
            with self.assertRaisesRegex(ValueError,'GENERATION_CALL_BUDGET_EXHAUSTED'):s.start('VID-03-LIBRARY-HANDOFF','B1_FIRST')
    def test_no_ail_without_review(self):
        with tempfile.TemporaryDirectory() as d:
            s=Session(Path(d)/'r',ROOT/'data'/'frozen_prompt_first_v01.json')
            with self.assertRaisesRegex(ValueError,'REVIEW_REQUIRED_BEFORE_INTERVENTION'):s.start('VID-03-LIBRARY-HANDOFF','AIL_SELECTIVE')
    def test_video_requires_local_path(self):
        with self.assertRaises(GenerationUnavailable):unwrap_video(['https://not-a-local-video.test/x.mp4'])
    def test_session_zip_has_provenance_not_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            s=Session(Path(d)/'v43_case',ROOT/'data'/'frozen_prompt_first_v01.json')
            with __import__('zipfile').ZipFile(s.upload) as z:
                self.assertIn('generative_receipts_v43.json',z.namelist())
                self.assertNotIn('generated_final.mp4',z.namelist())
    def test_real_backend_requires_exact_contract(self):
        class Client:
            def __init__(self,*a,**kw):pass
            def view_api(self,**kw):return {'named_endpoints':{'/run':{'parameters':[{}]*9}}}
        with self.assertRaisesRegex(GenerationUnavailable,'OFFICIAL_SPACE_SCHEMA_CHANGED'):
            generate('prompt','/tmp/not-written.mp4',client_factory=Client)
    def test_backend_receipt_real_without_fake_video(self):
        with tempfile.TemporaryDirectory() as d:
            video=Path(d)/'provider.mp4';video.write_bytes(b'A'*5000)
            class Client:
                def __init__(self,*a,**kw):pass
                def view_api(self,**kw):return {'named_endpoints':{'/run':{'parameters':[{}]*10}}}
                def predict(self,*args,**kwargs):
                    assert args[0]=='live moving scene';assert kwargs['api_name']=='/run'
                    return (str(video),args[0],42,'48 frames (2s)')
            target=Path(d)/'out.mp4'
            r=generate('live moving scene',target,client_factory=Client,duration=2)
            self.assertEqual(r['generation_mode'],'REAL_REMOTE_TEXT_TO_VIDEO_MODEL')
            self.assertTrue(target.is_file())
    def test_backend_duration_limit(self):
        with self.assertRaisesRegex(ValueError,'DURATION_OUT_OF_RANGE'):generate('anything','none',duration=8)
    def test_ffprobe_real_fixture_required(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'EMPTY_OR_MISSING'):media_probe(Path(d)/'no.mp4')
    def test_verified_generated_video_ffmpeg(self):
        import shutil,subprocess
        if not (shutil.which('ffmpeg') and shutil.which('ffprobe')):self.skipTest('no ffmpeg available')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'actual.mp4'
            cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=160x160:rate=16','-t','2','-c:v','mpeg4',str(p)]
            subprocess.run(cmd,check=True,timeout=40)
            r=media_probe(p)
            self.assertGreater(r['duration_s'],1.9)
            self.assertEqual(r['width'],160)
            self.assertFalse(r['moving_image_semantics_verified'])
    def test_frozen_protocol_immutable_value(self):
        a=self.t['VID-03-LIBRARY-HANDOFF'];self.assertEqual(hashlib.sha256(a['prompt'].encode()).hexdigest(),a['prompt_sha256'])

if __name__=='__main__':unittest.main()
