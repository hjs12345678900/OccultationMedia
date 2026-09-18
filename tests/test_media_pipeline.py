"""Run real CLI exports for synthetic SER, FITS and official-writer RAVF.

Synthetic detector arrays and CSV flux intentionally share a known low state.
These fixtures validate media plumbing, not astrophysical event measurement.
"""
import contextlib
from datetime import datetime,timedelta
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from PIL import Image
from astropy.io import fits
from ravf import RavfWriter,RavfFrameType


class PipelineTests(unittest.TestCase):
    def test_three_sources_export_matching_stretch_and_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            y,x=np.mgrid[:32,:64]
            base=(1000+40*x+20*y+20000*np.exp(-((x-32)**2+(y-16)**2)/4)).astype('<u2')
            cube=np.stack([base if not 7<=i<=11 else (base*.65).astype('<u2') for i in range(20)])
            csv=['Object,Type,StartingX,StartingY','1,OccultedStar,32,16','FrameNo,Time (UT),Signal (1),Background (1)']
            for i in range(20):
                utc=datetime(2026,1,1)+timedelta(seconds=i*.301)
                csv.append(f"{i+1500},{utc.strftime('%H:%M:%S.%f')},{20000 if 7<=i<=11 else 120000},1000")
            (root/'curve.csv').write_text('\n'.join(csv))
            fits.writeto(root/'cube.fits',cube)
            header=bytearray(178);header[:14]=b'LUCAM-RECORDER'
            struct.pack_into('<7I',header,14,0,0,1,64,32,16,20)
            (root/'frames.ser').write_bytes(header+cube.tobytes())
            with contextlib.redirect_stdout(io.StringIO()),(root/'frames.ravf').open('wb') as stream:
                w=RavfWriter(stream,[('COLOR-TYPE',0),('IMAGE-ENDIANESS',1),('IMAGE-WIDTH',64),
                    ('IMAGE-HEIGHT',32),('IMAGE-ROW-STRIDE',128),('IMAGE-FORMAT',1),('FRAME-TIMING-ACCURACY',1000)],[])
                for i,pixels in enumerate(cube):
                    w.write_frame(stream,RavfFrameType.LIGHT,pixels.tobytes(),i*301000000,300000000,7,0,0,0,i)
                w.finish(stream)
            script=Path(__file__).resolve().parents[1]/'launch.py'
            summaries=[]
            for source in ['frames.ser','cube.fits','frames.ravf']:
                out=root/source.replace('.','_')
                args=[sys.executable,str(script),'--cli',str(root),'--source',str(root/source),'--source-first-frame','1500',
                      '--event-date','2026-01-01','--asteroid','Synthetic test','--star','Target',
                      '--predicted-time','00:00:03','--prediction-error-sec','.7','--exposure-ms','300',
                      '--event-frames','1507','1511','--language','en',
                      '--output-dir',str(out),'--basename','test','--no-mp4']
                if source == 'frames.ser':
                    args += ['--target-xy','31','15']
                result=subprocess.run(args,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                metadata=json.loads((out/'test_metadata.json').read_text())
                self.assertEqual(metadata['target_xy'], [31,15] if source == 'frames.ser' else [32,16])
                self.assertEqual(metadata['target_position_source'], 'manual' if source == 'frames.ser' else 'csv_starting_position')
                summaries.append(metadata['outputs']['en'])
                with Image.open(out/'test_occultation_en.gif') as gif:
                    self.assertEqual(gif.size,(1260,540))
                    self.assertEqual(gif.n_frames,20)
                    rgb = np.array(gif.convert("RGB"))
                    yellow = (rgb[:,:,0] > 180) & (rgb[:,:,1] > 160) & (rgb[:,:,2] < 120)
                    self.assertGreater(int(yellow.sum()), 3, "GIF must preserve the target pointer color")
                    duration=0
                    for i in range(gif.n_frames):
                        gif.seek(i);duration+=gif.info['duration']
                    self.assertEqual(duration,6020)
            for field in ['black_adu','white_adu','frames','disappearance_utc','reappearance_utc']:
                self.assertEqual(len({s[field] for s in summaries}),1,field)


if __name__=='__main__':unittest.main()
