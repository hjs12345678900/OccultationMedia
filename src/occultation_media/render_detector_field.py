"""Pure display transforms for detector counts, independent of photometry."""
import numpy as np
from PIL import Image, ImageDraw


def first_frame_limits(frame):
    """Return 0.5/99.95 percentiles in input counts, ignoring invalid pixels.

    Limits are calculated once from the first displayed frame. Degenerate
    upper limits become black+1; a frame without finite samples is rejected.
    """
    pixels = np.asarray(frame,dtype=float)
    finite = pixels[np.isfinite(pixels)]
    if not finite.size:
        raise ValueError('Initial frame contains no finite pixels')
    black,white = np.percentile(finite,[0.5,99.95])
    return float(black),float(max(white,black+1) if white <= black else white)


def display_pixels(frame, black, white):
    """Map counts to uint8: round(255*asinh(8*x)/asinh(8)).

    x=clip((counts-black)/(white-black),0,1); nonfinite pixels display black.
    The supplied fixed limits must be reused for every frame of the clip.
    """
    x = np.clip((np.asarray(frame,dtype=float)-black)/(white-black),0,1)
    x = np.where(np.isfinite(x),x,0)
    return np.rint(255*np.arcsinh(8*x)/np.arcsinh(8)).astype(np.uint8)


def paste_full_field(panel, pixels, black, white, target_xy=None):
    """Fit full (y,x[,RGB]) field into the panel without cropping/distortion.

    Optional target_xy is in zero-based source pixels, origin upper left.
    A fixed lower/right crosshair leaves the star center unobscured; no tracking.
    """
    image = Image.fromarray(display_pixels(pixels,black,white)).convert('RGB')
    scale = min(852/image.width,560/image.height)
    width,height = max(1,round(image.width*scale)),max(1,round(image.height*scale))
    image = image.resize((width,height),Image.Resampling.LANCZOS)
    left,top = 54+(872-width)//2,124+(580-height)//2
    panel.paste(image,(left,top))
    if target_xy is not None:
        x,y = target_xy
        if not (0 <= x < pixels.shape[1] and 0 <= y < pixels.shape[0]):
            raise ValueError('Target coordinates outside source image')
        x,y = left+(x+.5)*width/pixels.shape[1],top+(y+.5)*height/pixels.shape[0]
        draw = ImageDraw.Draw(panel)
        draw.line((x+10,y,x+30,y),fill=(255,242,88),width=3)
        draw.line((x,y+10,x,y+30),fill=(255,242,88),width=3)


def frame_durations(rows):
    """Quantize elapsed CSV times to GIF 10-ms ticks without cumulative drift.

    Last frame uses median selected cadence. Intervals below 10 ms are rejected
    because GIF cannot represent them; subsample using --stride in that case.
    """
    times = np.array([(r.time_utc-rows[0].time_utc).total_seconds() for r in rows])
    steps = np.diff(times)
    if len(rows)<2 or np.any(steps<=0):
        raise ValueError('At least two strictly increasing CSV timestamps required')
    ticks = np.rint(np.r_[times,times[-1]+np.median(steps)]*100).astype(int)
    duration = np.diff(ticks)*10
    if np.any(duration < 10):
        raise ValueError('GIF cadence below 10 ms; increase --stride')
    return duration.tolist()
