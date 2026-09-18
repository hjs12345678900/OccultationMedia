"""Isolated ADV2 decoder using only stdlib plus Adv2's ctypes wrapper.

An Intel Python can run this worker under Rosetta without importing ARM NumPy.
Writes little-endian uint32 detector arrays and native exposure midpoint ns.
"""
import json
import sys
from array import array
from ctypes import c_uint
from pathlib import Path
from datetime import datetime, timedelta


def main():
    """Decode a JSON request (source, indices, output_dir) to files and metadata."""
    from Adv2 import AdvLib
    from Adv2.Adv import AdvFileInfo, AdvFrameInfo, StreamId
    request = json.loads(sys.stdin.read())
    info = AdvFileInfo()
    version = AdvLib.AdvOpenFile(request['source'], info)
    if version != 2:
        AdvLib.AdvCloseFile()
        raise ValueError(f'ADV2 required; decoder returned {version}')
    try:
        records = []
        for index in request['indices']:
            if not 0 <= index < info.CountMainFrames:
                raise IndexError(f'ADV index {index} outside 0..{info.CountMainFrames-1}')
            pixels = (c_uint*(info.Width*info.Height))()
            timing = AdvFrameInfo()
            status = AdvLib.AdvVer2_GetFramePixels(StreamId.Main,index,pixels,timing,0)
            if status != 0:
                raise ValueError(f'ADV decode failed at frame {index}: {status}')
            values = array('I',pixels)
            if sys.byteorder != 'little':
                values.byteswap()
            Path(request['output_dir'], f'{index}.raw').write_bytes(values.tobytes())
            ns = timing.UtcMidExposureTimestampLo + (timing.UtcMidExposureTimestampHi << 32)
            records.append({'source_index': index, 'midpoint_timestamp_ns': ns,
                            'utc': (datetime(2010,1,1)+timedelta(microseconds=ns//1000)).isoformat(),
                            'exposure_ns': timing.Exposure})
        print(json.dumps({'format':'ADV2', 'width': info.Width, 'height': info.Height,
                          'count': info.CountMainFrames, 'frames': records,
                          'timestamp_convention': 'UTC exposure midpoint; ns since 2010-01-01'}))
    finally:
        AdvLib.AdvCloseFile()


if __name__ == '__main__':
    main()
