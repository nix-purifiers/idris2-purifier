"""Native selection stability, tracked inputs, metadata binding and intrinsic-only graphs."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.check_output(
            ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"],
            text=True,
        ).strip()
    )
    / "bin/idris2-purifier"
)


def call(root, companion, *args, expected=0):
    result = subprocess.run(
        [cli, *args, "--project", root, "--lock", companion],
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected, (
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    return result


with tempfile.TemporaryDirectory(prefix="idris-capture-proof-") as tmp:
    tmp = Path(tmp)
    root = tmp / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns("build", ".idris2-purifier"),
    )
    companion = tmp / "external.json"
    (root / "idris2-purifier.lock.json").rename(companion)
    original = companion.read_bytes()
    call(root, companion, "lock")
    assert companion.read_bytes() == original
    (root / "selection.txt").write_text("Tracked selection\n")
    call(root, companion, "lock", "--update", "--input", "selection.txt")
    selected = json.loads(companion.read_text())
    assert (
        selected["extraInputs"] == ["selection.txt"]
        and selected["compiler"]["collection"] == "nightly-261102"
    )
    assert {n["name"] for n in selected["nodes"] if n["type"] == "git"} == {
        "algebra",
        "elab-util",
        "refined",
    }
    call(root, companion, "prefetch")
    selected["project"]["version"] = "999.0.0"
    companion.write_text(json.dumps(selected))
    assert (
        "root metadata differs" in call(root, companion, "prefetch", expected=1).stderr
    )
    selected["project"]["version"] = "0.1.0"
    next(n for n in selected["nodes"] if n["type"] == "git")["version"] = "999.0.0"
    companion.write_text(json.dumps(selected))
    assert "metadata differs" in call(root, companion, "prefetch", expected=1).stderr
    empty = tmp / "intrinsics"
    empty.mkdir()
    (empty / "pack.toml").write_text('collection="nightly-261102"\n')
    empty_lock = empty / "idris2-purifier.lock.json"
    call(empty, empty_lock, "lock")
    intrinsic = json.loads(empty_lock.read_text())
    assert intrinsic["project"] is None and all(
        n["type"] == "core" for n in intrinsic["nodes"]
    )
    assert len(intrinsic["entries"]) == 1
    call(empty, empty_lock, "prefetch")
    full_profile = json.loads(
        (root / ".idris2-purifier/environment-profile").resolve().read_text()
    )
    empty_profile = json.loads(
        (empty / ".idris2-purifier/environment-profile").resolve().read_text()
    )
    full = json.loads((Path(full_profile["output"]) / "manifest.json").read_text())
    baseline = json.loads((Path(empty_profile["output"]) / "manifest.json").read_text())
    assert full["compiler"] == baseline["compiler"], (
        "Unrelated library graphs must not rebuild the compiler"
    )

    (empty / "src").mkdir()
    (empty / "test").mkdir()
    (empty / "src/Library.idr").write_text(
        "module Library\nimport Data.Refined.Nat\npublic export\nanswer : Nat\nanswer = 42\n"
    )
    (empty / "library.ipkg").write_text(
        'package rootlibrary\nversion = 0.1.0\ndepends = refined\nsourcedir = "src"\nmodules = Library\n'
    )
    (empty / "test/test.ipkg").write_text(
        "package rootlibrary-test\ndepends = rootlibrary\nmodules = Main\nmain = Main\nexecutable = test\n"
    )
    (empty / "test/Main.idr").write_text(
        "module Main\nimport Library\nmain : IO ()\nmain = printLn answer\n"
    )
    (empty / "pack.toml").write_text(
        'collection="nightly-261102"\n[custom.all.rootlibrary]\ntype="local"\npath="."\nipkg="library.ipkg"\ntest="test/test.ipkg"\n'
    )
    call(empty, empty_lock, "lock", "--update", "--input", "test/test.ipkg")
    native = subprocess.run(
        [cli.parent / "pack", "test", "rootlibrary"],
        cwd=empty,
        capture_output=True,
        text=True,
    )
    assert native.returncode == 0 and native.stdout.strip().splitlines()[-1] == "42", (
        native
    )
    library_file = empty / "src/Library.idr"
    library_file.write_text(
        library_file.read_text().replace("answer = 42", "answer = 43")
    )
    changed = subprocess.run(
        [cli.parent / "pack", "test", "rootlibrary"],
        cwd=empty,
        capture_output=True,
        text=True,
    )
    assert (
        changed.returncode == 0 and changed.stdout.strip().splitlines()[-1] == "43"
    ), changed
    library_file.write_text(
        library_file.read_text().replace("answer = 43", "answer = 42")
    )
    restored = subprocess.run(
        [cli.parent / "pack", "test", "rootlibrary"],
        cwd=empty,
        capture_output=True,
        text=True,
    )
    assert (
        restored.returncode == 0 and restored.stdout.strip().splitlines()[-1] == "42"
    ), restored
    expression = f"let f=builtins.getFlake {json.dumps(str(repo))};p=import f.inputs.nixpkgs {{overlays=[f.overlays.default];}};b=p.idris2-purifier.buildIdrisProject {{src=/. + {json.dumps(str(empty))};}};in b.packages.project"
    library = Path(
        subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--no-link",
                "--print-out-paths",
            ],
            text=True,
        ).strip()
    )
    assert list(library.rglob("Library.ttc")) and list(library.rglob("Library.idr"))

print(
    "Native Idris selection, library tests, metadata rejection and compiler reuse passed"
)
