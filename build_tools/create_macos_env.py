"""Create a local Intel-only venv from a python.org universal2 interpreter."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
env=root/'.venv-build'
subprocess.run([sys.executable,'-m','venv','--copies',str(env)],check=True)
for path in (env/'bin').glob('python*'):
    if path.is_symlink() or not path.is_file():continue
    info=subprocess.run(['lipo','-archs',str(path)],capture_output=True,text=True)
    if info.returncode:continue
    if 'x86_64' not in info.stdout:raise SystemExit('Use a python.org universal2 or Intel Python installation.')
    if 'arm64' in info.stdout:
        thin=path.with_name(path.name+'.thin')
        subprocess.run(['lipo',str(path),'-thin','x86_64','-output',str(thin)],check=True)
        thin.replace(path)
python=env/'bin/python'
subprocess.run([str(python),'-m','pip','install','-e',str(root)+'[build]'],check=True)
subprocess.run([str(python),str(root/'build_tools/build.py')],cwd=root,check=True)
