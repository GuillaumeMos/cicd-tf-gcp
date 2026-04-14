#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", ".terraform", "__pycache__", "scripts"}


def is_stack_dir(path: Path) -> bool:
    return (
        (path / "main.tf").is_file()
        and (path / "_provider.tf").is_file()
        and (path / "tfvars").is_dir()
        and (path / "backend-vars").is_dir()
    )


def rel_path(path: Path) -> str:
    relative = path.relative_to(ROOT_DIR)
    return "." if str(relative) == "." else relative.as_posix()


def stack_id(path: Path) -> str:
    relative = rel_path(path)
    if relative == ".":
      return "root"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", relative)


def iter_stack_dirs() -> list[Path]:
    found: list[Path] = []

    if is_stack_dir(ROOT_DIR):
        found.append(ROOT_DIR)

    for directory in sorted(ROOT_DIR.rglob("*")):
        if not directory.is_dir():
            continue
        if any(part in SKIP_DIRS or part.startswith(".") for part in directory.parts[len(ROOT_DIR.parts):]):
            continue
        if directory == ROOT_DIR:
            continue
        if is_stack_dir(directory):
            found.append(directory)

    deduped: dict[str, Path] = {}
    for item in found:
        deduped[rel_path(item)] = item
    return [deduped[key] for key in sorted(deduped)]


def stack_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": stack_id(path),
            "path": rel_path(path),
        }
        for path in iter_stack_dirs()
    ]


def env_catalog(path: Path) -> list[str]:
    tfvars = {file.stem for file in (path / "tfvars").glob("*.tfvars")}
    backend = {file.stem for file in (path / "backend-vars").glob("*.tfvars")}
    return sorted(tfvars & backend)


def target_catalog(stack_filter: str | None = None) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []

    for path in iter_stack_dirs():
        if stack_filter is not None and rel_path(path) != stack_filter and stack_id(path) != stack_filter:
            continue

        for env in env_catalog(path):
            relative = rel_path(path)
            label_prefix = stack_id(path) if relative == "." else relative
            targets.append(
                {
                    "id": f"{stack_id(path)}-{env}",
                    "label": f"{label_prefix}:{env}",
                    "stack_id": stack_id(path),
                    "stack_path": relative,
                    "env": env,
                    "tfvars_file": f"{relative}/tfvars/{env}.tfvars" if relative != "." else f"tfvars/{env}.tfvars",
                    "backend_file": f"{relative}/backend-vars/{env}.tfvars" if relative != "." else f"backend-vars/{env}.tfvars",
                }
            )

    return targets


def resolve_stack(requested: str | None) -> str:
    stacks = stack_catalog()
    by_id = {item["id"]: item["path"] for item in stacks}
    by_path = {item["path"]: item["path"] for item in stacks}

    if requested:
        if requested in by_path:
            return by_path[requested]
        if requested in by_id:
            return by_id[requested]
        raise SystemExit(
            "Unknown Terraform stack: %s\nAvailable stacks:\n%s"
            % (requested, "\n".join(item["path"] for item in stacks))
        )

    if "." in by_path:
        return "."

    if "iam" in by_path:
        return "iam"

    if len(stacks) == 1:
        return stacks[0]["path"]

    raise SystemExit(
        "Multiple Terraform stacks detected. Set COMPONENT=<stack>.\n%s"
        % "\n".join(item["path"] for item in stacks)
    )


def print_json(data: object) -> None:
    print(json.dumps(data, separators=(",", ":")))


def cmd_list_stacks(args: argparse.Namespace) -> int:
    stacks = stack_catalog()
    if args.json:
        print_json(stacks)
    else:
        for stack in stacks:
            print(stack["path"])
    return 0


def cmd_list_envs(args: argparse.Namespace) -> int:
    stack_path = Path(ROOT_DIR / resolve_stack(args.stack))
    for env in env_catalog(stack_path):
        print(env)
    return 0


def cmd_list_targets(args: argparse.Namespace) -> int:
    targets = target_catalog(args.stack)
    if not targets:
        raise SystemExit("No Terraform targets found.")
    if args.json:
        print_json(targets)
    else:
        for target in targets:
            print(target["label"])
    return 0


def cmd_resolve_stack(args: argparse.Namespace) -> int:
    print(resolve_stack(args.stack))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover Terraform stacks and environments.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_stacks = subparsers.add_parser("list-stacks")
    list_stacks.add_argument("--json", action="store_true")
    list_stacks.set_defaults(func=cmd_list_stacks)

    list_envs = subparsers.add_parser("list-envs")
    list_envs.add_argument("--stack")
    list_envs.set_defaults(func=cmd_list_envs)

    list_targets = subparsers.add_parser("list-targets")
    list_targets.add_argument("--stack")
    list_targets.add_argument("--json", action="store_true")
    list_targets.set_defaults(func=cmd_list_targets)

    resolve = subparsers.add_parser("resolve-stack")
    resolve.add_argument("stack", nargs="?")
    resolve.set_defaults(func=cmd_resolve_stack)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
