import json
import os
from pathlib import Path
import tempfile

from .common import environment


def link(target, source):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        if target.resolve() == source.resolve():
            return
        target.unlink()
    elif target.exists():
        raise ValueError(f"Private SDK path is not a symlink: {target}")
    try:
        target.symlink_to(source, target_is_directory=source.is_dir())
    except FileExistsError:
        if not target.is_symlink() or target.resolve() != source.resolve():
            raise


def write(target, content):
    content = content.encode() if isinstance(content, str) else content
    if target.is_file() and target.read_bytes() == content:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
        temporary.write(content)
        name = temporary.name
    os.replace(name, target)


def prepare(state, manifest, root):
    data = manifest["lock"]
    revision = data["compiler"]["rev"]
    version = data["compiler"]["version"]
    for name in ("cache", "state/db", "user", "bin"):
        (state / name).mkdir(parents=True, exist_ok=True)
    collection = data["compiler"]["collection"]
    compiler = data["compiler"]
    toml = (
        "[idris2]\n"
        + "".join(
            key + "=" + json.dumps(compiler[key]) + "\n" for key in ("url", "version")
        )
        + "commit="
        + json.dumps(revision)
        + "\n"
    )
    for node in data["nodes"]:
        if node["type"] == "git":
            toml += (
                "\n[db."
                + node["name"]
                + ']\ntype="github"\nurl='
                + json.dumps(node["url"])
                + "\ncommit="
                + json.dumps(node["rev"])
                + "\nipkg="
                + json.dumps(node["ipkg"])
                + "\npackagePath=false\n"
            )
            cached = state / "cache" / node["name"] / node["rev"] / node["ipkg"]
            cached.parent.mkdir(parents=True, exist_ok=True)
            write(cached, node["content"])
            link(
                state / "state/install" / revision / node["name"] / node["hash"],
                Path(manifest["libraries"][node["name"]]) / "lib",
            )
    write(state / "state/db" / (collection + ".toml"), toml)
    write(state / "state/pack.toml", "collection=" + json.dumps(collection) + "\n")
    write(state / "user/pack.toml", "[install]\nwith-src=true\nwarn-depends=false\n")
    source = Path(manifest["compilerSource"])
    for name in (
        "prelude",
        "base",
        "linear",
        "network",
        "contrib",
        "test",
        "papers",
        "idris2",
    ):
        ipkg = "idris2api.ipkg" if name == "idris2" else name + ".ipkg"
        path = source / (ipkg if name == "idris2" else "libs/" + name + "/" + ipkg)
        target = state / "cache" / name / revision / ipkg
        target.parent.mkdir(parents=True, exist_ok=True)
        write(target, path.read_bytes())
    write(state / "cache/idris2" / revision / "version", version)
    prefix = state / "state/install" / revision / "idris2"
    link(prefix / "bin/idris2", Path(manifest["compiler"]) / "bin/idris2")
    libdir = prefix / ("idris2-" + version)
    libdir.mkdir(exist_ok=True)
    for library in manifest["coreLibraries"]:
        for item in (Path(library) / ("idris2-" + version)).iterdir():
            link(libdir / item.name, item)
    for name, folder in (("lib", "lib"), ("support", "share")):
        link(libdir / name, Path(manifest["support"]) / folder)
    paths = [
        str(Path(path) / ("lib/idris2-" + version))
        for path in manifest["libraries"].values()
    ] + [str(Path(path) / ("idris2-" + version)) for path in manifest["coreLibraries"]]
    return dict(
        environment(),
        PACK_PURIFIER_FROZEN="1",
        PACK_PURIFIER_ROOT=str(root),
        PACK_PURIFIER_ROOT_IPKG=(data["project"] or {}).get("ipkg", ""),
        PACK_PURIFIER_ROOT_NAME=(data["project"] or {}).get("name", ""),
        PACK_CACHE_DIR=str(state / "cache"),
        PACK_STATE_DIR=str(state / "state"),
        PACK_USER_DIR=str(state / "user"),
        PACK_BIN_DIR=str(state / "bin"),
        IDRIS2_PACKAGE_PATH=":".join(paths),
        IDRIS2_LIBS=str(Path(manifest["support"]) / "lib"),
        IDRIS2_DATA=str(Path(manifest["support"]) / "share"),
    )
