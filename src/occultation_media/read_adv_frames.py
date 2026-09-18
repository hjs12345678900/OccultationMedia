"""Bridge the platform-dependent ADV decoder to NumPy rendering safely."""
from pathlib import Path
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import numpy as np
from .platform_runtime import hidden_process_options


class AdvSource:
    """Read ADV2 using an isolated Python, with automatic macOS Intel fallback.

    `python` optionally names a compatible executable. The worker reads only
    requested zero-based main-stream indices; raw temporary files are deleted.
    """
    def __init__(self, path, python=None):
        self.path = Path(path).resolve()
        candidates = [python] if python else [sys.executable]
        if not python and platform.system() == 'Darwin' and platform.machine() == 'arm64':
            candidates += [str(p) for p in (Path('/usr/local/bin/python3-intel64'),) if p.exists()]
        self.env = dict(os.environ)
        spec = importlib.util.find_spec('Adv2')
        if spec and spec.origin:
            parent = str(Path(spec.origin).parent.parent)
            self.env['PYTHONPATH'] = os.pathsep.join(filter(None,[parent,self.env.get('PYTHONPATH','')]))
        errors = []
        for executable in candidates:
            self.executable = executable
            try:
                self.metadata = self._decode([], None)
                self.count = self.metadata['count']
                return
            except RuntimeError as error:
                errors.append(str(error))
        raise RuntimeError('ADV decoder unavailable. Install Adv2 and, on Apple Silicon, Rosetta plus Intel Python; pass --adv-python if needed.\n'+'\n'.join(errors))

    def _decode(self, indices, output_dir):
        request = {'source':str(self.path),'indices':indices,'output_dir':output_dir}
        if getattr(sys, 'frozen', False):
            # A windowed Windows build has no Python stdin/stdout. Exchange
            # JSON files rather than depending on console streams.
            with tempfile.TemporaryDirectory(prefix='adv-request-') as directory:
                req, res = Path(directory)/'request.json', Path(directory)/'result.json'
                req.write_text(json.dumps(request))
                result = subprocess.run([sys.executable,'--adv-worker',str(req),str(res)],
                                        capture_output=True,**hidden_process_options())
                if result.returncode or not res.exists():
                    detail = res.read_text() if res.exists() else str(result.stderr[-2000:])
                    raise RuntimeError('Bundled ADV decoder failed: '+detail)
                return json.loads(res.read_text())
        worker = Path(__file__).with_name('decode_adv_worker.py')
        result = subprocess.run([self.executable,str(worker)],input=json.dumps(request),
                                text=True,capture_output=True,env=self.env,**hidden_process_options())
        if result.returncode:
            raise RuntimeError(result.stderr[-2500:])
        try:
            return json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as error:
            raise RuntimeError('ADV worker did not return valid metadata') from error

    def read_many(self, indices):
        """Return index -> (uint32 (y,x) detector array, native time metadata)."""
        with tempfile.TemporaryDirectory(prefix='occultation-adv-') as directory:
            result = self._decode(list(indices),directory)
            shape = (result['height'],result['width'])
            return {r['source_index']:(np.fromfile(Path(directory,f"{r['source_index']}.raw"),'<u4').reshape(shape),r)
                    for r in result['frames']}

    def read(self,index):
        """Decode one zero-based main-stream index; use read_many for batches."""
        return self.read_many([index])[index]
