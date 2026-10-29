"""Local Ollama transport: single model residency, counted prompt/response and load times."""
import json,time,urllib.request,urllib.error
from firstlight_v5.core import parse_generation,validate_call,tool_specs,sha
from firstlight_v5.runner import prompt_messages

def safe_attempt(model,row,*,strict,corrective=False,base='http://127.0.0.1:11434'):
    messages=prompt_messages(row,strict=strict,corrective=corrective)
    payload={'model':model,'messages':messages,'stream':False,'keep_alive':0,
             'options':{'temperature':0,'seed':13,'num_predict':256,'num_ctx':2048}}
    t0=time.perf_counter()
    try:
        req=urllib.request.Request(base+'/api/chat',data=json.dumps(payload).encode(),
                                   headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=150) as response:decoded=json.load(response)
        raw=decoded.get('message',{}).get('content') or ''
        if not isinstance(raw,str) or not raw.strip():raise ValueError('EMPTY_MODEL_RESPONSE')
        result={'status':'OK','model':model,'raw':raw,'sha256':sha(raw),
                'input_tokens':decoded.get('prompt_eval_count'),
                'output_tokens':decoded.get('eval_count'),'wall_s':time.perf_counter()-t0,
                'provider_ns':{key:decoded.get(key) for key in ('total_duration','load_duration',
                            'prompt_eval_duration','eval_duration')},
                'parse_status':'UNKNOWN','call':None}
        try:
            call=parse_generation(raw);valid,reason=validate_call(call,tool_specs(row))
            result['parse_status']=reason
            if valid:result['call']={'name':call[0],'arguments':call[1]}
        except (ValueError,SyntaxError,TypeError,RecursionError) as ex:
            result['parse_status']='INVALID_RESPONSE:'+str(ex)[:150]
        return result
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError,ConnectionError,OSError) as ex:
        return {'status':'BLOCKED_MODEL_CALL','model':model,'error':str(ex)[:300],
            'call':None,'wall_s':time.perf_counter()-t0,'input_tokens':None,'output_tokens':None,
            'parse_status':'NOT_EVALUATED'}
