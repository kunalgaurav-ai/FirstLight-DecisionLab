"""Bounded static allowlist and resource-limited child execution of generated functions.

This is NOT a hardened security sandbox; only use trusted/public research code.
Never run on untrusted proprietary repositories. No general shell/tool capability.
"""
from __future__ import annotations
import ast,json,math,pathlib,re,subprocess,sys,time
FORBID=(ast.Import,ast.ImportFrom,ast.ClassDef,ast.Global,ast.Nonlocal,ast.With,ast.AsyncWith,ast.AsyncFunctionDef,ast.Await,ast.Yield,ast.YieldFrom,ast.Lambda,ast.Try,ast.Raise,ast.Delete)
SAFE_METHODS={'append','extend','pop','sort','reverse','count','index','get','setdefault','copy'}
DENY_NAMES={'eval','exec','compile','open','input','globals','locals','vars','dir','getattr','setattr','delattr','type','object','super','__builtins__','breakpoint','help','exit','quit'}

def extract(response,name):
    s=response.strip()
    m=re.search(r'```(?:python)?\s*\n([\s\S]*?)```',s,re.I)
    if m:s=m.group(1).strip()
    # Find beginning of requested top-level function when model surrounds it with text.
    m=re.search(r'(?m)^def '+re.escape(name)+r'\s*\(',s)
    if m:s=s[m.start():]
    return s[:18000].strip()+'\n'

def validate(code,name):
    if not code or len(code)>13000:return 'INVALID_CODE_SIZE'
    try:t=ast.parse(code)
    except SyntaxError:return 'INVALID_PYTHON_SYNTAX'
    top=[x for x in t.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
    if len(top)!=1 or top[0].name!=name or any(not isinstance(x,(ast.FunctionDef,ast.Expr)) for x in t.body):return 'INVALID_TOP_LEVEL'
    parents={child:node for node in ast.walk(t) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(t):
        if isinstance(node,FORBID):return 'UNSAFE_SYNTAX_'+node.__class__.__name__
        if isinstance(node,ast.Attribute):
            parent=parents.get(node)
            if not (node.attr in SAFE_METHODS and isinstance(node.value,ast.Name) and not node.value.id.startswith('_') and isinstance(parent,ast.Call) and parent.func is node):
                return 'UNSAFE_ATTRIBUTE'
        if isinstance(node,ast.Name) and (node.id in DENY_NAMES or node.id.startswith('__')):return 'FORBIDDEN_NAME'
        if isinstance(node,ast.Call) and not (
            (isinstance(node.func,ast.Name) and node.func.id not in DENY_NAMES) or
            (isinstance(node.func,ast.Attribute) and node.func.attr in SAFE_METHODS)):
            return 'UNSAFE_CALL'
        if isinstance(node,ast.FunctionDef) and node.name.startswith('__'):return 'FORBIDDEN_DEF'
    return None

# Published QuixBugs JSON cases are RESERVED strictly for final evaluation.
# These precommitted probes are authored from the algorithm specification,
# NEVER drawn from the official JSON testcases during runtime decisions.
PROBES={
'gcd':[[[21,35],7],[[48,18],6],[[0,5],5]],
'bucketsort':[[[[2,0,1,2],4],[0,1,2,2]],[[[],3],[]]],
'levenshtein':[[['same','same'],0],[['a','ab'],1]],
'is_valid_parenthesization':[[['(())'],True],[['(()'],False]],
'rpn_eval':[[[[9.0,3.0,'-']],6.0],[[[10.0,2.0,'/']],5.0]],
'find_in_sorted':[[[[2,4,6,8],7],-1],[[[2,4,6,8],6],2]],
}

def run_cases(code,name,cases,timeout=2.5):
    warning=validate(code,name)
    if warning:return {'status':'STATIC_REJECT','reason':warning,'passed':0,'total':len(cases),'wall_s':0.0}
    script=pathlib.Path(__file__).with_name('worker.py')
    start=time.perf_counter()
    try:
        p=subprocess.run([sys.executable,'-I','-S',str(script)],input=json.dumps({'code':code,'func':name,'cases':cases}),text=True,
                         capture_output=True,timeout=timeout,check=False)
        elapsed=time.perf_counter()-start
        if p.returncode!=0:return {'status':'CHILD_ERROR','reason':p.stderr[-240:], 'passed':0,'total':len(cases),'wall_s':round(elapsed,6)}
        out=json.loads(p.stdout)
        return {'status':out['status'],'reason':out.get('reason',''),'passed':out.get('passed',0),
                'total':len(cases),'wall_s':round(elapsed,6)}
    except subprocess.TimeoutExpired:
        return {'status':'CHILD_TIMEOUT','reason':'LIMITED_EXECUTION_TIMEOUT','passed':0,'total':len(cases),
                'wall_s':round(time.perf_counter()-start,6)}
    except Exception as e:
        return {'status':'CHILD_ERROR','reason':str(e)[:150],'passed':0,'total':len(cases),
                'wall_s':round(time.perf_counter()-start,6)}
