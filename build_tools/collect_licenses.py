"""Preserve installed third-party license texts in the shipped resources."""
from importlib import metadata
from pathlib import Path
import shutil


def collect(root):
    destination=root/'src/occultation_media/assets/licenses';destination.mkdir(parents=True,exist_ok=True)
    for dist in metadata.distributions():
        name=dist.metadata.get('Name','unknown')
        for file in dist.files or []:
            if any(token in file.name.lower() for token in ('license','licence','copying','notice')):
                source=Path(dist.locate_file(file))
                if source.is_file() and source.suffix.lower() not in ('.py','.pyc','.so','.dll'):
                    target=destination/name/str(file).replace('/','_');target.parent.mkdir(exist_ok=True)
                    shutil.copy2(source,target)
    for name in ('README.md','THIRD_PARTY.md'):
        shutil.copy2(root/name,destination/name)
