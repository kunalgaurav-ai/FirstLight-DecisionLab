import json,threading,unittest,urllib.error,urllib.request,tempfile
from pathlib import Path
from ail_v44.workbench import init_run
from ail_v44.server import create_server,JS
ROOT=Path(__file__).resolve().parents[1]

class HttpContract(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.run=init_run(Path(self.temp.name)/'run',ROOT/'data/workflow_suite_v44.json')
  self.server=create_server(self.run,ROOT/'data/workflow_suite_v44.json',0)
  t=threading.Thread(target=self.server.serve_forever,daemon=True);t.start()
  self.addCleanup(self.server.shutdown);self.addCleanup(self.server.server_close)
  self.base='http://127.0.0.1:'+str(self.server.server_port)
 def test_root_serves_real_markup(self):
  with urllib.request.urlopen(self.base+'/',timeout=3) as r:
   s=r.read().decode();self.assertIn('Agent Intelligence Lab v4.4',s);self.assertIn('/app.js',s)
 def test_script_is_real(self):
  with urllib.request.urlopen(self.base+'/app.js',timeout=3) as r:self.assertIn('function load()',r.read().decode())
 def test_actual_state_and_counts(self):
  with urllib.request.urlopen(self.base+'/api/state',timeout=3) as r:d=json.load(r)
  self.assertEqual(len(d['plan']['tasks']),11);self.assertEqual(len(d['state']['artifacts']),0)
  self.assertEqual(sum(len(x.get('shots',[])) for x in d['plan']['tasks']),19)
 def test_no_faux_player_for_missing(self):
  with urllib.request.urlopen(self.base+'/api/state',timeout=3) as r:d=json.load(r)
  self.assertEqual(sum(1 for a in d['state']['artifacts'] if a.get('available')),0)
 def test_unknown_media_fails(self):
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(self.base+'/media/aaaabbbbcccc',timeout=3)
  self.assertEqual(e.exception.code,404)
 def test_inert_savings_not_reported(self):
  with urllib.request.urlopen(self.base+'/api/state',timeout=3) as r:d=json.load(r)
  self.assertEqual(d['state']['comparison_status'],'NOT_ESTABLISHED_NO_MATCHED_INDEPENDENT_OUTCOMES')
 def test_unreviewed_assembly_rejected(self):
  data=json.dumps({'task_id':'VID-03-LIBRARY-HANDOFF'}).encode()
  req=urllib.request.Request(self.base+'/api/assemble',data=data,headers={'Content-Type':'application/json'},method='POST')
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req,timeout=3)
  self.assertEqual(e.exception.code,400)
