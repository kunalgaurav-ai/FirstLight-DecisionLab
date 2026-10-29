"""Fail-closed BFCL V4 subset pilot. Diagnostic scorer is NOT the BFCL official evaluator."""
import ast
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_FILES = {
    'simple_python': 'BFCL_v4_simple_python.json',
    'multiple': 'BFCL_v4_multiple.json',
}
ENDPOINT = 'https://raw.githubusercontent.com/ShishirPatil/gorilla/'


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def json_dump(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    tmp.replace(p)


def read_items(path):
    data=Path(path).read_text(encoding='utf8')
    try:
        val = json.loads(data)
        if isinstance(val,list): return val
        if isinstance(val,dict):
            if 'id' in val: return [val]
            return [{'id':k,'ground_truth':v} for k,v in val.items()]
    except json.JSONDecodeError: pass
    return [json.loads(x) for x in data.splitlines() if x.strip()]


def normalized_schema(row):
    if not isinstance(row,dict) or not row.get('id') or not isinstance(row.get('function'),list) or not row['function']:
        raise ValueError('UNSUPPORTED_BFCL_QUESTION_SCHEMA')
    if not isinstance(row.get('question'), list) or not row['question']:
        raise ValueError('UNSUPPORTED_BFCL_QUESTION_MESSAGES')
    return row


def prepare_prompt(row):
    """Golden answer is never supplied to this method, even if a row contains one."""
    row=normalized_schema(row)
    # Official BFCL single-turn tasks wrap messages in a list of turns:
    # "question": [[{"role":"user", "content":"..."}]]
    turns=row['question']
    if len(turns)==1 and isinstance(turns[0],list): turns=turns[0]
    elif any(isinstance(x,list) for x in turns): raise ValueError('MULTITURN_NOT_SUPPORTED_IN_THIS_PILOT')
    msgs=[]
    for item in turns:
        if not isinstance(item,dict) or item.get('role') not in ('user','system','assistant'):
            raise ValueError('UNSUPPORTED_BFCL_MESSAGE')
        content=item.get('content')
        if not isinstance(content,str):
            raise ValueError('UNSUPPORTED_BFCL_CONTENT')
        msgs.append({'role':item['role'],'content':content})
    return {'messages':msgs,'tools':row['function']}


def tool_specs(row):
    names={}
    for item in row['function']:
        if not isinstance(item,dict): raise ValueError('INVALID_TOOL_SCHEMA')
        meta=item.get('function',item)
        name=meta.get('name')
        if not isinstance(name,str) or not name: raise ValueError('INVALID_TOOL_NAME')
        params=meta.get('parameters',{})
        if not isinstance(params,dict): raise ValueError('INVALID_TOOL_ARGUMENT_SCHEMA')
        names[name]=params
    return names


def ast_value(n):
    # No eval(), no arbitrary Python execution.
    try: return ast.literal_eval(n)
    except (ValueError,TypeError,SyntaxError,RecursionError):
        if isinstance(n,ast.Name) and n.id in ('true','false','null'):
            return {'true':True,'false':False,'null':None}[n.id]
        raise ValueError('INVALID_LITERAL')


def parse_call(raw):
    if isinstance(raw,dict):
        n=raw.get('name',raw.get('tool'))
        args=raw.get('arguments',raw.get('parameters',{}))
        if isinstance(args,str):
            try: args=json.loads(args)
            except (ValueError,TypeError): raise ValueError('INVALID_ARGUMENT_JSON')
        if isinstance(n,str) and isinstance(args,dict): return (n,args)
        raise ValueError('INVALID_CALL_OBJECT')
    if not isinstance(raw,str): raise ValueError('INVALID_CALL_TYPE')
    raw=raw.strip().strip('`')
    if raw.startswith('{'):
        try: return parse_call(json.loads(raw))
        except (ValueError,TypeError): raise ValueError('INVALID_CALL_JSON')
    tree=ast.parse(raw,mode='eval').body
    if not isinstance(tree,ast.Call) or tree.args or any(x.arg is None for x in tree.keywords):
        raise ValueError('EXPECTED_KEYWORD_CALL')
    def dotted(expr):
        if isinstance(expr,ast.Name): return expr.id
        if isinstance(expr,ast.Attribute): return dotted(expr.value)+'.'+expr.attr
        raise ValueError('BAD_FUNCTION_NAME')
    return dotted(tree.func),{kw.arg:ast_value(kw.value) for kw in tree.keywords}


def parse_generation(raw):
    """Safe syntax-level extraction; invalid syntax => no call, not a fabricated tool result."""
    if not isinstance(raw,str) or not raw.strip(): raise ValueError('EMPTY_RESPONSE')
    candidate=raw.strip()
    candidate=re.sub(r'^```(?:json|python)?\s*|\s*```$', '', candidate, flags=re.I).strip()
    try:
        ob=json.loads(candidate)
        if isinstance(ob,list) and len(ob)==1: ob=ob[0]
        return parse_call(ob)
    except (ValueError,TypeError):
        return parse_call(candidate)


def validate_call(call,specs):
    try:
        name,args=call
        if name not in specs: return False,'TOOL_NOT_DECLARED'
        p=specs[name]
        properties=p.get('properties',{})
        required=p.get('required',[])
        if not isinstance(properties,dict) or not isinstance(required,list): return False,'BAD_TOOL_SCHEMA'
        if any(x not in args for x in required): return False,'REQUIRED_ARGUMENT_MISSING'
        # Some official BFCL schemas have optional params; reject unsupported extras only when known.
        if any(x not in properties for x in args) and properties: return False,'ARGUMENT_NOT_DECLARED'
        for key,value in args.items():
            typ=properties.get(key,{}).get('type')
            if typ=='integer' and (not isinstance(value,int) or isinstance(value,bool)): return False,'BAD_ARGUMENT_TYPE'
            if typ=='number' and (not isinstance(value,(int,float)) or isinstance(value,bool)): return False,'BAD_ARGUMENT_TYPE'
            if typ=='string' and not isinstance(value,str): return False,'BAD_ARGUMENT_TYPE'
            if typ=='boolean' and not isinstance(value,bool): return False,'BAD_ARGUMENT_TYPE'
            if typ=='array' and not isinstance(value,list): return False,'BAD_ARGUMENT_TYPE'
        return True,'PASS_SCHEMA'
    except (ValueError,AttributeError,KeyError,TypeError): return False,'BAD_TOOL_SCHEMA'


def gold_candidates(goldrow):
    """Conservative: accept explicit list/string calls; ambiguous references are unscored."""
    val=goldrow.get('ground_truth',goldrow.get('possible_answer'))
    if val is None: raise ValueError('GOLD_MISSING')
    if isinstance(val,dict) and ('name' in val or 'tool' in val): val=[val]
    if isinstance(val,str): val=[val]
    if not isinstance(val,list) or not val: raise ValueError('GOLD_UNSUPPORTED')
    candidates=[]
    for entry in val:
        try:
            # An answer may encode a one-call list of accepted choices.
            if isinstance(entry,list) and len(entry)==2 and isinstance(entry[0],str) and isinstance(entry[1],dict):
                candidates.append((entry[0],entry[1]))
            else:
                candidates.append(parse_call(entry))
        except (ValueError,SyntaxError,TypeError): continue
    if not candidates: raise ValueError('GOLD_UNSUPPORTED')
    return candidates


def _match_allowed(value, alternatives):
    """Conservative local alternative matching; not the official BFCL evaluator."""
    if not isinstance(alternatives,list): return False
    for choice in alternatives:
        if choice == value and type(choice) is type(value): return True
        # Official BFCL encodes optional aliases/defaults as an empty string.
        if isinstance(choice,dict) and isinstance(value,dict):
            if _match_reference_args(value,choice): return True
    return False


def _match_reference_args(pred_args,reference_args):
    if not isinstance(pred_args,dict) or not isinstance(reference_args,dict): return False
    if set(pred_args)-set(reference_args): return False
    for k,opts in reference_args.items():
        if not isinstance(opts,list): return False
        if k not in pred_args:
            if '' not in opts: return False
        elif not _match_allowed(pred_args[k],opts):
            return False
    return True


def score_diagnostic(prediction,gold):
    """Strict BFCL-V4-derived local diagnostic, not the official score.

    Official data use ground_truth = [{"function.name": {"arg":[accepted_values]}}].
    Do not silently convert an unsupported gold form into a failure.
    """
    ref=gold.get('ground_truth',gold.get('possible_answer'))
    if not isinstance(ref,list) or not ref:
        return {'status':'NOT_SCORABLE_LOCAL','reason':'GOLD_UNSUPPORTED'}
    if all(isinstance(x,dict) and len(x)==1 and isinstance(next(iter(x.values())),dict) for x in ref):
        if prediction is None: return {'status':'SCORED_DIAGNOSTIC','pass':False}
        name,args=prediction
        return {'status':'SCORED_DIAGNOSTIC', 'pass':any(name in r and _match_reference_args(args,r[name]) for r in ref)}
    try:
        opts=gold_candidates(gold)
    except ValueError as e: return {'status':'NOT_SCORABLE_LOCAL','reason':str(e)}
    if prediction is None:return {'status':'SCORED_DIAGNOSTIC','pass':False}
    return {'status':'SCORED_DIAGNOSTIC','pass':any(prediction==x for x in opts)}


def sample_rows(group_rows,max_items=24,seed='firstlight-v5-precommitted'):
    if max_items<1 or max_items>500: raise ValueError('ITEM_LIMIT_OUT_OF_RANGE')
    # Stratified deterministic sampling; recorded public source and all identifiers.
    groups={g:[] for g in OFFICIAL_FILES}
    for group,rows in group_rows.items():
        if group not in groups: raise ValueError('UNKNOWN_GROUP')
        for row in rows: groups[group].append(normalized_schema(row))
        groups[group].sort(key=lambda r:sha(seed+'|'+r['id']))
    # Half each when available; single group stays eligible in tests.
    active=[g for g in groups if groups[g]]
    if not active: raise ValueError('NO_DATA_ROWS')
    selections=[]
    for idx in range(max_items):
        g=active[idx%len(active)]
        if groups[g]: selections.append((g,groups[g].pop(0)))
        elif all(not groups[x] for x in active): break
    return selections


def summarize(rows):
    policies=['COMPETENT_LLM_GUARDED','FIRSTLIGHT_ADAPTIVE']
    result={}
    for pol in policies:
        records=[r['arms'][pol] for r in rows if pol in r.get('arms',{})]
        sc=[x for x in records if x.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC']
        total=len(records)
        passed=sum(x['diagnostic']['pass'] for x in sc)
        tok=sum((x.get('input_tokens') or 0)+(x.get('output_tokens') or 0) for x in records)
        elapsed=sum(x.get('wall_s',0) for x in records)
        result[pol]={'attempted':total,'diagnostic_scored':len(sc),'diagnostic_passes':passed,
                     'diagnostic_rate':passed/len(sc) if sc else None,
                     'tokens':tok,'summed_wall_s':round(elapsed,3),
                     'all_in_usd':None,'independent_acceptance':None}
    a,b=[result[x] for x in policies]
    # Do not imply safety/economic superiority with any unscored/blocked cases.
    if any(arm.get('status') != 'COMPLETED' for row in rows for arm in row.get('arms',{}).values()):
        gate='HOLD_INCOMPLETE_EXECUTION'
    elif min(a['diagnostic_scored'],b['diagnostic_scored']) < len(rows):
        gate='HOLD_INCOMPLETE_LOCAL_SCORER'
    elif not rows: gate='HOLD_NO_CASES'
    else: gate='HOLD_OFFICIAL_EVALUATION_AND_COST_NOT_VERIFIED'
    # Paired statistics are exploratory on pilot data; no taskwise labels are used for policy selection.
    scored_pairs=[]
    for row in rows:
        arms=row.get('arms',{})
        if not all(k in arms for k in policies): continue
        x,y=[arms[k].get('diagnostic',{}) for k in policies]
        if x.get('status')=='SCORED_DIAGNOSTIC' and y.get('status')=='SCORED_DIAGNOSTIC':
            scored_pairs.append((bool(x['pass']),bool(y['pass'])))
    n=len(scored_pairs)
    fl_only=sum(not base and fl for base,fl in scored_pairs)
    baseline_only=sum(base and not fl for base,fl in scored_pairs)
    # Exact, two-sided McNemar sign test for discordant paired binary outcomes.
    discordant=fl_only+baseline_only
    if discordant:
        k=min(fl_only,baseline_only)
        mc_p=min(1.0,2*sum(math.comb(discordant,j) for j in range(k+1))/2**discordant)
    else: mc_p=1.0 if n else None
    def wilson(success,total):
        if not total:return None
        z=1.96
        p=success/total
        den=1+z*z/total
        center=(p+z*z/(2*total))/den
        half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
        return [round(max(0,center-half),4),round(min(1,center+half),4)]
    paired={'scored_pairs':n,'firstlight_only_passes':fl_only,'baseline_only_passes':baseline_only,
            'exact_mcnemar_two_sided_p':mc_p,
            'firstlight_minus_baseline_pass_rate':sum(int(b)-int(a) for a,b in scored_pairs)/n if n else None,
            'quality_wilson_95':{pol:wilson(result[pol]['diagnostic_passes'],result[pol]['diagnostic_scored']) for pol in policies}}
    return {'arms':result,'commercial_gate':gate,'benchmark_grade':'UNOFFICIAL_BFCL_V4_DIAGNOSTIC_ONLY',
            'matched_cases':len(rows),'paired_uncertainty':paired,
            'quality_source':'PUBLISHED_POSSIBLE_ANSWER_LOCAL_STRICT_ADAPTER'}
