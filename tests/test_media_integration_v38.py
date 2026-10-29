"""TEST-ONLY media integration: fake LLM text + synthetic audio for FFmpeg plumbing.
Not production evidence, not a spoken voice, not AI video generation.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ail_v38 import workflow as w

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
class TestFFmpegMediaPlumbing(unittest.TestCase):
    def test_actual_ffmpeg_encode_decode_and_frame_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td);src=t/'dynamic_testsrc.mp4'
            mk=w.safe_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                 'testsrc2=size=640x360:rate=24','-t','5','-c:v','libx264','-preset','ultrafast',str(src)],50)
            self.assertEqual(mk['exit'],0,mk)
            task=w.CASES[0];content=' '.join(task['facts'])
            def stub_model(*args,**kwargs):
                return content,{'usage':{'prompt_eval_count':10,'eval_count':10},'actual_ollama_inference':False}
            original=w.safe_run
            def stub_say(argv,timeout=180):
                if argv[0]=='say':
                    output=argv[argv.index('-o')+1]
                    return original(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                          'sine=frequency=430:sample_rate=22050','-t','2','-c:a','pcm_s16be',str(output)],50)
                return original(argv,timeout=timeout)
            with patch('ail_v38.workflow.call_model',side_effect=stub_model), patch('ail_v38.workflow.safe_run',side_effect=stub_say):
                result=w.run_pipeline(t,src,'MOCK_TEST_ONLY','http://localhost:0',task,w.ARMS[0],1)
            self.assertEqual(result['status'],'COMPLETE',result)
            self.assertTrue((t/result['video_path']).is_file())
            self.assertTrue((t/result['frame_path']).is_file())
            self.assertTrue(result['technical']['has_audio'])
            self.assertTrue(result['technical']['has_video'])
            self.assertIsNone(result.get('independently_approved'))
            self.assertEqual(result['creative_approval'],'UNKNOWN_PENDING_BLIND_INDEPENDENT_REVIEW')

if __name__=='__main__':unittest.main()
