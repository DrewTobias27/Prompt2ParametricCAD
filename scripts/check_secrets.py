"""Fail a release when a tracked file contains a credential-shaped token."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


TOKEN_PATTERNS = (
    re.compile(r"sk-" + r"[A-Za-z0-9_-]{32,}"),
    re.compile(r"github_" + r"pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_" + r"[A-Za-z0-9]{20,}"),
)
IGNORED_PARTS = {".git", "generated", "node_modules", "dist", "__pycache__"}


def repository_paths(root: Path) -> tuple[Path, ...]:
    """Return tracked and non-ignored files without exposing their contents."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("git ls-files failed while checking release secrets")
    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return tuple(root / name for name in names if name)


def all_source_paths(root: Path) -> tuple[Path, ...]:
    """Return a filesystem source set for isolated scanner tests."""
    return tuple(
        path
        for path in root.rglob("*")
        if path.is_file() and not set(path.relative_to(root).parts) & IGNORED_PARTS
    )


def scan_paths(root: Path, paths: tuple[Path, ...]) -> list[tuple[str, int]]:
    """Report only locations, never matched credential values."""
    matches: list[tuple[str, int]] = []
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if any(pattern.search(line) for pattern in TOKEN_PATTERNS):
                matches.append((path.relative_to(root).as_posix(), line_number))
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Scan source-like filesystem paths instead of Git-tracked files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    paths = all_source_paths(root) if args.all_files else repository_paths(root)
    matches = scan_paths(root, paths)
    if matches:
        print("Credential-shaped values found; values are intentionally hidden:")
        for path, line_number in matches:
            print(f"- {path}:{line_number}")
        return 1
    print(f"PASS secret scan ({len(paths)} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
