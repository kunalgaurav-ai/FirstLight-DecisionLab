"""Fetch/pin MIT-licensed QuixBugs sources. Never modify an existing checkout."""
from __future__ import annotations
import hashlib,json,os,pathlib,subprocess
TASKS=('gcd','bucketsort','levenshtein','is_valid_parenthesization','rpn_eval','find_in_sorted')
URL='https://github.com/jkoppel/QuixBugs.git'

def sha(data):return hashlib.sha256(data).hexdigest()

def source_checkout(run_dir,source_dir=None):
    if source_dir:
        root=pathlib.Path(source_dir).expanduser().resolve()
        if not root.is_dir():raise ValueError('SOURCE_DIR_NOT_FOUND')
    else:
        # Unique per run: never clobber prior checkout or raw user data.
        root=pathlib.Path(run_dir)/'official_quixbugs_source'
        if root.exists():raise ValueError('SOURCE_ALREADY_EXISTS_NO_OVERWRITE')
        p=subprocess.run(['git','clone','--depth','1','--single-branch',URL,str(root)],capture_output=True,text=True,timeout=100)
        if p.returncode:raise RuntimeError('PUBLIC_REPOSITORY_DOWNLOAD_FAILED: '+p.stderr[-280:])
    l=root/'LICENSE'
    if not l.is_file() or 'Permission is hereby granted' not in l.read_text(errors='replace'):
        raise ValueError('QUIXBUGS_LICENSE_NOT_VERIFIED')
    if (root/'.git').exists():
        p=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,timeout=6)
        commit=p.stdout.strip() if p.returncode==0 else None
    else:commit=None
    sources={}; evidence={}
    for task in TASKS:
        file=root/'python_programs'/f'{task}.py'
        gold=root/'json_testcases'/f'{task}.json'
        if not file.is_file() or not gold.is_file():raise ValueError('OFFICIAL_TASK_FILES_MISSING:'+task)
        if file.stat().st_size>25_000 or gold.stat().st_size>100_000:raise ValueError('TASK_FILE_SIZE_LIMIT')
        program=file.read_text('utf8');cases=[]
        for line in gold.read_text('utf8').splitlines():
            if line.strip():
                obj=json.loads(line)
                if not isinstance(obj,list) or len(obj)!=2 or not isinstance(obj[0],list):raise ValueError('UNEXPECTED_JSON_CASE_FORMAT:'+task)
                cases.append(obj)
        if not cases:raise ValueError('GOLD_CASES_EMPTY:'+task)
        sources[task]={'name':task,'source':program,'final_gold':cases}
        evidence[task]={'program_sha256':sha(file.read_bytes()),'testcases_sha256':sha(gold.read_bytes()),'testcase_count':len(cases)}
    return sources,{'source':'jkoppel/QuixBugs','url':URL,'git_commit':commit,'license_sha256':sha(l.read_bytes()),'tasks':evidence,'gold_not_available_to_controller':True,'source_checkout_path':str(root),'local_preflight_probes_are_separately_authored':True}
