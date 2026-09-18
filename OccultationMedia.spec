# Build on the target OS. The macOS release is x86_64 for ADV compatibility.
from pathlib import Path
import importlib.util
import sys
import tomllib
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
root=Path(SPECPATH)
sys.path.insert(0,str(root/'build_tools'))
from prepare_ravf_bundle import prepare
vendor=prepare(root)
adv=Path(importlib.util.find_spec('Adv2').origin).parent
native='libAdvCore.dylib' if sys.platform=='darwin' else 'AdvLib.Core64.dll'
datas=collect_data_files('imageio_ffmpeg')+[(str(root/'src/occultation_media/assets'),'occultation_media/assets')]
hidden=collect_submodules('ravf')+['Adv2.AdvLib','Adv2.Adv','Adv2.AdvError']
a=Analysis([str(root/'launch.py')],pathex=[str(vendor),str(root/'src')],
           binaries=[(str(adv/'Adv2DLLlibs'/native),'Adv2/Adv2DLLlibs')],
           datas=datas,hiddenimports=hidden,excludes=['matplotlib','IPython','pytest','cv2'])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='OccultationMedia',
        debug=False,strip=False,upx=False,console=False,
        target_arch='x86_64' if sys.platform=='darwin' else None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='OccultationMedia')
if sys.platform=='darwin':
    app=BUNDLE(coll,name='OccultationMedia.app',bundle_identifier='org.occultation.media',
               info_plist={'CFBundleShortVersionString':tomllib.loads((root/'pyproject.toml').read_text())['project']['version'],'NSHighResolutionCapable':True})
