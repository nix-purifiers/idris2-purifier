import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .common import environment, inputs, load, run_pack


def configurations(root):
    return {
        os.path.relpath(parent / "pack.toml", root): (parent / "pack.toml").read_text()
        for parent in [root, *root.parents]
        if (parent / "pack.toml").is_file()
    }


def capture(root, companion, requirements=(), update=False, extra=(), ipkg=None):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = json.loads(companion.read_text()) if companion.exists() else {}
    requirements = list(requirements or previous.get("requirements", []))
    extra = list(extra or previous.get("extraInputs", []))
    ipkg = ipkg or (previous.get("project") or {}).get("ipkg")
    with tempfile.TemporaryDirectory(prefix="idris-capture-") as tmp:
        state = Path(tmp)
        captures = []
        project = None
        if ipkg is not None or list(root.glob("*.ipkg")):
            selected = run_pack(
                ["install-deps", *([ipkg] if ipkg else [])],
                root,
                state,
                PACK_PURIFIER_CAPTURE_ROOT="1",
            )
            project = selected["PURIFIER_PROJECT"]
            path = Path(project.pop("path")).resolve()
            if not path.is_relative_to(root):
                raise ValueError("The selected root ipkg must be in the project")
            project["ipkg"] = str(path.relative_to(root))
            captures.append(selected)
        for name in requirements or ([] if captures else ["base"]):
            captures.append(
                run_pack(["query", name], root, state, PACK_PURIFIER_CAPTURE=name)
            )
        compiler = captures[0]["PURIFIER_COMPILER"]
        if compiler["version"] != "0.8.0":
            raise ValueError(
                "The current Pack/LSP frontend supports Idris 0.8.0 collections"
            )
        nodes = {}
        for selected in captures:
            if (
                selected["PURIFIER_SETTINGS"]["applications"]
                or selected["PURIFIER_SETTINGS"]["documentation"]
            ):
                raise ValueError(
                    "Automatic application and documentation installation is outside this integration"
                )
            if selected["PURIFIER_COMPILER"] != compiler:
                raise ValueError("Native Pack selected inconsistent compilers")
            for node in selected["PURIFIER_GRAPH"]:
                if node["type"] not in ("core", "git"):
                    raise ValueError(
                        "Dependencies must be native curated Git packages or core libraries"
                    )
                if node["type"] == "core" and node["name"] not in (
                    "prelude",
                    "base",
                    "linear",
                    "network",
                    "contrib",
                    "test",
                ):
                    raise ValueError(
                        "This frontend currently supports the six standard runtime core libraries"
                    )
                if not re.fullmatch(r"[A-Za-z0-9_+-]+", node["name"]):
                    raise ValueError("Unsupported native package name")
                if node["name"] in nodes and nodes[node["name"]] != node:
                    raise ValueError(
                        "Native Pack selected inconsistent package metadata"
                    )
                nodes[node["name"]] = node
        entries = []

        def fetch(name, record):
            if not re.fullmatch(r"[a-f0-9]{40}", record["rev"]):
                raise ValueError(
                    "Native Pack must resolve Git references to exact commits"
                )
            result = subprocess.run(
                [
                    os.environ["IDRIS2_PURIFIER_PREFETCH_GIT"],
                    "--url",
                    record["url"],
                    "--rev",
                    record["rev"],
                ],
                env=environment(),
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise ValueError(result.stdout + result.stderr)
            fetched = json.loads(result.stdout)
            if fetched["rev"] != record["rev"]:
                raise ValueError(
                    "Git fetch revision differs from native Pack selection"
                )
            path = "sources/" + name
            entries.append(
                {
                    "path": path,
                    "hash": fetched["hash"],
                    "git": {
                        "url": record["url"],
                        "rev": record["rev"],
                        "submodules": False,
                        "leaveDotGit": False,
                        "commitObject": None,
                    },
                }
            )
            return path

        compiler["entry"] = fetch("compiler", compiler)
        for node in nodes.values():
            if node["type"] == "git":
                node["entry"] = fetch(node["name"], node)
        names = (
            extra
            + ([project["ipkg"]] if project else [])
            + (["pack.toml"] if (root / "pack.toml").exists() else [])
        )
        data = {
            "version": 1,
            "purifier": "idris2",
            "sdk": os.environ["IDRIS2_PURIFIER_SDK_VERSION"],
            "compiler": compiler,
            "project": project,
            "requirements": requirements,
            "extraInputs": extra,
            "inputs": inputs(root, names),
            "configurations": configurations(root),
            "nodes": sorted(nodes.values(), key=lambda n: n["name"]),
            "entries": sorted(entries, key=lambda e: e["path"]),
        }
        companion.parent.mkdir(parents=True, exist_ok=True)
        temporary = companion.with_suffix(companion.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        temporary.replace(companion)
