"""Validate desktop form fields and run cancellable independent jobs."""
from datetime import datetime
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import unicodedata
import math
from .platform_runtime import hidden_process_options


def prepare_job(values):
    """Validate form values and expose stable, translatable error identifiers."""
    try:
        return _prepare_job(values)
    except ValueError as error:
        if str(error).startswith('err_'):
            raise
        key='err_date' if 'does not match format' in str(error) or 'unconverted data' in str(error) else 'err_number'
        raise ValueError(key) from error


def _prepare_job(values):
    """Return CLI argv and a new run directory; never overwrite earlier exports."""
    values = dict(values)
    for key in ('date','predicted','uncertainty','exposure','first','margin','stride','low','target','hdu'):
        values[key] = unicodedata.normalize('NFKC', values.get(key,'')).strip()
    for key in ('exposure','margin'):
        if not math.isfinite(float(values[key])):
            raise ValueError('err_number')
    source,csv=Path(values['source']),Path(values['csv'])
    if not values['source'] or not source.exists():raise ValueError('err_source')
    if not values['csv'] or not csv.is_file():raise ValueError('err_csv')
    if not values['output']:raise ValueError('err_output')
    datetime.strptime(values['date'],'%Y-%m-%d')
    if values['predicted']:
        datetime.strptime(values['predicted'],'%H:%M:%S.%f' if '.' in values['predicted'] else '%H:%M:%S')
    if not values['asteroid'].strip() or not values['star'].strip():raise ValueError('err_names')
    if float(values['exposure'])<=0:raise ValueError('err_exposure')
    if values['predicted'] and values['uncertainty']:
        if not math.isfinite(float(values['uncertainty'])) or float(values['uncertainty'])<0:
            raise ValueError('err_exposure')
    if float(values['margin'])<0 or int(values['stride'])<1:raise ValueError('err_stride')
    first=int(values['first'])
    output=Path(values['output'])/datetime.now().strftime('occultation_%Y%m%d_%H%M%S_%f')
    argv=[str(csv.parent),'--csv',str(csv),'--event-date',values['date'],
          '--asteroid',values['asteroid'],'--star',values['star'],
          '--exposure-ms',values['exposure'],'--display-margin-sec',values['margin'],
          '--stride',values['stride'],'--language',values['language'],
          '--output-dir',str(output),'--basename','occultation']
    if values['predicted']:
        argv += ['--predicted-time',values['predicted']]
        if values['uncertainty']:
            argv += ['--prediction-error-sec',values['uncertainty']]
    if source.suffix.lower()=='.lc':argv+=['--lc',str(source)]
    else:argv+=['--source',str(source),'--source-first-frame',str(first),'--ser-byte-order',values['byte_order']]
    for key,flag in [('low','--event-frames'),('target','--target-xy')]:
        if values[key].strip():
            parts=values[key].replace(',',' ').split()
            if len(parts)!=2:raise ValueError('err_pair')
            [int(x) if key=='low' else float(x) for x in parts]
            argv += [flag,*parts]
    if values.get('hdu','').strip():argv+=['--fits-hdu',str(int(values['hdu']))]
    if not values['mp4']:argv+=['--no-mp4']
    output.mkdir(parents=True)
    return argv,output


def start_job(argv,output):
    """Spawn a process isolated from the GUI; job/log/result stay in output."""
    job=output/'job.json';job.write_text(json.dumps({'argv':argv},ensure_ascii=False,indent=2),encoding='utf-8')
    if getattr(sys,'frozen',False):command=[sys.executable,'--run-job',str(job)]
    else:command=[sys.executable,str(Path(__file__).resolve().parents[2]/'launch.py'),'--run-job',str(job)]
    options=hidden_process_options()
    if os.name!='nt':options['start_new_session']=True
    return subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**options)


def cancel_job(process):
    """Terminate the job and child decoders, retaining any partial output/logs."""
    if process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,**hidden_process_options())
    else:os.killpg(process.pid,signal.SIGTERM)


def open_folder(path):
    """Open only the user's local output directory in the system file manager."""
    if os.name=='nt':os.startfile(str(path))
    elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
    else:subprocess.Popen(['xdg-open',str(path)])
