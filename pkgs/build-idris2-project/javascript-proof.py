"""Bind installed bytes to the actual native compiler output and authored inputs."""

import hashlib
import json
from pathlib import Path
import sys

source, emitted, installed, compiler, backend, output = sys.argv[1:]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert Path(emitted).is_file() and not Path(emitted).is_symlink()
assert Path(emitted).read_bytes() == Path(installed).read_bytes()
inputs = {}
for original in sorted(Path(source).rglob("*")):
    if original.is_file():
        relative = original.relative_to(source)
        assert original.read_bytes() == Path(relative).read_bytes(), relative
        inputs[str(relative)] = digest(original)
Path(output).write_text(json.dumps({
    "backend": backend,
    "compiler": compiler,
    "compilerExecutableSha256": digest(Path(compiler) / "bin/idris2"),
    "authoredInputs": inputs,
    "nativeOutputSha256": digest(Path(emitted)),
    "installedOutputSha256": digest(Path(installed)),
}, sort_keys=True, indent=2) + "\n")
