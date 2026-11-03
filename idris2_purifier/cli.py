import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .capture import capture
from .common import load
from .runtime import prepare as prepare_runtime


def locate(project=None, companion=None):
    root = Path(
        project or os.environ.get("IDRIS2_PURIFIER_PROJECT", Path.cwd())
    ).resolve()
    external = companion or os.environ.get("IDRIS2_PURIFIER_LOCK")
    if external:
        return root, Path(external).resolve()
    if project or os.environ.get("IDRIS2_PURIFIER_PROJECT"):
        return root, root / "idris2-purifier.lock.json"
    for parent in [root, *root.parents]:
        if (parent / "idris2-purifier.lock.json").exists():
            return parent, parent / "idris2-purifier.lock.json"
    return root, root / "idris2-purifier.lock.json"


def realize(root, companion, target="environment"):
    state = root / ".idris2-purifier"
    state.mkdir(exist_ok=True)
    generation = hashlib.sha256(
        companion.read_bytes() + os.environ["IDRIS2_PURIFIER_SDK"].encode()
    ).hexdigest()[:20]
    profile = state / (target + "-" + generation + "-profile")
    result = subprocess.run(
        [
            "nix",
            "build",
            "--impure",
            "--file",
            str(Path(__file__).parent.parent / "nix/realize.nix"),
            "--argstr",
            "project",
            str(root),
            "--argstr",
            "companion",
            str(companion),
            "--argstr",
            "target",
            target,
            "--argstr",
            "sdk",
            os.environ["IDRIS2_PURIFIER_SDK"],
            "--arg",
            "profile",
            "true",
            "--out-link",
            str(profile),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    temporary = Path(tempfile.mktemp(prefix="profile-", dir=state))
    temporary.symlink_to(profile.name)
    temporary.replace(state / (target + "-profile"))
    return Path(json.loads(profile.resolve().read_text())["output"])


def prepare(root, companion):
    load(root, companion)
    output = realize(root, companion)
    manifest = json.loads((output / "manifest.json").read_text())
    key = hashlib.sha256(
        (str(root) + str(output) + os.environ["IDRIS2_PURIFIER_SDK"]).encode()
    ).hexdigest()[:20]
    state = root / ".idris2-purifier" / key
    return prepare_runtime(state, manifest, root), manifest


def execute(args, root, companion, native=False):
    originals = {
        "idris2": "IDRIS2_PURIFIER_ORIGINAL_IDRIS",
        "pack": "IDRIS2_PURIFIER_ORIGINAL_PACK",
        "idris2-lsp": "IDRIS2_PURIFIER_ORIGINAL_LSP",
    }
    if not companion.exists():
        print(
            "idris2-purifier: no lockfile; using ordinary impure resolution",
            file=sys.stderr,
        )
        if native:
            program = os.environ[originals[native]]
            os.execv(program, [program, *args])
        os.execvp(args[0], args)
    env, manifest = prepare(root, companion)
    if native:
        program = (
            str(Path(manifest["compiler"]) / "bin/idris2")
            if native == "idris2"
            else os.environ[
                "IDRIS2_PURIFIER_NATIVE_PACK"
                if native == "pack"
                else "IDRIS2_PURIFIER_NATIVE_LSP"
            ]
        )
        os.execve(program, [program, *args], env)
    env["PATH"] = (
        str(Path(sys.argv[0]).resolve().parent) + os.pathsep + env.get("PATH", "")
    )
    env["IDRIS2_PURIFIER_PROJECT"] = str(root)
    env["IDRIS2_PURIFIER_LOCK"] = str(companion)
    os.execvpe(args[0], args, env)


def main():
    try:
        args = sys.argv[1:]
        if args and args[0] in (
            "--native=idris2",
            "--native=pack",
            "--native=idris2-lsp",
        ):
            root, companion = locate()
            execute(args[1:], root, companion, native=args[0].split("=", 1)[1])
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "command", choices=["lock", "prefetch", "exec", "bundle", "publish"]
        )
        parser.add_argument("requirements", nargs="*")
        parser.add_argument("--project", type=Path)
        parser.add_argument("--lock", type=Path)
        parser.add_argument("--update", action="store_true")
        parser.add_argument("--input", action="append", default=[])
        parser.add_argument("--tag")
        parser.add_argument("--ipkg")
        passthrough = []
        if "--" in args:
            index = args.index("--")
            passthrough, args = args[index + 1 :], args[:index]
        selected = parser.parse_args(args)
        root, companion = locate(selected.project, selected.lock)
        if selected.command == "lock":
            capture(
                root,
                companion,
                selected.requirements,
                selected.update,
                selected.input,
                selected.ipkg,
            )
        elif selected.command == "exec":
            if not passthrough:
                raise ValueError("exec requires a command after --")
            execute(passthrough, root, companion)
        else:
            load(root, companion)
            output = realize(
                root,
                companion,
                "environment" if selected.command == "prefetch" else "release",
            )
            if selected.command == "publish":
                if not selected.tag:
                    raise ValueError("publish requires --tag")
                subprocess.run(
                    [
                        os.environ["IDRIS2_PURIFIER_GH"],
                        "release",
                        "upload",
                        selected.tag,
                        *map(str, sorted(output.iterdir())),
                        "--clobber",
                    ],
                    check=True,
                )
            else:
                print(output)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"idris2-purifier: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
