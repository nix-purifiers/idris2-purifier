"""Compare source metadata using Pack's native parser, without config or fetching."""

import json
import os
from pathlib import Path
import subprocess
import sys

pack, source, expected = sys.argv[1:]
env = {k: v for k, v in os.environ.items() if not k.startswith(("IDRIS", "PACK_"))}
env["PACK_PURIFIER_METADATA"] = str(Path(source).resolve())
result = subprocess.run([pack, "help"], env=env, capture_output=True, text=True)
if result.returncode:
    raise SystemExit(result.stdout + result.stderr)
actual = json.loads(
    next(
        line.split("=", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("PURIFIER_PROJECT=")
    )
)
expected = json.loads(Path(expected).read_text())
keys = ("name", "version", "content", "dependencies", "executable")
if {key: actual.get(key) for key in keys} != {key: expected.get(key) for key in keys}:
    raise SystemExit("Native Idris package metadata differs from the lock")
