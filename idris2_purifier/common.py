import hashlib
import json
import os
from pathlib import Path
import subprocess


def environment():
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("IDRIS", "PACK_"))
        and k
        not in (
            "LD_LIBRARY_PATH",
            "DYLD_LIBRARY_PATH",
            "C_INCLUDE_PATH",
            "CPLUS_INCLUDE_PATH",
            "LIBRARY_PATH",
        )
    }


def inputs(root, names):
    result = {}
    for name in sorted(set(names)):
        path = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or not path.is_file()
            or path.is_symlink()
        ):
            raise ValueError("Selection inputs must be regular project files")
        result[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "idris2":
        raise ValueError("Unsupported Idris lock")
    if data["sdk"] != os.environ["IDRIS2_PURIFIER_SDK_VERSION"]:
        raise ValueError("Pack frontend SDK changed; update the lock")
    names = (
        data["extraInputs"]
        + ([data["project"]["ipkg"]] if data["project"] else [])
        + (["pack.toml"] if (root / "pack.toml").exists() else [])
    )
    if data["inputs"] != inputs(root, names):
        raise ValueError("Selection inputs changed; update the lock")
    from .capture import configurations

    if data["configurations"] != configurations(root):
        raise ValueError("Pack project configuration changed; update the lock")
    if data["project"] is not None:
        env = dict(
            environment(), PACK_PURIFIER_METADATA=str(root / data["project"]["ipkg"])
        )
        result = subprocess.run(
            [os.environ["IDRIS2_PURIFIER_NATIVE_PACK"], "help"],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
        actual = json.loads(
            next(
                line.split("=", 1)[1]
                for line in result.stdout.splitlines()
                if line.startswith("PURIFIER_PROJECT=")
            )
        )
        actual.pop("path")
        actual["ipkg"] = data["project"]["ipkg"]
        if actual != data["project"]:
            raise ValueError("Native root metadata differs from the lock")
    elif list(root.glob("*.ipkg")):
        raise ValueError("Project metadata changed; update the lock")
    return data


def run_pack(args, root, state, **flags):
    for name in ("cache", "state", "user", "bin"):
        (state / name).mkdir(parents=True, exist_ok=True)
    env = dict(
        environment(),
        PACK_CACHE_DIR=str(state / "cache"),
        PACK_STATE_DIR=str(state / "state"),
        PACK_USER_DIR=str(state / "user"),
        PACK_BIN_DIR=str(state / "bin"),
        **flags,
    )
    result = subprocess.run(
        [os.environ["IDRIS2_PURIFIER_NATIVE_PACK"], "--no-prompt", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    records = {
        line.split("=", 1)[0]: json.loads(line.split("=", 1)[1])
        for line in result.stdout.splitlines()
        if line.startswith("PURIFIER_")
    }
    if "PURIFIER_GRAPH" not in records or "PURIFIER_COMPILER" not in records:
        raise ValueError("Native Pack did not export a dependency graph")
    return records
