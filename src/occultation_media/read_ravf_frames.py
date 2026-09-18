"""Decode RAVF raw samples, preserving packed 10/12-bit detector units.

Uses the upstream ravf container reader; pixel packing follows ravf 1.0.1
ravf_image_utils.py: https://github.com/ChasinSpin/ravf . Bayer mosaics remain
raw grayscale samples rather than silently debayering or scaling to 16 bits.
"""
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np


def unpack_pixels(data, width, height, stride, image_format, endian, color):
    """Return raw (y,x[,RGB]) samples; reject invalid dimensions/packing.

    Packed 10-bit: four high bytes followed by four 2-bit low parts, MSB first.
    Packed 12-bit: shared low-nibble byte followed by two high bytes.
    Row padding is discarded. No photometric calibration is performed.
    """
    if min(width, height, stride) <= 0 or len(data) != height*stride:
        raise ValueError('Invalid RAVF dimensions or pixel payload length')
    if endian not in (0,1) or color not in range(11):
        raise ValueError('Invalid RAVF endian/color metadata')
    channels = 3 if color in (9,10) else 1
    n = width*channels
    raw = np.frombuffer(data, 'u1').reshape(height, stride)
    if image_format in (0,1,4,5):
        size = 1 if image_format == 0 else 2
        if stride < n*size:
            raise ValueError('RAVF stride shorter than image row')
        dtype = 'u1' if size == 1 else ('<' if endian else '>')+'u2'
        pixels = np.frombuffer(raw[:, :n*size].copy().tobytes(), dtype).reshape(height, n)
    elif image_format in (2,3):
        group, length = (4,5) if image_format == 2 else (2,3)
        if n % group or stride < n//group*length:
            raise ValueError('Unsupported RAVF packed row width or stride')
        packed = raw[:, :n//group*length].astype(np.uint16).reshape(height, -1, length)
        pixels = np.empty((height,n), dtype=np.uint16)
        if image_format == 2:
            for j in range(4):
                pixels[:, j::4] = (packed[:,:,j] << 2) | ((packed[:,:,4] >> (6-2*j)) & 3)
        else:
            pixels[:,0::2] = (packed[:,:,1] << 4) | (packed[:,:,0] >> 4)
            pixels[:,1::2] = (packed[:,:,2] << 4) | (packed[:,:,0] & 15)
    else:
        raise ValueError(f'Unsupported RAVF image format {image_format}')
    pixels = pixels.reshape((height,width)+((3,) if channels == 3 else ()))
    return pixels[...,::-1].copy() if color == 10 else pixels.copy()


class RavfSource:
    """Random-access RAVF; original start/exposure nanoseconds retained."""
    def __init__(self, path):
        try:
            from ravf import RavfReader
        except ImportError as error:
            raise RuntimeError('RAVF requires ravf and opencv-python; install requirements-media.txt') from error
        self.path = Path(path)
        with self.path.open('rb') as stream:
            self.reader = RavfReader(stream)
        self.count = self.reader.frame_count()
        names = ('IMAGE-WIDTH','IMAGE-HEIGHT','IMAGE-ROW-STRIDE','IMAGE-FORMAT','IMAGE-ENDIANESS','COLOR-TYPE')
        self.settings = [int(self.reader.metadata_value(k)) for k in names]
        self.metadata = dict(zip(names,self.settings))
        self.metadata.update(format='RAVF', count=self.count, timestamp_convention='UTC exposure start; ns since 2010-01-01')

    def read(self, index):
        """Return detector counts and recorded exposure-start UTC metadata."""
        if not 0 <= index < self.count:
            raise IndexError(f'RAVF index {index} outside 0..{self.count-1}')
        with self.path.open('rb') as stream:
            frame = self.reader.frame_by_index(stream,index)
        pixels = unpack_pixels(frame.data, *self.settings)
        info = {'source_index': index, 'start_timestamp_ns': frame.start_timestamp,
                'exposure_ns': frame.exposure_duration,
                'utc': (datetime(2010,1,1)+timedelta(microseconds=frame.start_timestamp//1000)).isoformat()}
        return pixels, info
