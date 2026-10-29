"""Exercise actual localhost HTTP review/streaming endpoints using test-only dummy bytes."""
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch
from scripts import launch_v38 as app

class TestWorkingBlindReviewDashboard(unittest.TestCase):
    def test_save_review_and_range_response_without_exposing_arm(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            video=root/'media'/'case'/'arm'/'rendered_video.mp4';video.parent.mkdir(parents=True)
            video.write_bytes(b'ABCDEF') # TEST only, not video-generation evidence
            cards=[{'review_id':'R001','task_id':'case','arm':'SECRET_ARM',
                    'source_facts':['Fact one','Fact two'],'status':'COMPLETE',
                    'video_path':str(video.relative_to(root))}]
            report={'status':'TEST','run_id':'dummy','exec_mode':'test_only',
                    'source_video':{'reason':'TEST','duration_s':1},
                    'aggregate':{'SECRET_ARM':{'attempts':1}},'claims':{'approval':'UNKNOWN'}}
            origin=app.ThreadingHTTPServer;holder={};ready=threading.Event()
            def capture(*args,**kwargs):
                s=origin(*args,**kwargs);holder['server']=s;ready.set();return s
            with patch.object(app,'ThreadingHTTPServer',side_effect=capture):
                t=threading.Thread(target=app.dashboard,args=(root,report,cards),daemon=True)
                t.start();self.assertTrue(ready.wait(4))
                server=holder['server'];url=f'http://127.0.0.1:{server.server_port}'
                try:
                    page=urllib.request.urlopen(url).read().decode()
                    self.assertIn('R001',page)
                    self.assertNotIn('SECRET_ARM',page)
                    data=json.loads(urllib.request.urlopen(url+'/api/results').read())
                    self.assertNotIn('SECRET_ARM',json.dumps(data))
                    r=urllib.request.Request(url+'/'+str(video.relative_to(root)),headers={'Range':'bytes=1-3'})
                    self.assertEqual(urllib.request.urlopen(r).read(),b'BCD')
                    rev={'review_id':'R001','reviewer':'independent_sample','approved':False,
                         'factual':4,'creative':2,'audio':3,'feedback':'Not visually aligned'}
                    r=urllib.request.Request(url+'/api/review',data=json.dumps(rev).encode(),headers={'Content-Type':'application/json'},method='POST')
                    self.assertTrue(json.loads(urllib.request.urlopen(r).read())['saved'])
                    saved=[json.loads(s) for s in (root/'reviews.jsonl').read_text().splitlines()]
                    self.assertEqual(saved[0]['scores']['creative'],2)
                    self.assertTrue(saved[0]['independence_not_verified_automatically'])
                finally:
                    server.shutdown();t.join(timeout=4)
                    self.assertFalse(t.is_alive())

if __name__=='__main__':unittest.main()
