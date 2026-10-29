"""Expose separately authored precommit counterexamples, not gold tests."""
import ast,json,pathlib,subprocess,sys,time
from firstlight_v55.sandbox import validate


def complexity(code,name):
    try: tree=ast.parse(code)
    except SyntaxError:return {'nodes':0,'recursive_calls':0,'calls':0,'loops':0,'score':10,'signals':['INVALID_AST']}
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
    recursive=sum(isinstance(c.func,ast.Name) and c.func.id==name for c in calls)
    loops=sum(isinstance(n,(ast.For,ast.While,ast.ListComp)) for n in ast.walk(tree))
    # PRIORITY, NOT a calibrated failure probability.
    score=min(10,recursive*2+min(2,loops)+(2 if len(list(ast.walk(tree)))>125 else 0))
    signals=[]
    if recursive>=2:signals.append('MULTIBRANCH_RECURSION_OVERLAPPING_SUBPROBLEMS_POSSIBLE')
    elif recursive:signals.append('RECURSION_PRESENT')
    if loops>=2:signals.append('MULTILOOP')
    return {'nodes':len(list(ast.walk(tree))),'recursive_calls':recursive,'calls':len(calls),'loops':loops,'score':score,'signals':signals}


def single_case(code,name,case,timeout=1.0):
    start=time.perf_counter();error=validate(code,name)
    if error:return {'status':'STATIC_REJECT','reason':error,'elapsed_s':0.0,'case':case,'observed':'AST_REJECT'}
    packet={'code':code,'name':name,'args':case[0],'expected':case[1]}
    try:
        cmd=[sys.executable,'-I','-S',str(pathlib.Path(__file__).with_name('probe_worker.py'))]
        p=subprocess.run(cmd,input=json.dumps(packet),capture_output=True,text=True,timeout=timeout)
        elapsed=time.perf_counter()-start
        if p.returncode!=0:return {'status':'EXECUTION_ERROR','reason':'CHILD_FAILED','elapsed_s':elapsed,'case':case,'observed':'CHILD_EXIT'}
        out=json.loads(p.stdout)
        return {'status':out['status'],'reason':out.get('reason',''), 'elapsed_s':elapsed,'case':case,'observed':out.get('observed','')}
    except subprocess.TimeoutExpired:
        return {'status':'TIMEOUT','reason':'PER_CASE_WALL_TIMEOUT','elapsed_s':time.perf_counter()-start,'case':case,'observed':'TIMEOUT'}
    except Exception as exc:
        return {'status':'EXECUTION_ERROR','reason':type(exc).__name__,'elapsed_s':time.perf_counter()-start,'case':case,'observed':'ERROR'}
