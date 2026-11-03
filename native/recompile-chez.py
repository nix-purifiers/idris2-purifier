"""Use a source-derived Chez session key for native program compilation."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

scheme = sys.argv[1]
for driver in Path.cwd().rglob("compileChez*"):
    if not driver.is_file():
        continue
    command = driver.read_text()
    match = re.search(r'\(compile-(?:program|file)\s+("(?:[^"\\]|\\.)*")', command)
    if match is None:
        raise SystemExit(f"Unsupported native Chez compiler driver: {driver}")
    source = Path(json.loads(match.group(1)))
    key = "purifier" + hashlib.sha256(source.read_bytes()).hexdigest() + "-"
    # Chez's internal setter is also used by Debian's reproducible boot build.
    # Hashing this compilation unit keeps unrelated units in distinct namespaces.
    driver.write_text(
        "(#%$set-top-level-value! '$session-key " + json.dumps(key) + ")\n" + command
    )
    subprocess.run([scheme, "--script", str(driver)], check=True)
