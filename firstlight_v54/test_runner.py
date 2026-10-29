"""Bounded strict unittest runner that closes orphaned dashboard subprocesses.

Inherited tests can finish with 'Ran N tests / OK' yet retain a non-daemon child.
We require a complete terminal unittest success summary, then close the entire
isolated session after a short grace period. A timeout WITHOUT completed
success summary fails closed. No marketing evidence is derived from tests.
"""
import argparse,os,re,signal,subprocess,sys,time
from pathlib import Path

SUCCESS=re.compile(rb'\nRan\s+(\d+)\s+tests in [^\n]+\n\s*OK\s*\Z')

def completed_test_count(raw):
    match=SUCCESS.search(raw)
    return int(match.group(1)) if match else None


def stop_session(proc):
    if proc.poll() is not None:return
    if os.name=='posix':
        os.killpg(proc.pid,signal.SIGTERM)
    else:proc.terminate()
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name=='posix':os.killpg(proc.pid,signal.SIGKILL)
        else:proc.kill()
        proc.wait(timeout=5)


def execute(logfile,timeout=180,minimum_tests=310):
    if not 30<=timeout<=600 or minimum_tests<1:raise ValueError('TEST_RUNNER_BAD_LIMIT')
    logfile=Path(logfile);logfile.parent.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,'-m','unittest','discover','-s','tests','-q']
    with logfile.open('wb') as stream:
        proc=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT,
                             start_new_session=(os.name=='posix'))
    start=time.monotonic();first_ok=None
    while time.monotonic()-start<timeout:
        status=proc.poll();raw=logfile.read_bytes()
        count=completed_test_count(raw)
        if status is not None:
            if status==0 and count is not None and count>=minimum_tests:
                print(f'COMPLETE REGRESSION SUITE: {count} PASSED (process exited)',flush=True)
                return 0
            print('SUITE_INCOMPLETE_OR_FAILED',status,'completed_test_count',count,flush=True)
            return 1
        if count is not None and count>=minimum_tests:
            if first_ok is None:first_ok=time.monotonic()
            if time.monotonic()-first_ok>=3:
                stop_session(proc)
                print(f'COMPLETE REGRESSION SUITE: {count} PASSED; cleaned lingering inherited test subprocess',flush=True)
                return 0
        time.sleep(.25)
    stop_session(proc)
    with logfile.open('ab') as f:f.write(b'\nTEST_DRIVER_TIMED_OUT_BEFORE_COMPLETE_SUCCESS_SUMMARY\n')
    print('REGRESSION_TEST_TIMEOUT_FAIL_CLOSED',flush=True)
    return 124

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('logfile');ap.add_argument('--timeout',type=int,default=180)
    ap.add_argument('--min-tests',type=int,default=310)
    a=ap.parse_args();raise SystemExit(execute(a.logfile,a.timeout,a.min_tests))
