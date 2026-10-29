"""Bounded, fail-closed full regression runner.

Some inherited dashboard tests launch local web subprocesses. A timed test
runner prevents a stuck inherited fixture from blocking the user's Mac forever.
"""
import argparse,os,signal,subprocess,sys,time
from pathlib import Path

def execute(logfile,timeout_seconds=165):
    if not 30<=timeout_seconds<=600: raise ValueError('INVALID_TIMEOUT')
    logfile=Path(logfile);logfile.parent.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-m','unittest','discover','-s','tests','-q']
    with open(logfile,'wb') as stream:
        kw={'start_new_session':True} if os.name=='posix' else {}
        proc=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,**kw)
        try:
            rc=proc.wait(timeout=timeout_seconds)
            return int(rc)
        except subprocess.TimeoutExpired:
            if os.name=='posix':os.killpg(proc.pid,signal.SIGTERM)
            else:proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name=='posix':os.killpg(proc.pid,signal.SIGKILL)
                else:proc.kill()
                proc.wait()
            stream.write(b'\nFAIL_CLOSED_TEST_SUITE_TIMEOUT_NO_BENCHMARK_EXECUTION\n')
            return 124

def main():
    ap=argparse.ArgumentParser();ap.add_argument('logfile');ap.add_argument('--timeout',type=int,default=165)
    args=ap.parse_args()
    return execute(args.logfile,args.timeout)
if __name__=='__main__':sys.exit(main())
