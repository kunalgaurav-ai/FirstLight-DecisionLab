"""Optional maintainer QA; Playwright needed, not required for Mac launcher.

Controlled FFmpeg test clip is NOT generative-video model output.
"""
import json,sys,tempfile,threading,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ail_v44.workbench import init_run,suite,admit
from ail_v44.server import create_server
with tempfile.TemporaryDirectory() as t:
 root=Path(t);run=init_run(root/'run',ROOT/'data/workflow_suite_v44.json')
 clip=root/'controlled_not_model_generated.mp4'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=256x256:rate=12','-t','7','-c:v','mpeg4',str(clip)],check=True,timeout=60)
 rec=admit(run,suite(ROOT/'data/workflow_suite_v44.json'),'VID-03-LIBRARY-HANDOFF','VID-03-LIBRARY-HANDOFF-S01',clip,'CONTROLLED_FFMPEG_TEST_NOT_T2V','NONAI_TEST_PATTERN','AUTHORIZED_NONCONFIDENTIAL_TEST')
 srv=create_server(run,ROOT/'data/workflow_suite_v44.json',0);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
   page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   from ail_v44.server import PAGE,JS
   from ail_v44.workbench import get
   state=get(run)
   for x in state['artifacts']:x['available']=True
   mock={'plan':suite(ROOT/'data/workflow_suite_v44.json'),'state':state,'categories':list(__import__('ail_v44.workbench',fromlist=['CATEGORIES']).CATEGORIES)}
   page.set_content(PAGE.replace('<script src="/app.js"></script>',''))
   page.evaluate('window.fetch = async () => ({ok:true,json:async()=>JSON.parse(window.__AIL_QA_STATE)})')
   page.evaluate('(s)=>window.__AIL_QA_STATE=s',json.dumps(mock))
   page.add_script_tag(content=JS)
   page.wait_for_function("document.querySelectorAll('#videos section').length === 6",timeout=15000)
   page.wait_for_function("document.querySelectorAll('video').length === 1",timeout=15000)
   d={'visible_campaign_cards':page.locator('#videos section').count(),'unrequested_shot_notices':page.get_by_text('NOT GENERATED/IMPORTED',exact=False).count(),'video_players':page.locator('video').count(),'clip_duration':'NOT_TESTED_OFFLINE_BROWSER_MEDIA','page_errors':errors,'note':'Controlled FFmpeg generated test pattern, not a model-generated video'}
   page.screenshot(path='/mnt/data/ail_v44_build/v44_browser_qa.png',full_page=True)
   print(json.dumps(d,indent=2))
   assert d['visible_campaign_cards']==6 and d['unrequested_shot_notices']==18 and d['video_players']==1 and not errors
   browser.close()
 finally:srv.shutdown();srv.server_close();thread.join(5)
