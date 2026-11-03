"""Native compiler/editor, mutable source, isolation and artifact consumers."""

import hashlib
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
    / "bin"
)


def command(args, root, expected=0, **kwargs):
    result = subprocess.run(
        [str(x) for x in args], cwd=root, capture_output=True, text=True, **kwargs
    )
    assert result.returncode == expected, (
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    return result


with tempfile.TemporaryDirectory(prefix="typst-conformance-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".typst-purifier", "*.pdf"),
    )
    poison = temporary / "poison"
    poison.mkdir()
    env = dict(
        os.environ,
        TYPST_PACKAGE_PATH=str(poison),
        TYPST_PACKAGE_CACHE_PATH=str(poison),
        TYPST_FONT_PATHS=str(poison),
    )
    command(
        [
            cli / "typst",
            "compile",
            "--deps",
            root / "dependencies.json",
            "main.typ",
            "proof.pdf",
        ],
        root,
        env=env,
    )
    assert (root / "proof.pdf").read_bytes().startswith(b"%PDF")
    deps = json.loads((root / "dependencies.json").read_text())["inputs"]
    package_paths = [p for p in deps if "/preview/" in p]
    assert package_paths and all(p.startswith("/nix/store/") for p in package_paths)
    assert any(p.endswith(".wasm") for p in package_paths)
    assert (
        command(
            [
                cli / "typst",
                "eval",
                "--in",
                "main.typ",
                "query(<purifier-proof>).first().value",
            ],
            root,
            env=env,
        ).stdout.strip()
        == "42"
    )
    library = root / "lib.typ"
    original = library.read_text()
    library.write_text(original.replace("#let answer = 42", "#let answer = 43"))
    failed = subprocess.run(
        [cli / "typst", "compile", "main.typ", "negative.pdf"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert failed.returncode and "assertion failed" in failed.stderr, failed
    library.write_text(original.replace("cetz:0.5.2", "cetz:0.5.1"))
    missing = subprocess.run(
        [cli / "typst", "compile", "main.typ", "missing.pdf"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (
        missing.returncode
        and "absent from the locked Nix environment" in missing.stderr
    ), missing
    library.write_text(original)
    command([cli / "typst", "compile", "main.typ", "restored.pdf"], root, env=env)
    assert (root / "proof.pdf").read_bytes() == (root / "restored.pdf").read_bytes()
    command(["python3", repo / "tests/lsp.py", cli / "tinymist", root], root, env=env)
    companion = temporary / "external.json"
    (root / "typst-purifier.lock.json").rename(companion)
    external = dict(
        env, TYPST_PURIFIER_PROJECT=str(root), TYPST_PURIFIER_LOCK=str(companion)
    )
    nested = root / "nested"
    nested.mkdir()
    assert (
        command(
            [
                cli / "typst",
                "eval",
                "--in",
                "../main.typ",
                "query(<purifier-proof>).first().value",
            ],
            nested,
            env=external,
        ).stdout.strip()
        == "42"
    )
    metadata = root / "typst.toml"
    saved = metadata.read_text()
    metadata.write_text(saved.replace('version = "0.1.0"', 'version = "0.2.0"'))
    rejected = subprocess.run(
        [cli / "typst", "compile", "main.typ"],
        cwd=root,
        env=external,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode and "metadata changed" in rejected.stderr
    metadata.write_text(saved)
    profile = root / ".typst-purifier/environment-profile"
    references = subprocess.check_output(
        ["nix-store", "--query", "--requisites", profile.resolve()], text=True
    )
    assert "typst-purifier-" in references and "typst-locked-packages" in references
    fallback = temporary / "fallback"
    fallback.mkdir()
    ordinary = command([cli / "typst", "--version"], fallback)
    assert "typst 0.15.1" in ordinary.stdout and "impure" in ordinary.stderr
    ordinary_editor = command([cli / "tinymist", "--version"], fallback)
    assert (
        "tinymist" in ordinary_editor.stdout.lower()
        and "impure" in ordinary_editor.stderr
    )
    streams = command(
        [
            cli / "typst-purifier",
            "exec",
            "--project",
            fallback,
            "--",
            "python3",
            "-c",
            "import sys; print(sys.stdin.read().strip()); print('native-stderr',file=sys.stderr); sys.exit(7)",
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
    bundle = command(
        [cli / "typst-purifier", "bundle", "--project", root, "--lock", companion], root
    )
    artifacts = Path(bundle.stdout.strip().splitlines()[-1])
    archives = list(artifacts.glob("*.tar.gz"))
    assert len(archives) == 1 and (artifacts / "document.pdf").is_file()
    fake = temporary / "fake-gh"
    record = temporary / "uploaded.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport hashlib,json,os,pathlib,sys\nfiles={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in map(pathlib.Path,sys.argv[4:-1])};pathlib.Path(os.environ['PUBLICATION_RECORD']).write_text(json.dumps({'args':sys.argv[1:],'files':files}))\n"
    )
    fake.chmod(0o755)
    publication = dict(
        os.environ, TYPST_PURIFIER_GH=str(fake), PUBLICATION_RECORD=str(record)
    )
    command(
        [
            cli / "typst-purifier",
            "publish",
            "--tag",
            "v0.1.0",
            "--project",
            root,
            "--lock",
            companion,
        ],
        root,
        env=publication,
    )
    uploaded = json.loads(record.read_text())
    assert uploaded["args"] == [
        "release",
        "upload",
        "v0.1.0",
        *map(str, sorted(artifacts.iterdir())),
        "--clobber",
    ]
    assert uploaded["files"] == {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts.iterdir()
    }
    # An unmodified native compiler imports the published source package.
    consumer = temporary / "consumer"
    package_dir = consumer / "packages/local/purifier-proof/0.1.0"
    package_dir.mkdir(parents=True)
    import tarfile

    with tarfile.open(archives[0]) as archive:
        archive.extractall(package_dir, filter="data")
    (consumer / "main.typ").write_text(
        '#import "@local/purifier-proof:0.1.0": answer, proof-drawing\n#assert(answer == 42)\n#proof-drawing()\n#metadata(answer) <purifier-proof>\n'
    )
    selected = json.loads(profile.resolve().read_text())["output"]
    consumer_env = dict(
        os.environ,
        TYPST_PACKAGE_PATH=str(consumer / "packages"),
        TYPST_PACKAGE_CACHE_PATH=selected,
        TYPST_IGNORE_SYSTEM_FONTS="true",
    )
    answer = command(
        [
            cli / "typst",
            "eval",
            "--in",
            "main.typ",
            "query(<purifier-proof>).first().value",
        ],
        consumer,
        env=consumer_env,
    )
    assert answer.stdout.strip() == "42" and "impure" in answer.stderr

print(
    "Native Typst/WASM, editor, source, cache isolation, fallback and publication proofs passed"
)
