#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", ".terraform", "__pycache__", "scripts"}
IGNORED_SUFFIXES = {".md"}
MAX_SUMMARY_ROWS = 50


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


def load_changed_files(path: Path) -> list[str]:
    changed_files: list[str] = []

    for line in path.read_text().splitlines():
        value = line.strip()
        if not value:
            continue
        normalized = Path(value).as_posix()
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized:
            changed_files.append(normalized)

    return changed_files


def is_ignored_change(path: str) -> bool:
    return Path(path).suffix in IGNORED_SUFFIXES


def stack_definitions() -> list[dict[str, object]]:
    definitions: list[dict[str, object]] = []

    for path in iter_stack_dirs():
        definitions.append(
            {
                "id": stack_id(path),
                "path": rel_path(path),
                "envs": env_catalog(path),
            }
        )

    return definitions


def env_target_ids(stack: dict[str, object], env: str) -> list[str]:
    return [f"{stack['id']}-{env}"]


def all_stack_target_ids(stack: dict[str, object]) -> list[str]:
    return [f"{stack['id']}-{env}" for env in stack["envs"]]


def root_stack_path_for_file(path: str, stacks: list[dict[str, object]]) -> str | None:
    non_root_paths = sorted(
        [stack["path"] for stack in stacks if stack["path"] != "."],
        key=len,
        reverse=True,
    )

    for stack_path in non_root_paths:
        if path == stack_path or path.startswith(f"{stack_path}/"):
            return stack_path

    root_exists = any(stack["path"] == "." for stack in stacks)
    return "." if root_exists else None


def impacted_target_ids(changed_files: list[str], stack_filter: str | None = None) -> set[str]:
    stacks = stack_definitions()
    if stack_filter is not None:
        stacks = [
            stack
            for stack in stacks
            if stack["path"] == stack_filter or stack["id"] == stack_filter
        ]

    targets = {target["id"] for target in target_catalog(stack_filter)}

    if not changed_files:
        return targets

    impacted: set[str] = set()
    stacks_by_path = {stack["path"]: stack for stack in stacks}

    for path in changed_files:
        if is_ignored_change(path):
            continue

        stack_path = root_stack_path_for_file(path, stacks)
        if stack_path is None:
            continue

        stack = stacks_by_path.get(stack_path)
        if stack is None:
            continue

        relative = path if stack_path == "." else path[len(stack_path) + 1 :]

        if relative.startswith("tfvars/") and relative.endswith(".tfvars"):
            impacted.update(env_target_ids(stack, Path(relative).stem))
            continue

        if relative.startswith("backend-vars/") and relative.endswith(".tfvars"):
            impacted.update(env_target_ids(stack, Path(relative).stem))
            continue

        impacted.update(all_stack_target_ids(stack))

    return impacted & targets


def filtered_targets(changed_files: list[str], stack_filter: str | None = None) -> list[dict[str, str]]:
    selected_ids = impacted_target_ids(changed_files, stack_filter)
    return [
        target
        for target in target_catalog(stack_filter)
        if target["id"] in selected_ids
    ]


def analyze_changed_files(changed_files: list[str], stack_filter: str | None = None) -> list[dict[str, object]]:
    stacks = stack_definitions()
    if stack_filter is not None:
        stacks = [
            stack
            for stack in stacks
            if stack["path"] == stack_filter or stack["id"] == stack_filter
        ]

    targets_by_id = {target["id"]: target for target in target_catalog(stack_filter)}
    stacks_by_path = {stack["path"]: stack for stack in stacks}
    analysis: list[dict[str, object]] = []

    for path in changed_files:
        if is_ignored_change(path):
            analysis.append(
                {
                    "path": path,
                    "classification": "ignored",
                    "effect": "Ignored by discovery rules.",
                    "targets": [],
                }
            )
            continue

        stack_path = root_stack_path_for_file(path, stacks)
        if stack_path is None:
            analysis.append(
                {
                    "path": path,
                    "classification": "outside stack",
                    "effect": "Outside any Terraform stack.",
                    "targets": [],
                }
            )
            continue

        stack = stacks_by_path.get(stack_path)
        if stack is None:
            analysis.append(
                {
                    "path": path,
                    "classification": "outside stack",
                    "effect": "Outside the selected stack filter.",
                    "targets": [],
                }
            )
            continue

        relative = path if stack_path == "." else path[len(stack_path) + 1 :]

        if relative.startswith("tfvars/") and relative.endswith(".tfvars"):
            env = Path(relative).stem
            target_id = f"{stack['id']}-{env}"
            target = targets_by_id.get(target_id)
            if target is None:
                effect = f"Environment `{env}` has no matching tfvars/backend-vars pair."
                targets: list[str] = []
            else:
                effect = f"Selects environment `{target['label']}`."
                targets = [target["label"]]
            analysis.append(
                {
                    "path": path,
                    "classification": "single environment",
                    "effect": effect,
                    "targets": targets,
                }
            )
            continue

        if relative.startswith("backend-vars/") and relative.endswith(".tfvars"):
            env = Path(relative).stem
            target_id = f"{stack['id']}-{env}"
            target = targets_by_id.get(target_id)
            if target is None:
                effect = f"Environment `{env}` has no matching tfvars/backend-vars pair."
                targets = []
            else:
                effect = f"Selects environment `{target['label']}`."
                targets = [target["label"]]
            analysis.append(
                {
                    "path": path,
                    "classification": "single environment",
                    "effect": effect,
                    "targets": targets,
                }
            )
            continue

        stack_targets = [
            target["label"]
            for target in targets_by_id.values()
            if target["stack_id"] == stack["id"]
        ]
        analysis.append(
            {
                "path": path,
                "classification": "whole stack",
                "effect": f"Selects all environments in stack `{stack['path']}`.",
                "targets": stack_targets,
            }
        )

    return analysis


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_target_list(labels: list[str]) -> str:
    if not labels:
        return "none"
    return ", ".join(f"`{markdown_escape(label)}`" for label in labels)


