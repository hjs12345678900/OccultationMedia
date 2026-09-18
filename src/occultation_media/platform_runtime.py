"""Resolve cross-platform fonts and the packaged FFmpeg executable."""
from pathlib import Path
import os
import subprocess
from PIL import ImageFont


def load_font(size, language, bold=False):
    """Load system Latin/CJK fonts on Windows or macOS; fail clearly for CJK."""
    bundled=Path(__file__).parent/'assets/fonts/NotoSansCJKsc-Regular.otf'
    if bundled.exists():return ImageFont.truetype(str(bundled),size)
    windows=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    if language=='zh':
        candidates=[Path('/System/Library/Fonts/STHeiti Medium.ttc'),windows/'msyh.ttc',
                    windows/'msyhbd.ttc',windows/'simhei.ttf',
                    Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    else:
        candidates=[windows/('arialbd.ttf' if bold else 'arial.ttf'),
                    Path('/System/Library/Fonts/Supplemental')/('Arial Bold.ttf' if bold else 'Arial.ttf'),
                    Path('/System/Library/Fonts/Helvetica.ttc'),
                    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path),size)
    if language=='zh':
        raise RuntimeError('Chinese font unavailable. Install Microsoft YaHei/Noto Sans CJK or select English.')
    return ImageFont.load_default(size=size)


def ffmpeg_executable():
    """Return the bundled platform FFmpeg from imageio-ffmpeg, no PATH needed."""
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def hidden_process_options():
    """Prevent a console flash for child workers and FFmpeg on Windows."""
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
