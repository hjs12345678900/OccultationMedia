"""Validate explicit CSV/source indexing before synchronized rendering."""
from pathlib import Path
import numpy as np
from .read_frame_sources import open_source


def add_source_arguments(parser):
    """Add source selection and explicit zero-based frame mapping CLI options."""
    parser.add_argument('--source',type=Path,help='ADV/SER/RAVF/FITS file or FITS directory; omit for LC cutouts')
    parser.add_argument('--csv',type=Path,help='Explicit Tangra CSV (required when folder has multiple CSVs)')
    parser.add_argument('--lc',type=Path,help='Explicit LC file for legacy cutout mode')
    parser.add_argument('--source-first-frame',type=int,help='CSV frame number corresponding to source index 0; required with --source')
    parser.add_argument('--target-xy',type=float,nargs=2,metavar=('X','Y'),help='Override CSV initial target position, zero-based source pixels')
    parser.add_argument('--ser-byte-order',choices=('header','little','big'),default='header')
    parser.add_argument('--fits-hdu',type=int)
    parser.add_argument('--adv-python',help='Compatible Python executable for ADV decoding')
    parser.add_argument('--stride',type=int,default=1,help='Display every Nth CSV sample, preserving elapsed time')
    parser.add_argument('--event-frames',type=int,nargs=2,metavar=('FIRST_LOW','LAST_LOW'),help='Inclusive CSV low-state frames; bypass automatic detection')
    parser.add_argument('--no-mp4',action='store_true',help='Only GIF and PNG, without ffmpeg')


def unique_file(folder, explicit, suffix):
    """Select an explicit file or the sole matching extension; never guess."""
    if explicit is not None:
        if not explicit.is_file():
            raise ValueError(f'File not found: {explicit}')
        return explicit
    paths = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower()==suffix]
    if len(paths)!=1:
        raise ValueError(f'Expected exactly one {suffix} file; found {len(paths)}. Specify it explicitly.')
    return paths[0]


def validate_rows(rows, target_id):
    """Require finite target flux, unique frames and strictly increasing UTC."""
    if len(rows)<3 or len({r.frame for r in rows})!=len(rows):
        raise ValueError('CSV must contain at least 3 distinct frame numbers')
    if any(b.time_utc<=a.time_utc for a,b in zip(rows,rows[1:])):
        raise ValueError('CSV UTC must increase; check date rollover or duplicate times')
    if not all(np.isfinite(r.net_flux_adu(target_id)) for r in rows):
        raise ValueError('CSV target net flux contains missing/nonfinite values')


def load_source_frames(args, selected_rows):
    """Return CSV-frame-keyed raw pixels and auditable source timing metadata.

    source_index = csv_frame - source_first_frame. Native timestamps are saved
    separately; they never override Tangra UTC or receive duplicate corrections.
    """
    if args.source_first_frame is None:
        raise ValueError('--source-first-frame is required with --source; do not guess frame alignment')
    source = open_source(args.source,ser_byte_order=args.ser_byte_order,
                         fits_hdu=args.fits_hdu,adv_python=args.adv_python)
    indices = [r.frame-args.source_first_frame for r in selected_rows]
    if any(i<0 or i>=source.count for i in indices):
        raise ValueError(f'Mapped source indices outside 0..{source.count-1}; check --source-first-frame')
    decoded = source.read_many(indices) if hasattr(source,'read_many') else {i:source.read(i) for i in indices}
    images,records = {},[]
    for row,index in zip(selected_rows,indices):
        pixels,info = decoded[index]
        if pixels.ndim not in (2,3) or (pixels.ndim==3 and pixels.shape[-1]!=3):
            raise ValueError('Expected grayscale (y,x) or RGB (y,x,3) pixels')
        images[row.frame] = pixels
        records.append(dict(info,csv_frame=row.frame,csv_utc=row.time_utc.isoformat()))
    if len({p.shape for p in images.values()})!=1:
        raise ValueError('Selected source frames have inconsistent dimensions')
    return images,{'source':str(args.source.resolve()),'source_first_frame':args.source_first_frame,
                   'source_metadata':source.metadata,'frames':records,
                   'display_timestamp_convention':'Tangra CSV UTC; no additional time correction'}
