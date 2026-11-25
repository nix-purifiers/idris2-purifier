"""Exercise failures in the actual owning native JavaScript producer."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix="idris-js-controls-") as temporary:
    for case in ("preexisting-output", "foreign-backend", "stale-metadata"):
        source = Path(temporary) / case
        shutil.copytree(repo / "tests/fixtures/javascript", source,
                        ignore=shutil.ignore_patterns("build", ".idris2-purifier"))
        if case == "preexisting-output":
            (source / "proof.html").write_text("throw new Error('authored impostor');\n")
            expected = "executable already exists in the source tree"
        elif case == "foreign-backend":
            (source / "Main.idr").write_text('''module Main
%foreign "scheme:missingNativeSchemeOnly"
nativeOnly : PrimIO ()
main : IO ()
main = primIO nativeOnly
''')
            expected = "No supported backend found in the definition of Main.nativeOnly"
        else:
            with (source / "proof.ipkg").open("a") as stream:
                stream.write('-- stale authored metadata\n')
            expected = "Idris lock is missing, stale or unsupported"
        core = os.environ.get("IDRIS_TEST_CORE_SOURCE")
        override = (".override { purifier = import (/. + " + json.dumps(core) +
                    ' + "/nix/lib") { inherit (p) lib; }; }') if core else ""
        expression = f'''let
          f = builtins.getFlake {json.dumps(str(repo))};
          p = import f.inputs.nixpkgs {{ system = builtins.currentSystem; overlays = [ f.overlays.default ]; }};
          builder = p.idris2-purifier.buildIdrisProject{override};
        in (builder {{ src = /. + {json.dumps(str(source))};
          javascriptTargets.proof = "node"; }}).javascriptPackages.proof'''
        result = subprocess.run(["nix", "build", "--impure", "--no-link", "-L",
                                 "--expr", expression], text=True, capture_output=True)
        assert result.returncode != 0, (case, "unexpected success")
        if expected:
            assert expected in result.stderr, (case, result.stderr)
        else:
            assert "Main.idr" in result.stderr, (case, result.stderr)
        print(json.dumps({"case": case, "exitCode": result.returncode,
                          "diagnostic": result.stderr}))
