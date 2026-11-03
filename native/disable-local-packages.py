"""Bind the scoped compiler/API's local package lookup to an immutable empty tree."""

from pathlib import Path
import sys

source, directory = sys.argv[1:]
path = Path(source) / "src/Core/Directory.idr"
text = path.read_text()
start = text.index("pkgLocalDirectory =\n")
end = text.index(
    "\n------------------------------------------------------------------------", start
)
text = text[:start] + 'pkgLocalDirectory = pure "' + directory + '"\n' + text[end:]
path.write_text(text)
