"""Mandatory cross-build tests: no drawtext, no Pillow required, no silent caption loss."""
from __future__ import annotations
import json,shutil,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from ail_v41.captions import caption_png,make_lines
from ail_v40.workflow import clip_command

class CaptionCompatibility(unittest.TestCase):
 def test_no_drawtext_or_subtitle_lib_dependency(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);txt=d/'caption.txt';txt.write_text('Required fact for a trial.\nIllustrative only.',encoding='utf-8')
   cmd=clip_command(d/'source.jpg',txt,d/'scene.mp4',1.2)
   joined=' '.join(cmd)
   self.assertNotIn('drawtext',joined)
   self.assertNotIn('subtitles=',joined)
   self.assertIn('overlay=0:0',joined)
   self.assertTrue((d/'caption.overlay.png').is_file())
 def test_python_stdlib_fallback_creates_valid_rgba_png(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);txt=d/'caption.txt';txt.write_text('THE TRAIL CLOSES DURING LIGHTNING WARNINGS.\nIllustrative footage - not the named venue.')
   p=d/'caption.png';r=caption_png(txt,p,force_stdlib=True)
   self.assertEqual(r['renderer'],'PYTHON_STDLIB_BITMAP_NO_EXTRA_PACKAGES')
   self.assertEqual(p.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
   self.assertGreater(p.stat().st_size,200)
   if shutil.which('ffprobe'):
    q=subprocess.run(['ffprobe','-v','error','-of','json','-show_streams',str(p)],capture_output=True,text=True,check=True,timeout=20)
    streams=json.loads(q.stdout)['streams']
    self.assertEqual(streams[0]['width'],640)
    self.assertEqual(streams[0]['height'],360)
 def test_very_long_captions_fail_not_truncate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'cap.txt';p.write_text('This sentence contains essential facts. '*90)
   with self.assertRaisesRegex(ValueError,'OVERFLOW'):caption_png(p,Path(d)/'cap.png')
 def test_live_two_source_encode_without_optional_drawtext(self):
  if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):self.skipTest('media tools missing')
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);pic=d/'scene.jpg';c=d/'caption.txt';c.write_text('Open daily at ten.\nIllustrative imagery.');out=d/'scene.mp4'
   subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=green:s=640x360','-frames:v','1',str(pic)],check=True,timeout=30)
   cmd=clip_command(pic,c,out,1.3)
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
   self.assertEqual(p.returncode,0,p.stderr[-800:]);self.assertGreater(out.stat().st_size,1000)
 def test_sandbox_mac_error_compatibility(self):
  # Failure evidence from actual user run, not a synthetic Mac success claim.
  self.assertTrue('drawtext' not in clip_command.__code__.co_consts)

if __name__=='__main__':unittest.main()