def render_markdown_summary(changed_files: list[str], targets: list[dict[str, str]], stack_filter: str | None = None) -> str:
    analysis = analyze_changed_files(changed_files, stack_filter)
    lines = [
        "## Terraform Target Discovery",
        "",
        f"- Changed files: `{len(changed_files)}`",
        f"- Selected targets: `{len(targets)}`",
        "- Rule: `tfvars/<env>.tfvars` or `backend-vars/<env>.tfvars` selects one environment. Any other file inside a stack selects all environments in that stack.",
        "",
        "### Changed Files",
        "",
        "| File | Classification | Effect | Targets |",
        "| --- | --- | --- | --- |",
    ]

    if not analysis:
        lines.append("| _none_ | - | No changed files were provided. | all targets |")
    else:
        for item in analysis[:MAX_SUMMARY_ROWS]:
            lines.append(
                "| `{path}` | {classification} | {effect} | {targets} |".format(
                    path=markdown_escape(str(item["path"])),
                    classification=markdown_escape(str(item["classification"])),
                    effect=markdown_escape(str(item["effect"])),
                    targets=render_target_list(list(item["targets"])),
                )
            )
        remaining_changes = len(analysis) - MAX_SUMMARY_ROWS
        if remaining_changes > 0:
            lines.append(f"| _..._ | _..._ | `{remaining_changes}` additional changed files omitted. | _..._ |")

    lines.extend(
        [
            "",
            "### Selected Targets",
            "",
        ]
    )

    if not targets:
        lines.append("No Terraform target selected for this change set.")
    else:
        lines.extend(
            [
                "| Target | Stack | Environment | tfvars | backend-vars |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for target in targets[:MAX_SUMMARY_ROWS]:
            lines.append(
                "| `{label}` | `{stack}` | `{env}` | `{tfvars}` | `{backend}` |".format(
                    label=markdown_escape(target["label"]),
                    stack=markdown_escape(target["stack_path"]),
                    env=markdown_escape(target["env"]),
                    tfvars=markdown_escape(target["tfvars_file"]),
                    backend=markdown_escape(target["backend_file"]),
                )
            )
        remaining_targets = len(targets) - MAX_SUMMARY_ROWS
        if remaining_targets > 0:
            lines.append(f"| _..._ | _..._ | _..._ | _..._ | `{remaining_targets}` additional targets omitted. |")

    return "\n".join(lines)


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
    if args.changed_files_from is not None:
        changed_files = load_changed_files(Path(args.changed_files_from))
        targets = filtered_targets(changed_files, args.stack)
    else:
        targets = target_catalog(args.stack)

    if not targets and args.fail_if_empty:
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


def cmd_render_summary(args: argparse.Namespace) -> int:
    changed_files = load_changed_files(Path(args.changed_files_from))
    targets = filtered_targets(changed_files, args.stack)
    print(render_markdown_summary(changed_files, targets, args.stack))
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
    list_targets.add_argument("--changed-files-from")
    list_targets.add_argument("--fail-if-empty", action="store_true")
    list_targets.set_defaults(func=cmd_list_targets)

    resolve = subparsers.add_parser("resolve-stack")
    resolve.add_argument("stack", nargs="?")
    resolve.set_defaults(func=cmd_resolve_stack)

    render_summary = subparsers.add_parser("render-summary")
    render_summary.add_argument("--stack")
    render_summary.add_argument("--changed-files-from", required=True)
    render_summary.set_defaults(func=cmd_render_summary)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
