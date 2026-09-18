"""Read indexed SER and FITS frames without modifying detector counts.

All indices are zero-based. Arrays use (y, x), or (y, x, RGB); FITS cubes
use (frame, y, x). FITS values include the file's BSCALE/BZERO calibration.
SER layout: https://free-astro.org/images/5/51/SER_Doc_V3b.pdf
"""
from pathlib import Path
from datetime import datetime, timedelta
import re
import struct
import numpy as np


class SerSource:
    """Random-access SER reader; endian override handles nonconforming writers.

    `byte_order=header` follows the specification (1=little, 0=big).
    Bayer mosaics remain raw grayscale counts; RGB/BGR is returned as RGB.
    Timestamp trailer ticks are 100 ns since 0001-01-01, without corrections.
    """
    def __init__(self, path, byte_order='header'):
        self.path = Path(path)
        with self.path.open('rb') as stream:
            header = stream.read(178)
        if len(header) != 178 or header[:14].rstrip(b'\0') != b'LUCAM-RECORDER':
            raise ValueError('Invalid or truncated SER header')
        _, color, endian, self.width, self.height, depth, self.count = struct.unpack_from('<7I', header, 14)
        if not (1 <= depth <= 16 and self.width > 0 and self.height > 0 and self.count > 0):
            raise ValueError('Invalid SER dimensions, depth or count')
        if color not in (0, 8, 9, 10, 11, 16, 17, 18, 19, 100, 101):
            raise ValueError(f'Unsupported SER color ID {color}')
        if endian not in (0, 1):
            raise ValueError('Invalid SER endian flag')
        order = ('<' if endian else '>') if byte_order == 'header' else {'little': '<', 'big': '>'}[byte_order]
        self.dtype = np.dtype('u1' if depth <= 8 else order + 'u2')
        self.color = color
        self.channels = 3 if color in (100, 101) else 1
        self.frame_bytes = self.width * self.height * self.channels * self.dtype.itemsize
        self.trailer = 178 + self.count * self.frame_bytes
        size = self.path.stat().st_size
        if size < self.trailer or (self.trailer < size < self.trailer + 8*self.count):
            raise ValueError('Truncated SER pixels or timestamp trailer')
        self.has_times = size >= self.trailer + 8*self.count
        self.metadata = {'format': 'SER', 'count': self.count, 'width': self.width,
                         'height': self.height, 'byte_order': order, 'color_id': color,
                         'timestamp_convention': 'SER trailer UTC; no delay correction'}

    def read(self, index):
        """Return a copied detector-count array and optional ISO UTC metadata."""
        if not 0 <= index < self.count:
            raise IndexError(f'SER index {index} outside 0..{self.count-1}')
        with self.path.open('rb') as stream:
            stream.seek(178 + index*self.frame_bytes)
            pixels = np.frombuffer(stream.read(self.frame_bytes), self.dtype)
            shape = (self.height, self.width) + ((3,) if self.channels == 3 else ())
            pixels = pixels.reshape(shape).copy()
            if self.color == 101:
                pixels = pixels[..., ::-1].copy()
            info = {'source_index': index}
            if self.has_times:
                stream.seek(self.trailer + 8*index)
                ticks = struct.unpack('<Q', stream.read(8))[0]
                if ticks:
                    info['utc'] = (datetime(1, 1, 1) + timedelta(microseconds=ticks//10)).isoformat()
        return pixels, info


class FitsSource:
    """Read a 2D FITS image, a (time,y,x) cube, or naturally sorted directory.

    Only image HDUs with two/three axes are accepted. Multiple image HDUs
    require explicit `hdu`; no inferred UTC cadence is invented for cubes.
    """
    def __init__(self, path, hdu=None):
        from astropy.io import fits
        self.path, self.hdu = Path(path), hdu
        key = lambda p: [int(v) if v.isdigit() else v.lower() for v in re.split(r'(\d+)', p.name)]
        self.files = sorted([p for p in self.path.iterdir() if p.suffix.lower() in ('.fit', '.fits', '.fts')], key=key) if self.path.is_dir() else [self.path]
        if not self.files:
            raise ValueError('No FITS images in directory')
        self.entries = []
        for file in self.files:
            with fits.open(file, memmap=False) as hdus:
                candidates = [i for i,h in enumerate(hdus) if h.header.get('NAXIS',0) in (2,3) and isinstance(h, (fits.PrimaryHDU, fits.ImageHDU, fits.CompImageHDU))]
                if hdu is None and len(candidates) != 1:
                    raise ValueError(f'{file}: select --fits-hdu; found {len(candidates)} image HDUs')
                chosen = hdu if hdu is not None else candidates[0]
                header = hdus[chosen].header
                if header.get('NAXIS') not in (2,3):
                    raise ValueError('FITS HDU must be a 2D image or 3D time cube')
                for plane in range(header.get('NAXIS3', 1)):
                    self.entries.append((file, chosen, plane))
        self.count = len(self.entries)
        self.metadata = {'format': 'FITS', 'count': self.count, 'file_order': [str(p) for p in self.files],
                         'timestamp_convention': 'Header metadata only; display UTC comes from CSV'}

    def read(self, index):
        """Return calibrated pixels plus original FITS timing header values."""
        from astropy.io import fits
        if not 0 <= index < self.count:
            raise IndexError(f'FITS index {index} outside 0..{self.count-1}')
        file, hdu, plane = self.entries[index]
        with fits.open(file, memmap=False) as hdus:
            data = hdus[hdu].data
            image = (data[plane] if data.ndim == 3 else data).copy()
            info = {'source_index': index, 'file': str(file), 'plane': plane,
                    'header_timing': {k: hdus[hdu].header[k] for k in ('DATE-OBS','DATE-BEG','DATE-END','EXPTIME','TIMESYS') if k in hdus[hdu].header}}
        return image, info


def open_source(path, *, ser_byte_order='header', fits_hdu=None, adv_python=None):
    """Dispatch a path to a raw reader; raise on unsupported formats."""
    path = Path(path)
    if path.is_dir() or path.suffix.lower() in ('.fits', '.fit', '.fts'):
        return FitsSource(path, fits_hdu)
    if path.suffix.lower() == '.ser':
        return SerSource(path, ser_byte_order)
    if path.suffix.lower() == '.ravf':
        from .read_ravf_frames import RavfSource
        return RavfSource(path)
    if path.suffix.lower() == '.adv':
        from .read_adv_frames import AdvSource
        return AdvSource(path, adv_python)
    raise ValueError(f'Unsupported image source: {path}')
