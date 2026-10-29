"""Tests verify mechanics, not customer-level visual relevance or approval."""
import json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from ail_v40.visuals import load_catalog,inspect_image,prepare_assets,task_assets,sha
from ail_v40.workflow import clip_command,ARMS
ROOT=Path(__file__).resolve().parents[1]

class VisualGateTest(unittest.TestCase):
 def setUp(self):self.cat=load_catalog(ROOT/'data'/'curated_visual_assets_v40.json')
 def test_four_topics_two_each(self):
  self.assertEqual(len(self.cat),8)
  self.assertEqual(len({x['task_id'] for x in self.cat}),4)
  for task in {x['task_id'] for x in self.cat}:
   self.assertEqual(sum(x['task_id']==task for x in self.cat),2)
 def test_all_assets_licensed_cc0_and_not_client_venues(self):
  self.assertTrue(all(x['license']=='CC0_1.0' and x['depicts_actual_client'] is False for x in self.cat))
 def test_no_big_buck_bunny_reuse(self):
  self.assertTrue(all('bbb' not in x['download_url'].lower() for x in self.cat))
 def test_duplicate_license_record_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d)/'cat.json';bad=[dict(x) for x in self.cat];bad[0]['license']='UNKNOWN';tmp.write_text(json.dumps({'assets':bad}))
   with self.assertRaisesRegex(ValueError,'RIGHTS'):load_catalog(tmp)
 def test_duplicate_asset_ids_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d)/'cat.json';bad=[dict(x) for x in self.cat];bad[0]['asset_id']=bad[1]['asset_id'];tmp.write_text(json.dumps({'assets':bad}))
   with self.assertRaisesRegex(ValueError,'EIGHT'):load_catalog(tmp)
 def test_missing_images_are_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=prepare_assets(self.cat,d,fetch=False)
   self.assertEqual(len(r),8)
   self.assertTrue(all(x['status'].startswith('BLOCKED') for x in r))
   self.assertIsNone(task_assets(r,'c01_archive'))
 def test_html_file_rejected_even_if_named_jpg(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'x.jpg';f.write_bytes(b'<html>'*1000)
   self.assertFalse(inspect_image(f)['admitted'])
 def test_external_downloads_not_in_test(self):
  self.assertEqual(len(ARMS),2)
  self.assertNotEqual(ARMS[0],ARMS[1])
 def test_mock_valid_images_do_not_bypass_provenance(self):
  if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):self.skipTest('ffmpeg unavailable')
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/self.cat[0]['filename'];subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=red:s=640x360','-frames:v','1',str(p)],check=True)
   result=prepare_assets(self.cat,r,fetch=False)
   self.assertTrue(result[0]['inspection']['admitted'])
   self.assertFalse(result[0]['inspection']['provenance_sidecar_match'])
   self.assertIsNone(task_assets(result,'c01_archive'))
 def test_actual_ffmpeg_captioned_scene_and_two_distinct_sources(self):
  if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):self.skipTest('ffmpeg unavailable')
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);clips=[]
   for color in ('red','blue'):
    jpg=root/(color+'.jpg')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',f'color={color}:s=640x360','-frames:v','1',str(jpg)],check=True,timeout=20)
    cap=root/(color+'.txt');cap.write_text('Approved subject\nIllustrative imagery')
    out=root/(color+'.mp4');rr=subprocess.run(clip_command(jpg,cap,out,1.25),capture_output=True,text=True,timeout=60)
    self.assertEqual(rr.returncode,0,rr.stderr[-1000:])
    self.assertGreater(out.stat().st_size,1000);clips.append(out)
   self.assertNotEqual(sha(clips[0]),sha(clips[1]))
if __name__=='__main__':unittest.main()

class FullAssemblyTest(unittest.TestCase):
 def test_real_two_scene_mp4_with_controlled_test_audio(self):
  from ail_v40.workflow import create_media
  from ail_v38.workflow import safe_run as actual_run
  from unittest.mock import patch
  if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):self.skipTest('FFmpeg unavailable')
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);run=root;out=run/'media'/'trial'/'B1';out.mkdir(parents=True)
   photos=[]
   for col in ('red','blue'):
    p=root/(col+'.jpg')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',f'color={col}:s=640x360','-frames:v','1',str(p)],check=True,timeout=15)
    photos.append({'local_path':str(p),'asset_id':'photo_'+col,'inspection':{'sha256':sha(p)}})
   def fake_speech_command(args,timeout=180):
    if args[0]=='say':
     path=args[args.index('-o')+1]
     return actual_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','5','-c:a','pcm_s16be',path],timeout=40)
    return actual_run(args,timeout=timeout)
   case={'facts':['The archive opens at ten.','Admission is free on Thursdays.']};events=[]
   with patch('ail_v40.workflow.safe_run',side_effect=fake_speech_command):
    result=create_media(run,out,photos,case,'Controlled synthetic test audio',events)
   self.assertEqual(result['status'],'COMPLETE_TECHNICALLY',result)
   self.assertEqual(len(result['frame_paths']),2)
   self.assertNotEqual(sha(run/result['frame_paths'][0]),sha(run/result['frame_paths'][1]))
   self.assertEqual(sum(e['stage']=='ffmpeg_render_grounded_scene' for e in events),2)
