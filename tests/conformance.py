"""Native Pack/compiler/editor, mutable source, frozen caches and native publication."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from editor import check as check_editor

repo = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.check_output(
            ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"],
            text=True,
        ).strip()
    )
    / "bin"
)


def run(args, root, expected=0, **kwargs):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=root, capture_output=True, text=True, **kwargs
    )
    assert result.returncode == expected, (
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    return result


with tempfile.TemporaryDirectory(prefix="idris-conformance-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project with spaces"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns("build", ".idris2-purifier"),
    )
    env = dict(
        os.environ,
        IDRIS2_PREFIX=str(temporary / "poison"),
        IDRIS2_PACKAGE_PATH=str(temporary / "poison"),
        PACK_USER_DIR=str(temporary / "poison"),
        PACK_STATE_DIR=str(temporary / "poison"),
    )
    assert run([cli / "pack", "run"], root, env=env).stdout.strip() == "42"
    assert (
        run([cli / "pack", "run", "purifierproof"], root, env=env).stdout.strip()
        == "42"
    )
    run([cli / "idris2", "--build", "proof.ipkg"], root, env=env)
    assert run([root / "build/exec/proof"], root).stdout.strip() == "42"
    profile = root / ".idris2-purifier/environment-profile"
    manifest = json.loads(
        (
            Path(json.loads(profile.resolve().read_text())["output"]) / "manifest.json"
        ).read_text()
    )
    package_dir = (
        Path(manifest["libraries"]["refined"]) / "lib/idris2-0.8.0/refined-0.1.0"
    )
    poisoned = root / "depends/refined-99.0.0"
    shutil.copytree(package_dir, poisoned)
    for file in poisoned.rglob("*"):
        file.chmod(file.stat().st_mode | 0o200)
    metadata = next(poisoned.glob("*.ipkg"))
    metadata.write_text(metadata.read_text().replace("0.1.0", "99.0.0"))
    packages = run([cli / "idris2", "--list-packages"], root, env=env)
    assert (
        "refined (0.1.0)" in packages.stdout
        and "refined (99.0.0)" not in packages.stdout
    ), packages
    run([cli / "idris2", "--build", "proof.ipkg"], root, env=env)
    check_editor(cli, root, env)
    source = root / "Main.idr"
    original = source.read_text()
    source.write_text(original.replace("answer = 42", "answer = 43"))
    changed = run([cli / "pack", "run"], root, env=env)
    assert changed.stdout.strip().splitlines()[-1] == "43", changed
    source.write_text(original)
    restored = run([cli / "pack", "run"], root, env=env)
    assert restored.stdout.strip().splitlines()[-1] == "42", restored
    missing = run(
        [cli / "pack", "install", "purifier_absent"], root, expected=1, env=env
    )
    assert "Unknown package" in missing.stdout
    ipkg = root / "proof.ipkg"
    saved = ipkg.read_text()
    ipkg.write_text(saved + "\n")
    stale = run([cli / "idris2", "--version"], root, expected=1, env=env)
    assert "inputs changed" in stale.stderr
    ipkg.write_text(saved)
    companion = temporary / "external.json"
    (root / "idris2-purifier.lock.json").rename(companion)
    external = dict(
        env, IDRIS2_PURIFIER_PROJECT=str(root), IDRIS2_PURIFIER_LOCK=str(companion)
    )
    nested = root / "nested"
    nested.mkdir()
    run([cli / "idris2", "--build", "../proof.ipkg"], nested, env=external)
    references = subprocess.check_output(
        ["nix-store", "-q", "--requisites", profile.resolve()], text=True
    )
    assert "idris2-purifier-" in references and "refined-0.1.0" in references
    fallback = temporary / "fallback"
    fallback.mkdir()
    ordinary = run([cli / "idris2", "--version"], fallback)
    assert "version 0.8.0" in ordinary.stdout and "impure" in ordinary.stderr
    streams = run(
        [
            cli / "idris2-purifier",
            "exec",
            "--project",
            fallback,
            "--",
            "python3",
            "-c",
            "import sys;print(sys.stdin.read().strip());print('native-stderr',file=sys.stderr);sys.exit(7)",
        ],
        fallback,
        expected=7,
        input="native-stdin\n",
    )
    assert (
        streams.stdout.strip() == "native-stdin"
        and "native-stderr" in streams.stderr
        and "impure" in streams.stderr
    )
    artifacts = Path(
        run(
            [cli / "idris2-purifier", "bundle", "--project", root, "--lock", companion],
            root,
        ).stdout.strip()
    )
    (archive,) = artifacts.glob("*.tar.gz")
    with tarfile.open(archive) as bundle:
        assert all(
            "depends" not in Path(name).parts and ".idris2-purifier" not in name
            for name in bundle.getnames()
        )
    fake = temporary / "fake-gh"
    record = temporary / "publication.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport hashlib,json,os,pathlib,sys\npathlib.Path(os.environ['PUBLICATION_RECORD']).write_text(json.dumps({'args':sys.argv[1:],'hash':hashlib.sha256(pathlib.Path(sys.argv[4]).read_bytes()).hexdigest()}))\n"
    )
    fake.chmod(0o755)
    run(
        [
            cli / "idris2-purifier",
            "publish",
            "--tag",
            "v0.1.0",
            "--project",
            root,
            "--lock",
            companion,
        ],
        root,
        env=dict(
            os.environ, IDRIS2_PURIFIER_GH=str(fake), PUBLICATION_RECORD=str(record)
        ),
    )
    assert json.loads(record.read_text()) == {
        "args": ["release", "upload", "v0.1.0", str(archive), "--clobber"],
        "hash": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    # Ordinary compiler consumes the source artifact with an explicitly supplied dependency environment.
    consumer = temporary / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(consumer, filter="data")
    consumer = consumer / "project"
    (consumer / "idris2-purifier.lock.json").unlink(missing_ok=True)
    paths = [
        str(Path(path) / "lib/idris2-0.8.0") for path in manifest["libraries"].values()
    ] + [str(Path(path) / "idris2-0.8.0") for path in manifest["coreLibraries"]]
    ordinary_env = dict(
        os.environ,
        IDRIS2_PACKAGE_PATH=os.pathsep.join(paths),
        IDRIS2_LIBS=str(Path(manifest["support"]) / "lib"),
        IDRIS2_DATA=str(Path(manifest["support"]) / "share"),
    )
    consumed = run(
        [cli / "idris2", "--build", "proof.ipkg"], consumer, env=ordinary_env
    )
    assert "impure" in consumed.stderr
    assert run([consumer / "build/exec/proof"], consumer).stdout.strip() == "42"

print(
    "Native Idris/Pack/LSP, source edits, frozen caches and ordinary source consumption passed"
)
