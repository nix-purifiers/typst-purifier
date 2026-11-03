"""Native Typst and Tinymist with locked Nix-resolved packages."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import json

from .capture import capture
from .common import HERE, environment, load, locate, run


def realize(root, companion, target="environment"):
    state = root / ".typst-purifier"
    state.mkdir(exist_ok=True)
    result = run(
        [
            "nix-build",
            HERE / "nix/realize.nix",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "target",
            target,
            "--argstr",
            "sdk",
            os.environ["TYPST_PURIFIER_SDK"],
            "--arg",
            "profile",
            "true",
            "--out-link",
            state / (target + "-profile"),
        ],
        capture_output=True,
        text=True,
    )
    return Path(
        json.loads(Path(result.stdout.strip().splitlines()[-1]).read_text())["output"]
    )


def native(tool, args):
    root, companion = locate()
    suffix = tool.upper()
    if not companion.exists():
        print(
            f"warning: typst-purifier: no lockfile; using ordinary impure {tool} resolution",
            file=sys.stderr,
        )
        os.execv(os.environ["TYPST_PURIFIER_ORIGINAL_" + suffix], [tool, *args])
    data = load(root, companion)
    if tool == "typst" and any(
        x.startswith(("--package-path", "--package-cache-path", "--font-path"))
        for x in args
    ):
        raise ValueError(
            "Locked Typst package and font search paths cannot be overridden"
        )
    prepared = realize(root, companion)
    env = environment()
    env.update(
        TYPST_PURIFIER_FROZEN="1",
        TYPST_PACKAGE_PATH=str(prepared),
        TYPST_PACKAGE_CACHE_PATH=str(prepared),
    )
    if tool == "typst":
        commands = {"compile", "c", "watch", "w", "eval"}
        # These options belong after the native subcommand, preserving its CLI.
        for i, arg in enumerate(args):
            if arg in commands:
                args = [
                    *args[: i + 1],
                    *[x for d in data["defines"] for x in ["--input", d]],
                    *args[i + 1 :],
                ]
                break
    elif not args:
        args = ["lsp", "--ignore-system-fonts"]
    elif args[0] == "lsp":
        if "--ignore-system-fonts" not in args:
            args = [*args, "--ignore-system-fonts"]
    os.execve(os.environ["TYPST_PURIFIER_NATIVE_" + suffix], [tool, *args], env)


def main():
    try:
        args = sys.argv[1:]
        if args and args[0].startswith("--native="):
            native(args[0].split("=", 1)[1], args[1:])
            return
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "command", choices=["lock", "prefetch", "bundle", "publish", "exec"]
        )
        parser.add_argument("--document")
        parser.add_argument("--update", action="store_true")
        parser.add_argument("--input", action="append", default=[])
        parser.add_argument("--define", action="append", default=[])
        parser.add_argument("--project", type=Path, default=Path.cwd())
        parser.add_argument("--lock", type=Path)
        parser.add_argument("--tag")
        before, separator, after = args, False, []
        if "--" in args:
            position = args.index("--")
            before, separator, after = args[:position], True, args[position + 1 :]
        opts = parser.parse_args(before)
        root = opts.project.resolve()
        companion = (
            opts.lock.resolve() if opts.lock else root / "typst-purifier.lock.json"
        )
        if opts.command == "lock":
            capture(
                root, companion, opts.document, opts.update, opts.input, opts.define
            )
        elif opts.command == "exec":
            if not separator or not after:
                raise ValueError("Use typst-purifier exec -- command")
            if not companion.exists():
                print(
                    "warning: typst-purifier: no lockfile; using ordinary impure resolution",
                    file=sys.stderr,
                )
                os.execvpe(after[0], after, os.environ)
            load(root, companion)
            prepared = realize(root, companion)
            env = environment()
            env.update(
                TYPST_PURIFIER_FROZEN="1",
                TYPST_PACKAGE_PATH=str(prepared),
                TYPST_PACKAGE_CACHE_PATH=str(prepared),
                TYPST_PURIFIER_LOCK=str(companion),
                TYPST_PURIFIER_PROJECT=str(root),
            )
            env["PATH"] = (
                os.environ["TYPST_PURIFIER_SDK"] + "/bin:" + env.get("PATH", "")
            )
            os.execvpe(after[0], after, env)
        else:
            load(root, companion)
            result = realize(
                root,
                companion,
                "environment" if opts.command == "prefetch" else "release",
            )
            if opts.command == "publish":
                if not opts.tag:
                    raise ValueError("Publication requires --tag")
                run(
                    [
                        os.environ.get("TYPST_PURIFIER_GH", "gh"),
                        "release",
                        "upload",
                        opts.tag,
                        *sorted(result.iterdir()),
                        "--clobber",
                    ],
                    cwd=root,
                )
            print(result)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        print("typst-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)
