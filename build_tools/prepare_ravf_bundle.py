"""Stage ravf 1.0.1 with optional OpenCV imports deferred for raw-frame use.

Keep upstream container parsing and pixel utility implementations unchanged.
Only debayer helpers need OpenCV; this application's raw-frame path never calls
those helpers. The source install can still use OpenCV, while the frozen app
excludes it. Preserve the upstream distribution and license in the bundle.
"""
from importlib.util import find_spec
from pathlib import Path
import ast
import shutil


def prepare(root):
    """Return staging import root after checking and deferring cv2 imports."""
    source = Path(find_spec('ravf').origin).parent
    vendor = root / 'build_vendor'
    target = vendor / 'ravf'
    shutil.copytree(source, target, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    path = target / 'ravf_image_utils.py'
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    imports = [node for node in tree.body if isinstance(node, ast.Import)
               and any(alias.name == 'cv2' for alias in node.names)]
    if len(imports) != 1 or len(imports[0].names) != 1:
        raise ValueError('Unexpected ravf cv2 import; review upstream before packaging')
    lines = text.splitlines(keepends=True)
    insertions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and any(
                isinstance(child, ast.Name) and child.id == 'cv2'
                for child in ast.walk(node)):
            first = node.body[0]
            insertions.append((first.lineno-1, ' ' * first.col_offset + 'import cv2\n'))
    if len(insertions) != 5:
        raise ValueError('Unexpected ravf debayer helpers; review upstream before packaging')
    for index, line in sorted(insertions, reverse=True):
        lines.insert(index, line)
    del lines[imports[0].lineno-1]
    path.write_text(''.join(lines), encoding='utf-8')
    ast.parse(path.read_text(encoding='utf-8'))
    return vendor
