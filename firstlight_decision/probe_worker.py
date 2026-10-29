"""Bounded child for ONE spec-authored counterexample; not a security sandbox."""
import json,resource,sys,builtins
try:
 resource.setrlimit(resource.RLIMIT_CPU,(2,3))
 resource.setrlimit(resource.RLIMIT_AS,(1024*1024*1024 if sys.platform=='darwin' else 512*1024*1024,)*2)
 resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
except (OSError,ValueError):pass
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
src=Path(__file__).parent.parent/'firstlight_v55'/'sandbox.py'
sp=spec_from_file_location('_fl_previous_validator',str(src));m=module_from_spec(sp);sp.loader.exec_module(m)
SAFE={k:getattr(builtins,k) for k in ('range','len','min','max','abs','sum','sorted','enumerate','reversed','zip','list','dict','set','tuple','int','float','str','bool','any','all')}
try:
 packet=json.load(sys.stdin)
 code=packet['code']; name=packet['name']; args=packet['args'];expected=packet['expected']
 if m.validate(code,name):raise ValueError('AST_REJECT')
 env={'__builtins__':SAFE}
 exec(compile(code,'<restricted-public-repair>','exec'),env)
 result=env[name](*args)
 if type(result)==type(expected) and result==expected:ok=True
 elif isinstance(expected,float) and isinstance(result,(float,int)):ok=abs(float(expected)-float(result))<1e-9
 else:ok=False
 print(json.dumps({'status':'PASS' if ok else 'FAIL','observed':repr(result)[:180]}))
except BaseException as exc:
 print(json.dumps({'status':'FAIL','observed':'EXCEPTION:'+type(exc).__name__}))
