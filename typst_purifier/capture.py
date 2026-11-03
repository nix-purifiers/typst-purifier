"""Capture the exact package archives selected by the native compiler."""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
import tomllib

from .common import environment, inputs, load, package, relative, run


def file_tree(root):
    result = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Package symlinks are outside the current scope")
        if path.is_file():
            result[str(path.relative_to(root))] = (
                path.read_bytes(),
                bool(path.stat().st_mode & 0o111),
            )
    return result


def capture(root, companion, document=None, update=False, extra=(), defines=()):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = {}
    if companion.exists() and update:
        try:
            previous = json.loads(companion.read_text())
            if not isinstance(previous, dict):
                previous = {}
        except (ValueError, AttributeError):
            pass
    document = document or previous.get("document", "main.typ")
    extra = extra or previous.get("extraInputs", [])
    defines = defines or previous.get("defines", [])
    tracked = inputs(root, extra)
    if not relative(document) or not (root / document).is_file():
        raise ValueError("Select a Typst document inside the project")
    with tempfile.TemporaryDirectory(prefix="typst-capture-") as temporary:
        temporary = Path(temporary)
        cache, archives, home, local = [
            temporary / n for n in ["cache", "archives", "home", "local"]
        ]
        for directory in [cache, archives, home, local]:
            directory.mkdir()
        env = environment()
        env.update(
            HOME=str(home),
            XDG_CACHE_HOME=str(home / "cache"),
            XDG_DATA_HOME=str(home / "data"),
            TYPST_PACKAGE_PATH=str(local),
            TYPST_PACKAGE_CACHE_PATH=str(cache),
            TYPST_PURIFIER_CAPTURE=str(archives),
        )
        options = [x for define in defines for x in ["--input", define]]
        deps_file = temporary / "dependencies.json"
        run(
            [
                os.environ["TYPST_PURIFIER_NATIVE_TYPST"],
                "compile",
                "--ignore-system-fonts",
                *options,
                "--deps",
                deps_file,
                document,
                temporary / "document.pdf",
            ],
            cwd=root,
            env=env,
        )
        entries, nodes = [], []
        for metadata in sorted(archives.glob("*.json")):
            node = json.loads(metadata.read_text())
            if (
                node["namespace"] != "preview"
                or not re.fullmatch(r"[a-z0-9-]+", node["name"])
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", node["version"])
            ):
                raise ValueError("Unsupported native Typst package coordinates")
            archive = metadata.with_suffix(".gz")
            extracted = temporary / "sources" / node["name"] / node["version"]
            extracted.mkdir(parents=True)
            with tarfile.open(archive) as stream:
                stream.extractall(extracted, filter="data")
            native = cache / node["namespace"] / node["name"] / node["version"]
            if file_tree(native) != file_tree(extracted):
                raise ValueError(
                    "Native Typst cache differs from its retained package archive"
                )
            info = tomllib.loads((native / "typst.toml").read_text())["package"]
            if info["name"] != node["name"] or info["version"] != node["version"]:
                raise ValueError(
                    "Native Typst package identity differs from its archive"
                )
            node["entrypoint"] = info["entrypoint"]
            node["entry"] = f"archives/{node['name']}/{node['version']}.tar.gz"
            nodes.append(node)
            digest = base64.b64encode(
                hashlib.sha256(archive.read_bytes()).digest()
            ).decode()
            entries.append(
                {
                    "path": node["entry"],
                    "url": node["url"],
                    "hash": "sha256-" + digest,
                    "mirrors": [],
                }
            )
        native_deps = json.loads(deps_file.read_text())["inputs"]
        selected = {
            str(p.relative_to(cache).parts[:3])
            for p in (Path(x) for x in native_deps)
            if p.is_absolute() and p.is_relative_to(cache)
        }
        retained = {str((n["namespace"], n["name"], n["version"])) for n in nodes}
        if selected != retained:
            raise ValueError(
                "Native Typst dependency report and retained archives differ"
            )
        data = {
            "version": 1,
            "purifier": "typst",
            "sdk": os.environ["TYPST_PURIFIER_SDK_VERSION"],
            "document": document,
            "defines": list(defines),
            "package": package(root),
            "extraInputs": list(extra),
            "inputs": tracked,
            "entries": entries,
            "nodes": nodes,
        }
        companion.parent.mkdir(parents=True, exist_ok=True)
        pending = companion.with_suffix(companion.suffix + ".tmp")
        pending.write_text(json.dumps(data, indent=2) + "\n")
        pending.replace(companion)
