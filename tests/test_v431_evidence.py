import hashlib,json,os,subprocess,sys,tempfile,threading,time,unittest,urllib.request,urllib.error,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v431.console import EvidenceConsole,range_spec,serve
from ail_v43.engine import task_index,media_probe

class EvidenceV431(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name)
        cls.prompts=ROOT/'data'/'frozen_prompt_first_v01.json'
        cls.src=cls.base/'original';cls.src.mkdir()
        path=cls.src/'media/clip-123456abcdef/generated_0.mp4';path.parent.mkdir(parents=True)
        z=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=128x128:rate=8',
                          '-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(path)],capture_output=True,text=True,timeout=30)
        if z.returncode:raise RuntimeError(z.stderr)
        cls.probe=media_probe(path)
        cls.rec={'records':[{'clip_id':'clip-123456abcdef','task_id':'VID-03-LIBRARY-HANDOFF','status':'COMPLETE',
                  'final_media':'media/clip-123456abcdef/generated_0.mp4','probe':cls.probe,'review':None,'error':None,'model':'LTX-2.5'}],
                 'calls_started':1,'completed_calls':1}
        (cls.src/'generative_receipts_v43.json').write_text(json.dumps(cls.rec))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def new(self,rec=None,generator=None,max_new_calls=3):
        src=self.src
        if rec is not None:
            src=self.base/('source-'+str(time.time_ns()));src.mkdir(); (src/'generative_receipts_v43.json').write_text(json.dumps(rec))
        return EvidenceConsole(src,self.base/('test-'+str(time.time_ns())),self.prompts,max_new_calls,generator)
    def test_single_actual_record_five_not_requested(self):
        s=self.new();tasks=s.tasks_overview()
        self.assertEqual(len(tasks),6)
        self.assertEqual(sum(t['status']=='VIDEO_AVAILABLE' for t in tasks),1)
        self.assertEqual(sum(t['status']=='NOT_REQUESTED' for t in tasks),5)
        self.assertEqual(s.new_calls_started,0)
        self.assertIsNotNone(s.media_for('clip-123456abcdef'))
        self.assertTrue(s.upload.is_file())
        with zipfile.ZipFile(s.upload) as z:
            self.assertIn('GENERATIVE_EVIDENCE_V431.json',z.namelist())
            self.assertNotIn('generated_0.mp4',z.namelist())
    def test_missing_video_becomes_media_missing(self):
        s=self.new(self.rec)
        self.assertEqual(sum(t['status']=='MEDIA_MISSING_OR_CORRUPT' for t in s.tasks_overview()),1)
        self.assertIsNone(s.media_for('clip-123456abcdef'))
    def test_wrong_checksum_is_never_accepted(self):
        source=self.base/('bad-'+str(time.time_ns()));source.mkdir()
        media=source/'media/clip-123456abcdef/generated_0.mp4';media.parent.mkdir(parents=True)
        media.write_bytes(b'not a video'*1000)
        (source/'generative_receipts_v43.json').write_text(json.dumps(self.rec))
        s=EvidenceConsole(source,self.base/('reject-'+str(time.time_ns())),self.prompts)
        self.assertEqual(sum(t['status']=='MEDIA_MISSING_OR_CORRUPT' for t in s.tasks_overview()),1)
    def test_removed_or_modified_after_initial_admission_is_hidden(self):
        s=self.new()
        clip='clip-123456abcdef'
        target=s.media_for(clip)
        self.assertIsNotNone(target)
        target.write_bytes(b'modified')
        self.assertIsNone(s.media_for(clip))
        self.assertEqual(next(x for x in s.tasks_overview() if x['task_id']=='VID-03-LIBRARY-HANDOFF')['status'], 'MEDIA_MISSING_OR_CORRUPT')
        with self.assertRaisesRegex(ValueError,'VIDEO_MISSING_OR_HASH_MISMATCH'):
            s.review({'clip_id':clip,'scores':{},'events':{}})

    def test_range_contract(self):
        self.assertEqual(range_spec(None,100),(0,99,200))
        self.assertEqual(range_spec('bytes=0-2',100),(0,2,206))
        self.assertEqual(range_spec('bytes=90-',100),(90,99,206))
        self.assertEqual(range_spec('bytes=-5',100),(95,99,206))
        self.assertEqual(range_spec('bytes=100-',100)[2],416)
        self.assertEqual(range_spec('bytes=0-1,3-4',100)[2],416)
    def test_real_http_range_head_play_and_health(self):
        s=self.new();srv,url=serve(s,ROOT/'ail_v431/app.js',open_browser=False)
        t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
        try:
            with urllib.request.urlopen(url+'api/state') as r:
                d=json.load(r);self.assertEqual(len(d['tasks']),6)
            with urllib.request.urlopen(url+'api/health') as r:self.assertTrue(json.load(r)['ok'])
            with urllib.request.urlopen(url+'app.js') as r:
                js=r.read().decode();self.assertIn('Not requested',js)
            with urllib.request.urlopen(url) as r:self.assertIn(b'<h1>',r.read())
            req=urllib.request.Request(url+'video/clip-123456abcdef',headers={'Range':'bytes=0-127'})
            with urllib.request.urlopen(req) as r:
                self.assertEqual(r.status,206);self.assertEqual(len(r.read()),128)
                self.assertEqual(r.headers['Accept-Ranges'],'bytes')
            req=urllib.request.Request(url+'video/clip-123456abcdef',method='HEAD')
            with urllib.request.urlopen(req) as r:
                self.assertEqual(r.status,200);self.assertEqual(int(r.headers['Content-Length']),self.probe['bytes'])
            req=urllib.request.Request(url+'video/clip-123456abcdef',headers={'Range':'bytes=999999-'})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
            self.assertEqual(e.exception.code,416)
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url+'video/clip-000000000000')
            self.assertEqual(e.exception.code,404)
        finally:srv.shutdown();srv.server_close();t.join(timeout=5)
    def test_no_implicit_generation_and_explicit_provider_failure(self):
        calls=[]
        def blocked(*a,**k):calls.append(1);raise RuntimeError('GPU_QUOTA_EXHAUSTED')
        s=self.new(generator=blocked,max_new_calls=1)
        self.assertEqual(calls,[])
        task='VID-01-LION-TEMPORAL';cid=s.start(task)
        for _ in range(120):
            r=next(x for x in s.records if x['clip_id']==cid)
            if r['status'] not in ('QUEUED','RUNNING'):break
            time.sleep(.02)
        self.assertEqual(r['status'],'PROVIDER_FAILED')
        self.assertEqual(len(calls),1)
        self.assertIn('GPU_QUOTA_EXHAUSTED',r['error'])
        self.assertEqual(next(x for x in s.tasks_overview() if x['task_id']==task)['status'],'PROVIDER_FAILED_OR_INTERRUPTED')
        with self.assertRaisesRegex(ValueError,'BUDGET'):s.start('VID-02-GLASS-DYNAMICS')
    def test_reject_generation_for_existing_verified_clip(self):
        s=self.new()
        with self.assertRaisesRegex(ValueError,'VIDEO_ALREADY_AVAILABLE'):s.start('VID-03-LIBRARY-HANDOFF')
    def test_review_requires_all_scores(self):
        s=self.new()
        with self.assertRaisesRegex(ValueError,'REVIEW_REQUIRES_ALL_CRITERIA'):
            s.review({'clip_id':'clip-123456abcdef','scores':{},'events':{}})
    def test_valid_review_persists_and_no_double_review(self):
        s=self.new();t=s.tasks['VID-03-LIBRARY-HANDOFF']
        rev={'clip_id':'clip-123456abcdef','scores':dict.fromkeys(('prompt_elements','event_order','subject_motion','identity_continuity','visual_quality','safety_constraints'),2),
             'events':{e:'uncertain' for e in t['events_in_order']},'notes':'Needs direct inspection', 'external_reviewer':False}
        self.assertTrue(s.review(rev)['recorded'])
        self.assertEqual(s.records[0]['review']['reviewer_kind'],'self_reported')
        with self.assertRaisesRegex(ValueError,'REVIEW_ALREADY_PRESENT'):s.review(rev)
    def test_original_files_unmodified(self):
        f=self.src/'generative_receipts_v43.json';old=hashlib.sha256(f.read_bytes()).hexdigest();self.new()
        self.assertEqual(old,hashlib.sha256(f.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()
