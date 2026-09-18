"""Independent binary fixtures for pixel, timing and display invariants."""
import contextlib
from datetime import datetime, timedelta
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
import numpy as np
from astropy.io import fits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from occultation_media.read_frame_sources import SerSource, FitsSource
from occultation_media.read_ravf_frames import RavfSource, unpack_pixels
from occultation_media.render_detector_field import first_frame_limits, display_pixels, frame_durations
from occultation_media.prepare_source_frames import load_source_frames


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_ser(self, order, depth=16):
        frames = np.array([[[0,1],[257,1023]],[[14,25],[87,99]]],dtype=np.uint16)
        if depth==8:
            frames = (frames%256).astype('u1')
        path = self.root/'test.ser'
        h=bytearray(178);h[:14]=b'LUCAM-RECORDER'
        struct.pack_into('<7I',h,14,0,0,int(order=='<'),2,2,depth,2)
        ticks = 638000000000000000
        path.write_bytes(h+frames.astype('u1' if depth==8 else order+'u2').tobytes()+struct.pack('<2Q',ticks,ticks+3000000))
        return path,frames

    def test_ser_orders_depth_and_timing(self):
        for order in ['<','>']:
            for depth in [8,12,16]:
                path,expected=self.write_ser(order,depth)
                src=SerSource(path)
                for i in range(2):
                    np.testing.assert_array_equal(src.read(i)[0],expected[i])
                t=[datetime.fromisoformat(src.read(i)[1]['utc']) for i in range(2)]
                self.assertAlmostEqual((t[1]-t[0]).total_seconds(),.3)
                with self.assertRaises(IndexError):src.read(-1)
                path.write_bytes(path.read_bytes()[:180])
                with self.assertRaises(ValueError):SerSource(path)

    def test_fits_natural_order_cube_and_bzero(self):
        directory=self.root/'fits';directory.mkdir()
        a=np.array([[0,65535],[32768,4]],dtype=np.uint16)
        fits.writeto(directory/'frame10.fit',a+0)
        fits.writeto(directory/'frame2.fit',a//2)
        src=FitsSource(directory)
        np.testing.assert_array_equal(src.read(0)[0],a//2)
        np.testing.assert_array_equal(src.read(1)[0],a)
        cube=self.root/'cube.fits';fits.writeto(cube,np.stack([a,a//2]))
        np.testing.assert_array_equal(FitsSource(cube).read(1)[0],a//2)
        multi=self.root/'multi.fits'
        fits.HDUList([fits.PrimaryHDU(a),fits.ImageHDU(a)]).writeto(multi)
        with self.assertRaises(ValueError):FitsSource(multi)
        np.testing.assert_array_equal(FitsSource(multi,1).read(0)[0],a)

    def test_ravf_packed_known_values(self):
        # Hand-encoded values test nibble/bit order rather than round-trip code.
        p=unpack_pixels(bytes([0,1,128,255,0b00011011,99]),4,1,6,2,1,0)
        np.testing.assert_array_equal(p,[[0,5,514,1023]])
        p=unpack_pixels(bytes([0xCF,0xAB,0xDE,99]),2,1,4,3,1,0)
        np.testing.assert_array_equal(p,[[0xABC,0xDEF]])
        for fmt in [1,4,5]:
            for endian,dtype in [(0,'>u2'),(1,'<u2')]:
                raw=np.array([3,200,777],dtype=dtype).tobytes()+b'xx'
                p=unpack_pixels(raw,3,1,8,fmt,endian,0)
                np.testing.assert_array_equal(p,[[3,200,777]])
        np.testing.assert_array_equal(unpack_pixels(b'\1\2\3x',3,1,4,0,1,0),[[1,2,3]])

    def test_ravf_real_container(self):
        from ravf import RavfWriter,RavfFrameType
        path=self.root/'test.ravf'
        required=[('COLOR-TYPE',0),('IMAGE-ENDIANESS',1),('IMAGE-WIDTH',4),('IMAGE-HEIGHT',2),
                  ('IMAGE-ROW-STRIDE',10),('IMAGE-FORMAT',1),('FRAME-TIMING-ACCURACY',1000)]
        raw=np.arange(8,dtype='<u2').reshape(2,4)
        data=b''.join(row.tobytes()+b'xx' for row in raw)
        with contextlib.redirect_stdout(io.StringIO()),path.open('wb') as f:
            w=RavfWriter(f,required,[])
            w.write_frame(f,RavfFrameType.LIGHT,data,1_000_000_000,20_000_000,7,0,0,0,0)
            w.finish(f)
        s=RavfSource(path);pixels,info=s.read(0)
        np.testing.assert_array_equal(pixels,raw)
        self.assertEqual(info['utc'],'2010-01-01T00:00:01')
        self.assertEqual(info['exposure_ns'],20_000_000)

    def test_mapping_not_position_in_csv(self):
        path,expected=self.write_ser('<')
        args=SimpleNamespace(source=path,source_first_frame=1500,ser_byte_order='header',fits_hdu=None,adv_python=None)
        rows=[SimpleNamespace(frame=1501,time_utc=datetime(2026,1,1))]
        images,metadata=load_source_frames(args,rows)
        np.testing.assert_array_equal(images[1501],expected[1])
        self.assertEqual(metadata['frames'][0]['source_index'],1)
        args.source_first_frame=None
        with self.assertRaises(ValueError):load_source_frames(args,rows)

    def test_fixed_stretch_and_gif_elapsed_time(self):
        first=np.arange(10000,dtype=float).reshape(100,100)
        black,white=first_frame_limits(first)
        self.assertAlmostEqual(black,49.995)
        self.assertAlmostEqual(white,9994.0005)
        bright=display_pixels(first,black,white)
        dim=display_pixels(first*.5,black,white)
        self.assertLess(int(dim[50,50]),int(bright[50,50]))
        self.assertEqual(first_frame_limits(np.ones((2,2))),(1.,2.))
        t=datetime(2026,1,1)
        rows=[SimpleNamespace(time_utc=t+timedelta(seconds=x)) for x in [0,.301,.602,.903]]
        durations=frame_durations(rows)
        self.assertLessEqual(abs(sum(durations)-1204),5)
        with self.assertRaises(ValueError):frame_durations([rows[0],rows[0]])


if __name__=='__main__':unittest.main()
