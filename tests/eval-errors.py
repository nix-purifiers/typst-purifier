"""Validate the lock protocol without import-from-derivation."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".typst-purifier", "*.pdf"),
    )
    companion = root / "typst-purifier.lock.json"
    original = json.loads(companion.read_text())

    def inspect():
        expression = f"let f=builtins.getFlake {json.dumps(str(repo))};lock=f.lib.typst-purifier.readLock {{src=/. + {json.dumps(str(root))};}};in {{inherit(lock)problems outputs;fetches=map(e: e.path)lock.entries;}}"
        return json.loads(
            subprocess.check_output(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                text=True,
            )
        )

    valid = inspect()
    assert valid["problems"] == [] and valid["outputs"]["packages"] == [
        "default",
        "environment",
        "project",
    ]
    companion.unlink()
    assert inspect()["problems"]
    for mutation in [
        lambda d: d.update(purifier="other"),
        lambda d: d["entries"][0].update(hash="invalid"),
        lambda d: d["nodes"][0].update(url="https://example.invalid/package"),
        lambda d: d["nodes"][0].update(entrypoint="../escape.typ"),
        lambda d: d.update(document="missing.typ"),
        lambda d: d.update(package=None),
        lambda d: d.update(sdk=None),
    ]:
        data = json.loads(json.dumps(original))
        mutation(data)
        companion.write_text(json.dumps(data))
        assert inspect()["problems"]
    companion.write_text(json.dumps(original))
    (root / "typst.toml").write_text("# stale\n")
    assert inspect()["problems"]

print("Typst lock validation passed without IFD")
