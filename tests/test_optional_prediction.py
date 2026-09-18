"""Missing prediction must not become a fabricated time or visual overlay."""
from datetime import datetime,timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import ImageDraw
from occultation_media.read_tangra_photometry import TangraRow
from occultation_media.detect_low_flux import detect_event
from occultation_media.render_occultation_media import render_language
from occultation_media.desktop_job import prepare_job


class OptionalPredictionTests(unittest.TestCase):
    def test_search_without_prediction(self):
        t=datetime(2026,1,1)
        rows=[TangraRow(i,t+timedelta(seconds=i),{1:10 if 45<=i<=65 else 100},{1:0}) for i in range(110)]
        start,end=detect_event(rows,1)
        self.assertLessEqual(start,55);self.assertGreaterEqual(end,55)
        with self.assertRaisesRegex(ValueError,'--event-frames'):
            detect_event(rows,1,t+timedelta(seconds=10))

    def test_desktop_blank_and_time_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'test.ser').touch();(root/'curve.csv').touch()
            v={'source':str(root/'test.ser'),'csv':str(root/'curve.csv'),'output':str(root),
               'date':'2026-01-01','predicted':'','uncertainty':'','exposure':'300','margin':'1',
               'stride':'1','first':'0','asteroid':'Test','star':'Target','language':'en',
               'byte_order':'header','low':'2 3','target':'','hdu':'','mp4':False}
            args,_=prepare_job(v)
            self.assertNotIn('--predicted-time',args);self.assertNotIn('--prediction-error-sec',args)
            v['uncertainty']='0.7'
            args,_=prepare_job(v);self.assertNotIn('--prediction-error-sec',args)
            v.update(predicted='00:00:01',uncertainty='')
            args,_=prepare_job(v);self.assertIn('--predicted-time',args);self.assertNotIn('--prediction-error-sec',args)
            v['uncertainty']='0'
            args,_=prepare_job(v);self.assertEqual(args[args.index('--prediction-error-sec')+1],'0')

    def test_render_omits_prediction_labels_and_band(self):
        t=datetime(2026,1,1)
        rows=[TangraRow(i,t+timedelta(seconds=i*.3),{1:100000},{1:0}) for i in range(6)]
        stamps={i:np.arange(2048,dtype=np.uint16).reshape(32,64) for i in range(6)}
        original_text=ImageDraw.ImageDraw.text
        original_rectangle=ImageDraw.ImageDraw.rectangle
        for lang in ['en','zh']:
            for midpoint,error in [(None,None),(t+timedelta(seconds=.75),None),(t+timedelta(seconds=.75),.2)]:
                texts=[];bands=[]
                def draw_text(draw,xy,text,*args,**kwargs):
                    texts.append(str(text));return original_text(draw,xy,text,*args,**kwargs)
                def rectangle(draw,xy,*args,**kwargs):
                    if kwargs.get('fill') in [(65,116,166,42),(65,116,166,90)]:bands.append(xy)
                    return original_rectangle(draw,xy,*args,**kwargs)
                with tempfile.TemporaryDirectory() as directory,patch.object(ImageDraw.ImageDraw,'text',draw_text),patch.object(ImageDraw.ImageDraw,'rectangle',rectangle):
                    result=render_language(rows,list(range(6)),stamps,1,(2,3),midpoint,error,
                         'Test','Target',300,None,lang,Path(directory)/'test.gif',full_field=True)
                    self.assertEqual(result['frames'],6)
                predictions=[s for s in texts if 'predic' in s.lower() or '预报' in s]
                self.assertEqual(bool(predictions),midpoint is not None)
                self.assertEqual(bool(bands),midpoint is not None and error is not None)


if __name__=='__main__':unittest.main()
