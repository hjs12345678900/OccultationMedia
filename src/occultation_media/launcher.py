"""Dispatch GUI, CLI and isolated jobs without depending on console streams."""
from pathlib import Path
import contextlib
import io
import json
import sys
import traceback


def main():
    args=sys.argv[1:]
    if args and args[0]=='--adv-worker':
        request,result=map(Path,args[1:3])
        try:
            from .decode_adv_worker import main as decode
            old_stdin=sys.stdin
            try:
                sys.stdin=io.StringIO(request.read_text())
                with result.open('w') as output,contextlib.redirect_stdout(output):decode()
            finally:sys.stdin=old_stdin
        except Exception:
            result.write_text(traceback.format_exc());raise SystemExit(1)
    elif args and args[0]=='--run-job':
        job=Path(args[1]);config=json.loads(job.read_text(encoding='utf-8'))
        result=job.with_name('result.json')
        with job.with_name('run.log').open('w',encoding='utf-8',buffering=1) as log:
            with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
                try:
                    from .make_tangra_occultation_media import main as generate
                    print('Reading observation and generating synchronized media…',flush=True)
                    generate(config['argv'])
                    result.write_text(json.dumps({'ok':True}),encoding='utf-8')
                except BaseException as error:
                    traceback.print_exc()
                    result.write_text(json.dumps({'ok':False,'error':str(error)}),encoding='utf-8')
                    raise SystemExit(1)
    elif args and args[0]=='--self-test':
        from .self_test import run
        report=run()
        if len(args)>1:Path(args[1]).write_text(json.dumps(report,indent=2))
        elif sys.stdout:print(json.dumps(report,indent=2))
    elif args and args[0]=='--cli':
        from .make_tangra_occultation_media import main as generate
        generate(args[1:])
    else:
        from .desktop_app import run
        run(smoke=bool(args and args[0]=='--gui-smoke'))
