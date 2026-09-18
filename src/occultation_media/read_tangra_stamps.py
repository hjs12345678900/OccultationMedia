"""Decode the recorded 35x35 target stamps from Tangra LC v4 containers."""
from __future__ import annotations
import io
import struct
import zlib
from pathlib import Path
import numpy as np
STAMP_SIZE = 35

class DotNetReader:
    """Read little-endian primitives emitted by .NET ``BinaryWriter``."""

    def __init__(self, stream: io.BytesIO) -> None:
        self.stream = stream

    def read(self, count: int) -> bytes:
        value = self.stream.read(count)
        if len(value) != count:
            raise EOFError(f"Expected {count} bytes, received {len(value)}")
        return value

    def unpack(self, code: str):
        return struct.unpack("<" + code, self.read(struct.calcsize(code)))[0]

    def u8(self) -> int: return self.unpack("B")
    def boolean(self) -> bool: return bool(self.u8())
    def i16(self) -> int: return self.unpack("h")
    def i32(self) -> int: return self.unpack("i")
    def u32(self) -> int: return self.unpack("I")
    def i64(self) -> int: return self.unpack("q")
    def f32(self) -> float: return self.unpack("f")
    def f64(self) -> float: return self.unpack("d")

    def string(self) -> str:
        """Read a UTF-8 string with a .NET 7-bit byte-count prefix."""

        length = 0
        shift = 0
        while True:
            byte = self.u8()
            length |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return self.read(length).decode("utf-8")
            shift += 7
            if shift > 35:
                raise ValueError("Invalid .NET string length")

def skip_lc_header(reader: DotNetReader) -> tuple[int, int, int]:
    """Consume a Tangra v4 header and return object/timing/frame counts."""

    container_version = reader.i16()
    if container_version != 4:
        raise ValueError(f"Only Tangra LC container v4 is supported, got {container_version}")
    header_version = reader.i32()
    reader.u32(); reader.u32(); reader.u32()
    object_count = reader.u8()
    reader.i32(); reader.string(); reader.string(); reader.i32(); reader.i32()
    reader.i64(); reader.i64(); reader.f64(); reader.u32(); reader.i32(); reader.i32()
    for _ in range(object_count):
        reader.i32(); reader.f32(); reader.boolean()
    reader.f32()
    if header_version > 1: reader.i32(); reader.i32()
    timing_type = reader.u8() if header_version > 2 else 0
    if header_version > 3:
        for _ in range(object_count): reader.i32()
    if header_version > 4:
        for _ in range(object_count): reader.f64()
    if header_version > 5: reader.f64()
    if header_version > 6: reader.i32()
    if header_version > 7: reader.i32()
    if reader.u8() != object_count:
        raise ValueError("Tangra object-count fields disagree")
    return object_count, timing_type, reader.i32()

def skip_frame_timing(reader: DotNetReader) -> None:
    """Consume one Tangra frame-timing record."""

    version = reader.i32()
    reader.i64(); reader.i32()
    width, height = reader.i32(), reader.i32()
    reader.read(width * height)
    if version > 1 and reader.boolean():
        reader.read(24)

def read_measurement(reader: DotNetReader, retain: bool) -> tuple[int, int, np.ndarray | None]:
    """Read one object measurement and optionally retain its 35 × 35 stamp.

    Returns
    -------
    frame, target : int
        Tangra frame number and zero-based target number.
    pixels : ndarray, uint32, shape (35, 35), or None
        Raw detector counts in image ``(y, x)`` order when retained.
    """

    version = reader.i32()
    frame, target = reader.u32(), reader.u8()
    reader.u32(); reader.u32()
    dtype = np.dtype("<u1" if version < 7 else "<u4")
    raw = reader.read(STAMP_SIZE * STAMP_SIZE * dtype.itemsize)
    pixels = None
    if retain:
        pixels = np.frombuffer(raw, dtype=dtype).astype(np.uint32).reshape(STAMP_SIZE, STAMP_SIZE).T
    reader.u8(); reader.f32(); reader.f32(); reader.i32(); reader.i32()
    if version == 3: reader.read(8)
    if version > 4: reader.i64()
    if version > 5: reader.u32()
    if version > 7: reader.read(12)
    if version > 8:
        file_name_length = reader.i32()
        if file_name_length > 0: reader.string()
    return frame, target, pixels

def extract_target_stamps(
    lc_path: Path, wanted_frames: set[int], target_id: int
) -> dict[int, np.ndarray]:
    """Extract selected target stamps from a raw-DEFLATE Tangra `.lc` file.

    Parameters
    ----------
    lc_path : Path
        Tangra v4 `.lc` file.
    wanted_frames : set[int]
        Frame numbers needed by the animation.
    target_id : int
        One-based target identifier from the Tangra CSV.

    Returns
    -------
    dict[int, ndarray]
        Frame number to raw ``uint32`` detector stamp, shape ``(35, 35)``.
    """

    payload = zlib.decompress(lc_path.read_bytes(), wbits=-15)
    reader = DotNetReader(io.BytesIO(payload))
    object_count, timing_type, frame_count = skip_lc_header(reader)
    stamps: dict[int, np.ndarray] = {}
    zero_based_target = target_id - 1
    for _ in range(frame_count):
        if timing_type != 0: skip_frame_timing(reader)
        for _object in range(object_count):
            position = reader.stream.tell()
            reader.i32(); frame = reader.u32(); target = reader.u8()
            reader.stream.seek(position)
            retain = frame in wanted_frames and target == zero_based_target
            frame, target, pixels = read_measurement(reader, retain)
            if pixels is not None: stamps[frame] = pixels
        if len(stamps) == len(wanted_frames): break
    missing = wanted_frames.difference(stamps)
    if missing:
        raise ValueError(f"Tangra .lc is missing {len(missing)} requested stamps")
    return stamps
