"""Regression: v4.1 rejected legitimate thumb.wikimedia.org redirect targets."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request
from ail_v42.visuals import MEDIA_HOSTS,StrictMediaRedirect,fetch_one,prepare_assets,task_assets

class FakeResponse:
 def __init__(self,url,data=b'\xff\xd8\xff'+b'x'*1800,content_type='image/jpeg'):
  self.u=url;self.buffer=io.BytesIO(data);self.headers={'Content-Type':content_type}
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def geturl(self):return self.u
 def read(self,n):return self.buffer.read(n)

class FakeOpener:
 def __init__(self,resp):self.resp=resp
 def open(self,*a,**k):return self.resp

START='https://commons.wikimedia.org/wiki/Special:FilePath/Foo.jpg?width=1024'
THUMB='https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a1/Foo.jpg/1024px-Foo.jpg'
UPLOAD='https://upload.wikimedia.org/wikipedia/commons/a/a1/Foo.jpg'

class TransportTests(unittest.TestCase):
 def asset(self):return {'download_url':START}
 def perform(self,url,content_type='image/jpeg',data=b'\xff\xd8\xff'+b'x'*1800):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'one.jpg'
   with patch('urllib.request.build_opener',return_value=FakeOpener(FakeResponse(url,data,content_type))):
    result=fetch_one(self.asset(),p)
   return result,p.exists()
 def test_thumb_wikimedia_is_trusted_verified_cdn(self):
  result,exists=self.perform(THUMB)
  self.assertTrue(result['downloaded']);self.assertEqual(result['resolved_host'],'thumb.wikimedia.org');self.assertTrue(exists)
 def test_upload_wikimedia_is_also_trusted(self):
  result,exists=self.perform(UPLOAD)
  self.assertTrue(result['downloaded']);self.assertTrue(exists)
 def test_foreign_host_is_rejected_and_partial_removed(self):
  result,exists=self.perform('https://attack.example/Foo.jpg')
  self.assertFalse(result['downloaded']);self.assertFalse(exists)
  self.assertIn('UNEXPECTED_DOWNLOAD_REDIRECT',result['message'])
 def test_host_suffix_spoof_is_rejected(self):
  result,exists=self.perform('https://thumb.wikimedia.org.attacker.example/Foo.jpg')
  self.assertFalse(result['downloaded']);self.assertFalse(exists)
 def test_non_image_response_rejected(self):
  result,exists=self.perform(THUMB,'text/html',b'<html>'+b'x'*2000)
  self.assertFalse(result['downloaded']);self.assertFalse(exists)
 def test_too_large_rejected(self):
  from ail_v42.visuals import MAX_BYTES
  result,exists=self.perform(THUMB,data=b'x'*(MAX_BYTES+1))
  self.assertFalse(result['downloaded']);self.assertFalse(exists)
 def test_initial_off_domain_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'one.jpg'
   with patch('urllib.request.build_opener') as op:
    result=fetch_one({'download_url':'https://unrelated.example/a'},p)
   self.assertFalse(result['downloaded']);op.assert_not_called()
 def test_redirect_does_not_follow_off_domain(self):
  handler=StrictMediaRedirect()
  req=Request(START)
  with self.assertRaisesRegex(ValueError,'UNEXPECTED_DOWNLOAD_REDIRECT'):
   handler.redirect_request(req,None,302,'Found',{},'https://evil.example/a.jpg')
  result=handler.redirect_request(req,None,302,'Found',{},THUMB)
  self.assertEqual(result.full_url,THUMB)
 def test_exact_host_set_not_wildcard(self):
  self.assertEqual(MEDIA_HOSTS,{'commons.wikimedia.org','thumb.wikimedia.org','upload.wikimedia.org'})
 def test_legacy_bug_was_exclusion_of_thumb_host(self):
  from pathlib import Path
  legacy=(Path(__file__).parents[1]/'ail_v40'/'visuals.py').read_text()
  self.assertIn("('upload.wikimedia.org','commons.wikimedia.org')",legacy)
 def test_unverified_or_missing_visuals_not_accepted_as_a_task(self):
  rows=[{'task_id':'task','asset_id':'one','status':'READY_ILLUSTRATIVE_ONLY','inspection':{'sha256':'a'}},
        {'task_id':'task','asset_id':'two','status':'BLOCKED_ASSET_PROVENANCE_OR_IMAGE','inspection':{'sha256':'b'}}]
  self.assertIsNone(task_assets(rows,'task'))

if __name__=='__main__':unittest.main()
