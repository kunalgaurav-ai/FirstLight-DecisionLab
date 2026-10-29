"""Actual local Ollama calls. No API keys, cloud inference, or invented token counts."""
import json,time,urllib.request
BASE='http://127.0.0.1:11434'

def installed():
    try:
        with urllib.request.urlopen(BASE+'/api/tags',timeout=3) as resp:
            return {m['name'] for m in json.load(resp).get('models',[])}
    except Exception as e:raise RuntimeError('OLLAMA_UNAVAILABLE: '+str(e))

def generate(model,prompt,timeout=100,seed=1707):
    payload=json.dumps({'model':model,'prompt':prompt,'stream':False,'options':{'temperature':0,'seed':seed,'num_predict':768,'num_ctx':3072},'keep_alive':'2m'}).encode()
    t=time.perf_counter()
    try:
        req=urllib.request.Request(BASE+'/api/generate',data=payload,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=timeout) as r:data=json.load(r)
        return {'status':'OK','response':data.get('response',''),'input_tokens':data.get('prompt_eval_count'),
                'output_tokens':data.get('eval_count'),'model_reported_duration_ns':data.get('total_duration'),
                'wall_s':round(time.perf_counter()-t,6),'model':model}
    except Exception as e:
        return {'status':'MODEL_ERROR','error':str(e)[:320],'response':'','input_tokens':None,'output_tokens':None,
                'model_reported_duration_ns':None,'wall_s':round(time.perf_counter()-t,6),'model':model}
