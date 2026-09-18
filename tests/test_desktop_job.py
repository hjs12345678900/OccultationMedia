"""Desktop form validation, including localized punctuation and safe outputs."""
from pathlib import Path
import tempfile
import unittest
from occultation_media.desktop_job import prepare_job


class DesktopJobTests(unittest.TestCase):
    def test_fullwidth_time_and_unique_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'input.ser').touch();(root/'curve.csv').touch()
            values={'source':str(root/'input.ser'),'csv':str(root/'curve.csv'),'output':str(root),
                    'date':'2026-09-07','predicted':'11：04：20','asteroid':'YB35','star':'Target',
                    'uncertainty':'０．９','exposure':'194.7','first':'0','margin':'1','stride':'1',
                    'low':'314，317','target':'','hdu':'','mp4':True,'language':'both','byte_order':'header'}
            first,out1=prepare_job(values);second,out2=prepare_job(values)
            self.assertEqual(first[first.index('--predicted-time')+1],'11:04:20')
            self.assertEqual(first[first.index('--event-frames')+1:first.index('--event-frames')+3],['314','317'])
            self.assertNotEqual(out1,out2)
            values['exposure']='NaN'
            with self.assertRaises(ValueError):prepare_job(values)


if __name__=='__main__':unittest.main()
