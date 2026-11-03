"""Locked package selection and native Typst process environment."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tomllib

HERE = Path(__file__).resolve().parent.parent
LOCK = "typst-purifier.lock.json"


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("TYPST_"):
            env.pop(key, None)
    env.update(TYPST_IGNORE_SYSTEM_FONTS="true", SOURCE_DATE_EPOCH="315532800")
    return env


def relative(name):
    return bool(name) and not Path(name).is_absolute() and ".." not in Path(name).parts


def inputs(root, extra=()):
    names = sorted(
        set([*(["typst.toml"] if (root / "typst.toml").exists() else []), *extra])
    )
    result = {}
    for name in names:
        path = root / name
        if not relative(name) or path.resolve() != path or not path.is_file():
            raise ValueError(
                "Configuration inputs must be regular files inside the project"
            )
        blob = path.read_bytes()
        result[name] = {
            "content": blob.decode(),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }
    return result


def package(root):
    manifest = root / "typst.toml"
    if not manifest.exists():
        return None
    metadata = tomllib.loads(manifest.read_text())["package"]
    return {k: metadata[k] for k in ["name", "version", "entrypoint"]}


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "typst":
        raise ValueError("Invalid Typst lock")
    if data.get("sdk") != os.environ["TYPST_PURIFIER_SDK_VERSION"]:
        raise ValueError("Typst SDK changed; run typst-purifier lock --update")
    if data["inputs"] != inputs(root, data.get("extraInputs", [])) or data[
        "package"
    ] != package(root):
        raise ValueError(
            "Typst package metadata changed; run typst-purifier lock --update"
        )
    if not relative(data["document"]) or not (root / data["document"]).is_file():
        raise ValueError("Locked Typst document is missing")
    return data


def locate():
    selected = os.environ.get("TYPST_PURIFIER_LOCK")
    if selected:
        companion = Path(selected).resolve()
        return Path(
            os.environ.get("TYPST_PURIFIER_PROJECT", companion.parent)
        ).resolve(), companion
    root = next(
        (p for p in (Path.cwd(), *Path.cwd().parents) if (p / LOCK).exists()),
        Path.cwd(),
    )
    return root, root / LOCK
