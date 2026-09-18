"""Build Windows artifacts without launching or testing the application."""
from pathlib import Path
import sys
import subprocess
import shutil
import json
import hashlib
import platform
import tomllib
from importlib import metadata
sys.path.insert(0,str(Path(__file__).parent/'build_tools'))
from collect_licenses import collect
root=Path(__file__).resolve().parent
collect(root)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','OccultationMedia.spec'],cwd=root,check=True)
version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
package=root/'dist/OccultationMedia'
(package/'使用说明-README.txt').write_text('OccultationMedia '+version+' — Windows x64\n\n解压整个文件夹，然后双击 OccultationMedia.exe。请保留 _internal 文件夹。\nExtract the complete folder, then open OccultationMedia.exe. Keep _internal beside it.\n\n本包按用户要求仅打包，未启动程序或执行运行测试。\nBuild-only delivery: the application was not launched or runtime-tested.\n',encoding='utf-8-sig')
archive=Path(shutil.make_archive(str(root/'dist'/f'OccultationMedia-v{version}-Windows-x64'),'zip',root/'dist','OccultationMedia'))
report={'version':version,'architecture':'Windows x64','build_host':'macOS / CrossOver Windows Python','python':sys.version,'application_executed':False,'runtime_tests':'not run at user request','exe_sha256':hashlib.sha256((package/'OccultationMedia.exe').read_bytes()).hexdigest(),'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'dependencies':{d.metadata['Name']:d.version for d in metadata.distributions()}}
(root/'dist/windows-build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(archive)
