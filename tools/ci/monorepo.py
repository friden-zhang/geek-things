#!/usr/bin/env python3
"""Monorepo helpers for board discovery, validation, and builds."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class Board(NamedTuple):
    name: str
    path: Path
    contract_path: Path
    firmware_path: Path


def _entry_path_from_value(entry_value: str, manifest_path: Path) -> Path | None:
    entry_file = entry_value.strip().strip("'\"").split(":", 1)[0].strip()
    if not entry_file:
        return None
    return manifest_path.parent / entry_file


def manifest_entry_file(manifest_path: Path) -> Path | None:
    current_build: str | None = None
    builds_indent: int | None = None
    current_build_indent: int | None = None
    fallback_entry: Path | None = None

    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = line.strip()

        if builds_indent is None:
            if stripped == "builds:":
                builds_indent = indent
            continue

        if indent <= builds_indent:
            break

        if (
            stripped.endswith(":")
            and ":" not in stripped[:-1]
            and indent == builds_indent + 2
        ):
            current_build = stripped[:-1]
            current_build_indent = indent
            continue

        if not stripped.startswith("entry:") or current_build_indent is None:
            continue
        if indent <= current_build_indent:
            continue

        entry_path = _entry_path_from_value(stripped.split(":", 1)[1], manifest_path)
        if current_build == "default":
            return entry_path
        if fallback_entry is None:
            fallback_entry = entry_path

    if fallback_entry is not None:
        return fallback_entry
    return None


def discover_boards(repo_root: Path) -> list[Board]:
    boards_root = repo_root / "hardware" / "boards"
    if not boards_root.is_dir():
        return []

    boards: list[Board] = []
    for path in boards_root.iterdir():
        if not path.is_dir():
            continue
        if not (path / "ato.yaml").is_file():
            continue
        boards.append(
            Board(
                name=path.name,
                path=path,
                contract_path=repo_root / "hardware" / "contracts" / f"{path.name}.yaml",
                firmware_path=repo_root / "firmware" / "boards" / path.name,
            )
        )

    return sorted(boards, key=lambda board: board.name)


def validate_repo(repo_root: Path) -> list[str]:
    errors: list[str] = []

    required_dirs = [
        repo_root / "hardware" / "boards",
        repo_root / "hardware" / "contracts",
        repo_root / "hardware" / "packages" / "interfaces",
        repo_root / "hardware" / "packages" / "power",
        repo_root / "hardware" / "packages" / "common",
        repo_root / "firmware" / "shared",
        repo_root / "firmware" / "boards",
        repo_root / "software" / "tools",
        repo_root / "docs" / "architecture",
        repo_root / "tools" / "ci",
    ]

    for path in required_dirs:
        if not path.is_dir():
            errors.append(f"Missing required directory: {path.relative_to(repo_root)}")

    atopile_root = repo_root / "third_party" / "atopile"
    if not atopile_root.is_dir():
        errors.append(f"Missing required directory: {atopile_root.relative_to(repo_root)}")
    else:
        for rel in ("pyproject.toml", "src/atopile/__init__.py"):
            path = atopile_root / rel
            if not path.is_file():
                errors.append(
                    f"Missing required atopile path: {path.relative_to(repo_root)}"
                )

    version_file = repo_root / "VERSION"
    if not version_file.is_file():
        errors.append("Missing required file: VERSION")
    elif not version_file.read_text(encoding="utf-8").strip():
        errors.append("VERSION must contain a non-empty monorepo version")

    boards = discover_boards(repo_root)
    if not boards:
        errors.append("No hardware boards found under hardware/boards")
        return errors

    for board in boards:
        manifest_path = board.path / "ato.yaml"
        required_paths = [
            board.path / "README.md",
            manifest_path,
            board.path / "src" / "main.ato",
            board.path / "layouts",
            board.contract_path,
            board.firmware_path,
        ]
        for path in required_paths:
            if path.suffix:
                exists = path.is_file()
            else:
                exists = path.is_dir()
            if not exists:
                errors.append(f"Missing required board path: {path.relative_to(repo_root)}")

        entry_file = manifest_entry_file(manifest_path)
        if entry_file is None:
            errors.append(
                f"Missing or invalid entry declaration in: {manifest_path.relative_to(repo_root)}"
            )
        elif not entry_file.is_file():
            errors.append(
                "Missing board manifest entry file: "
                f"{entry_file.relative_to(repo_root)} "
                f"(declared by {manifest_path.relative_to(repo_root)})"
            )

    return errors


def board_names_json(repo_root: Path) -> str:
    return json.dumps([board.name for board in discover_boards(repo_root)])


def canonical_design_artifact(board: Board) -> Path:
    return (
        board.path
        / "build"
        / "builds"
        / "default"
        / "default.canonical_design.json"
    )


def build_board(repo_root: Path, board_name: str, frozen: bool = False) -> int:
    boards = {board.name: board for board in discover_boards(repo_root)}
    board = boards.get(board_name)
    if board is None:
        print(f"Unknown board: {board_name}", file=sys.stderr)
        return 1

    print(f"==> ato build ({board.name})")
    command = ["ato", "build"]
    if frozen:
        command.append("--frozen")
    result = subprocess.run(command, cwd=board.path, check=False)
    if result.returncode != 0:
        return result.returncode

    artifact = canonical_design_artifact(board)
    if not artifact.is_file():
        print(
            f"Missing canonical design artifact: {artifact.relative_to(repo_root)}",
            file=sys.stderr,
        )
        return 1

    return 0


def build_all_boards(repo_root: Path, frozen: bool = False) -> int:
    exit_code = 0
    for board in discover_boards(repo_root):
        exit_code = max(exit_code, build_board(repo_root, board.name, frozen=frozen))
    return exit_code


def parse_args() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root to inspect",
    )
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="Pass `--frozen` through to `ato build` commands",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--json-boards",
        action="store_true",
        help="Print the hardware board inventory as a JSON array",
    )
    mode_group.add_argument(
        "--check",
        action="store_true",
        help="Validate the expected monorepo shape",
    )
    mode_group.add_argument(
        "--build-board",
        metavar="BOARD",
        help="Run `ato build` for one hardware board",
    )
    mode_group.add_argument(
        "--build-all",
        action="store_true",
        help="Run `ato build` for every discovered hardware board",
    )
    return parser, parser.parse_args()


def main() -> int:
    parser, args = parse_args()
    repo_root = args.repo_root.resolve()

    if args.json_boards:
        print(board_names_json(repo_root))
        return 0

    if args.check:
        errors = validate_repo(repo_root)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Monorepo structure OK ({len(discover_boards(repo_root))} board(s))")
        return 0

    if args.build_board:
        return build_board(repo_root, args.build_board, frozen=args.frozen)

    if args.build_all:
        return build_all_boards(repo_root, frozen=args.frozen)

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
