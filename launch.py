"""Source and PyInstaller entry point for the independent desktop tool."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from occultation_media.launcher import main
if __name__=='__main__':
    main()
