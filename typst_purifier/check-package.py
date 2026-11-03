"""Bind native package identity and entrypoint to the retained archive."""

import json
from pathlib import Path
import sys
import tomllib

expected = json.loads(Path(sys.argv[1]).read_text())
root = Path(sys.argv[2])
metadata = tomllib.loads((root / "typst.toml").read_text())["package"]
if any(metadata[k] != expected[k] for k in ("name", "version", "entrypoint")):
    raise SystemExit("Native Typst package metadata differs from its lock")
entrypoint = Path(metadata["entrypoint"])
if (
    entrypoint.is_absolute()
    or ".." in entrypoint.parts
    or not (root / entrypoint).is_file()
):
    raise SystemExit("Native Typst package entrypoint is invalid")
