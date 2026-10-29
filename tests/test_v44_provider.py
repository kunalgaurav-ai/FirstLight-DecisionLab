import os,unittest
from unittest.mock import patch
from ail_v44.provider_ltx import generate,ProviderError

class LtxProviderSafety(unittest.TestCase):
 def test_no_implicit_billed_api(self):
  with self.assertRaisesRegex(ProviderError,'REQUIRES_ACK'):generate('hello','/tmp/notrun.mp4','ltx-2-5-fast')
 def test_missing_rate(self):
  with self.assertRaisesRegex(ProviderError,'PRICE_REQUIRED'):generate('hello','/tmp/notrun.mp4','ltx-2-5-fast',ack_billable=True)
 def test_no_env_key(self):
  with patch.dict(os.environ,{'LTXV_API_KEY':''}):
   with self.assertRaisesRegex(ProviderError,'MISSING_LTXV'):generate('hello','/tmp/notrun.mp4','ltx-2-5-fast',ack_billable=True,price_usd_per_sec=.10)
 def test_not_local_video_generation_mock(self):
  with self.assertRaises(ProviderError):generate('hello','/tmp/notrun.mp4','fake-model',ack_billable=True,price_usd_per_sec=.10)
 def test_no_subfive_polling(self):
  with patch.dict(os.environ,{'LTXV_API_KEY':'test_only_dummy'}):
   with self.assertRaisesRegex(ProviderError,'POLL_INTERVAL'):generate('hello','/tmp/notrun.mp4','ltx-2-5-fast',ack_billable=True,price_usd_per_sec=.1,poll_interval=1)
