"""Build and smoke-test an OS-native desktop release; no cross compilation."""
from pathlib import Path
import json
import platform
import shutil
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
from collect_licenses import collect
collect(root)
if platform.system() not in ('Windows','Darwin'):
    raise SystemExit('Run the build on Windows x64 or Intel-compatible macOS Python.')
if platform.system()=='Darwin' and platform.machine()!='x86_64':
    raise SystemExit('Use Intel Python/Rosetta for the macOS release; ADV native library is Intel.')
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root,check=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','OccultationMedia.spec'],cwd=root,check=True)
mac=platform.system()=='Darwin'
exe=root/('dist/OccultationMedia.app/Contents/MacOS/OccultationMedia' if mac else 'dist/OccultationMedia/OccultationMedia.exe')
report=root/'dist/package-self-test.json'
subprocess.run([str(exe),'--self-test',str(report)],check=True)
if not json.loads(report.read_text())['ok']:raise SystemExit('Package self-test failed')
if mac:
    archive=root/'dist/OccultationMedia-macOS-Intel.zip'
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(root/'dist/OccultationMedia.app'),str(archive)],check=True)
else:
    archive=Path(shutil.make_archive(str(root/'dist/OccultationMedia-Windows-x64'),'zip',root/'dist','OccultationMedia'))
print(f'Release: {archive}')
