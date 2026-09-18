"""Exercise shipped codecs, fonts and exports inside a frozen application."""
import contextlib
from datetime import datetime,timedelta
import io
import json
from pathlib import Path
import platform
import struct
import tempfile
import numpy as np
from PIL import Image
from astropy.io import fits
from .make_tangra_occultation_media import main as generate
from .platform_runtime import load_font,ffmpeg_executable


def run():
    """Return test results; raise on missing bundled resources or wrong outputs."""
    from ravf import RavfWriter,RavfFrameType
    load_font(20,'en');load_font(20,'zh')
    with tempfile.TemporaryDirectory(prefix='occultation-self-test-') as tmp:
        root=Path(tmp);base=np.arange(2048,dtype='<u2').reshape(32,64)+1000
        cube=np.stack([base if i not in (2,3) else base//2 for i in range(6)])
        csv=['FrameNo,Time (UT),Signal (1),Background (1)']
        for i in range(6):
            t=datetime(2026,1,1)+timedelta(seconds=i*.3)
            csv.append(f"{i},{t.strftime('%H:%M:%S.%f')},{10000 if i in (2,3) else 120000},1000")
        (root/'curve.csv').write_text('\n'.join(csv))
        fits.writeto(root/'cube.fits',cube)
        h=bytearray(178);h[:14]=b'LUCAM-RECORDER';struct.pack_into('<7I',h,14,0,0,1,64,32,16,6)
        (root/'frames.ser').write_bytes(h+cube.tobytes())
        with contextlib.redirect_stdout(io.StringIO()),(root/'frames.ravf').open('wb') as stream:
            writer=RavfWriter(stream,[('COLOR-TYPE',0),('IMAGE-ENDIANESS',1),('IMAGE-WIDTH',64),('IMAGE-HEIGHT',32),
                 ('IMAGE-ROW-STRIDE',128),('IMAGE-FORMAT',1),('FRAME-TIMING-ACCURACY',1000)],[])
            for i,pixels in enumerate(cube):writer.write_frame(stream,RavfFrameType.LIGHT,pixels.tobytes(),i*300000000,300000000,7,0,0,0,i)
            writer.finish(stream)
        summaries=[]
        for source in ['cube.fits','frames.ser','frames.ravf']:
            output=root/source.replace('.','_')
            argv=[str(root),'--source',str(root/source),'--source-first-frame','0',
                  '--event-date','2026-01-01','--asteroid','Self test','--star','Target',
                  '--predicted-time','00:00:00.750','--prediction-error-sec','.2','--exposure-ms','300',
                  '--event-frames','2','3','--language','both','--output-dir',str(output),'--basename','test']
            if source == 'frames.ravf':
                for flag in ('--predicted-time','--prediction-error-sec'):
                    index=argv.index(flag);del argv[index:index+2]
            with contextlib.redirect_stdout(io.StringIO()):generate(argv)
            for lang in ['en','zh']:
                gif=output/f'test_occultation_{lang}.gif'
                with Image.open(gif) as image:
                    if image.n_frames!=6 or image.size!=(1260,540):raise AssertionError('Invalid GIF')
                if (output/f'test_occultation_{lang}.mp4').stat().st_size<100:raise AssertionError('Empty MP4')
            manifest=json.loads((output/'test_metadata.json').read_text())
            if source=='frames.ravf' and manifest['prediction'] is not None:
                raise AssertionError('Missing prediction must remain null')
            summaries.append(manifest['outputs']['en'])
        if len({s['black_adu'] for s in summaries})!=1:raise AssertionError('Stretch differs between source formats')
    return {'ok':True,'system':platform.system(),'architecture':platform.machine(),
            'exports':['SER','FITS','RAVF'],'languages':['en','zh'],'outputs':['GIF','PNG','MP4'],
            'ffmpeg':ffmpeg_executable(),'adv':'Requires separate real-observation smoke test'}
