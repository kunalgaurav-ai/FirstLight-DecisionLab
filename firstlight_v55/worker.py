"""Restricted child worker. Not a substitute for VM/container security."""
import ast,json,resource,sys
# Memory/process limits are applied before model code is evaluated.
try:
 resource.setrlimit(resource.RLIMIT_CPU,(2,3))
 resource.setrlimit(resource.RLIMIT_AS,(1024*1024*1024 if sys.platform=="darwin" else 512*1024*1024,)*2)
 resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
except (ValueError,OSError):pass
from pathlib import Path
# Parent validates AST; child repeats the validation to prevent bypass.
from importlib.util import spec_from_file_location,module_from_spec
p=Path(__file__).with_name('sandbox.py')
spec=spec_from_file_location('_restricted_validation',str(p));mod=module_from_spec(spec);spec.loader.exec_module(mod)
import builtins
SAFE={k:getattr(builtins,k) for k in ('range','len','min','max','abs','sum','sorted','enumerate','reversed','zip','list','dict','set','tuple','int','float','str','bool','any','all')}
try:
 packet=json.load(sys.stdin)
 code=packet['code'];name=packet['func'];cases=packet['cases']
 assert isinstance(cases,list) and len(cases)<200 and all(isinstance(x,list) and len(x)==2 and isinstance(x[0],list) for x in cases)
 if mod.validate(code,name):raise ValueError('STATIC_REJECT_CHILD')
 env={'__builtins__':SAFE};exec(compile(code,'<candidate>','exec'),env)
 f=env[name];good=0
 for args,expected in cases:
  try:
   actual=f(*args)
   # bool/int should not be deemed interchangeable
   ok=type(actual)==type(expected) and actual==expected
   if isinstance(expected,float) and isinstance(actual,(float,int)):
    ok=abs(float(expected)-float(actual))<1e-9
   if ok:good+=1
  except BaseException:pass
 print(json.dumps({'status':'PASS' if good==len(cases) else 'FAIL','passed':good}))
except BaseException as exc:
 print(json.dumps({'status':'CHILD_ERROR','reason':type(exc).__name__}))
