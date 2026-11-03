"""Native graph changes, empty documents, tracked inputs and metadata binding."""

import json
import os
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
    / "bin/typst-purifier"
)

with tempfile.TemporaryDirectory(prefix="typst-capture-proof-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project"
    root.mkdir()
    document = root / "main.typ"
    document.write_text(
        '#let answer = int(sys.inputs.at("answer"))\n#assert(answer == 42)\n#metadata(answer) <purifier-proof>\n'
    )
    (root / "selection.txt").write_text("tracked input\n")
    companion = temporary / "external.json"

    def call(*args):
        return subprocess.run(
            [cli, *args, "--project", root, "--lock", companion],
            capture_output=True,
            text=True,
            check=True,
        )

    call("lock", "--input", "selection.txt", "--define", "answer=42")
    empty = json.loads(companion.read_text())
    assert empty["nodes"] == empty["entries"] == [] and empty["package"] is None
    assert empty["defines"] == ["answer=42"]
    call("prefetch")
    before = companion.read_bytes()
    call("lock")
    assert companion.read_bytes() == before
    env = dict(
        os.environ, TYPST_PURIFIER_PROJECT=str(root), TYPST_PURIFIER_LOCK=str(companion)
    )
    answer = subprocess.check_output(
        [
            cli.parent / "typst",
            "eval",
            "--in",
            "main.typ",
            "query(<purifier-proof>).first().value",
        ],
        cwd=root,
        env=env,
        text=True,
    )
    assert answer.strip() == "42"
    for name in ["main.typ", "lib.typ", "typst.toml"]:
        shutil.copy2(repo / "examples/minimal" / name, root / name)
    assert subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion], capture_output=True
    ).returncode
    call("lock", "--update")
    selected = json.loads(companion.read_text())
    assert selected["extraInputs"] == ["selection.txt"]
    assert {n["name"] for n in selected["nodes"]} == {"cetz", "oxifmt"}
    call("prefetch")
    selected["nodes"][0]["entrypoint"] = "wrong.typ"
    companion.write_text(json.dumps(selected))
    failed = subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion],
        capture_output=True,
        text=True,
    )
    assert failed.returncode and "metadata differs" in failed.stderr, failed

print(
    "Native Typst empty/configured graph, update, external companion and archive metadata binding passed"
)
