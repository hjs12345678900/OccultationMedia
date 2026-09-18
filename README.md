# OccultationMedia

**English** | [简体中文](README.zh-CN.md)

A desktop tool for creating occultation animations. Synchronize recorded star fields with Tangra light curves and export GIF, PNG and MP4. Includes English and Chinese interfaces.

## Download and use

Download a package from [Releases](https://github.com/hjs12345678900/OccultationMedia/releases/latest):

- **Windows 10/11 x64:** extract the entire archive and open `OccultationMedia.exe`. Keep the `_internal` folder beside it.
- **macOS 14+:** extract and open `OccultationMedia.app`. Intel build; Apple Silicon requires Rosetta.

Select an observation file, a Tangra CSV and an output folder. Enter the date, exposure time and target names, then generate the animation. Predicted time and uncertainty are optional.

## Features

- Inputs: ADV2, SER, FITS images / sequences / cubes, RAVF, and Tangra LC target cutouts.
- Uses Tangra CSV photometry and UTC. Set the CSV frame number corresponding to source frame 0 to align the data.
- Reads the initial target position from CSV, with a manual override. The marker has only right and lower arms; it does not track frame-by-frame motion.
- Fixes the display stretch using the first displayed frame's 0.5th and 99.95th percentiles throughout the animation.
- English and Chinese output; release packages include Python, Chinese fonts and FFmpeg.

For visualization, not formal occultation timing measurements. The v1.3.2 packages are unsigned / unnotarized and received build and static file checks only, without runtime testing of this version.

## Run and build from source

Use Python 3.13 with Tk support. In a virtual environment:

```bash
python -m pip install -e ".[build]"
python launch.py
```

Build entry points: `Build-Windows.bat` on Windows and `Build-Mac.command` on Mac. Both include tests.
For packaging only, use `python package_windows_only.py` on Windows or `python -m PyInstaller --noconfirm --clean OccultationMedia.spec` on Mac.
GitHub Actions runs are triggered manually. See [THIRD_PARTY.md](THIRD_PARTY.md) for third-party components and licenses.
