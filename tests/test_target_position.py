"""CSV metadata must identify the selected target, independent of table order."""
from pathlib import Path
import tempfile
import unittest
from occultation_media.read_tangra_photometry import read_target_position

class TargetPositionTests(unittest.TestCase):
    def read(self, text, target=2):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'curve.csv'
            path.write_text('\ufeff'+text, encoding='utf-8')
            return read_target_position(path,target)

    def test_reordered_columns_and_target(self):
        text='Object, Type, StartingY, StartingX\n1,GuidingStar,9,8\n2,OccultedStar,223.7,400.1\nFrameNo,Time (UT)\n'
        self.assertEqual(self.read(text),(400.1,223.7))
        self.assertIsNone(self.read(text,3))

    def test_invalid_and_missing(self):
        for pair in ['nan,2','inf,3','-1,3',',3','bad,3']:
            self.assertIsNone(self.read('Object,StartingX,StartingY\n2,'+pair))
        self.assertIsNone(self.read('Object,Type\n2,OccultedStar\nFrameNo,Time (UT)'))
        self.assertIsNone(self.read('Object,StartingX,StartingY\n2,1,2\n2,3,4'))

if __name__=='__main__':unittest.main()
