"""Audit instruction files against the codebase.

Checks:
- Referenced paths exist on disk (from project structure tree)
- uv run scripts are registered or point to existing files
- Type conventions (msgspec vs dataclasses)
- Combined instruction file line budget
- Staleness (docs older than source)
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple


def _find_root() -> Path:
    """Find the project root by walking up from CWD looking for pyproject.toml."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    print("Error: could not find pyproject.toml", file=sys.stderr)
    sys.exit(2)


ROOT = _find_root()
LINE_BUDGET = 1000
SKIP_PATHS = {".env"}  # Gitignored files expected to be absent
TOOL_COMMANDS = {"ruff", "ty"}  # External tools invoked via uv run


class Issue(NamedTuple):
    file: str
    line: int
    message: str


def find_instruction_files() -> list[Path]:
    patterns = ["AGENTS.md", "README.md", ".claude/**/SKILL.md", "src/**/AGENTS.md"]
    found: set[Path] = set()
    for p in patterns:
        found.update(ROOT.glob(p))
    return sorted(found)


def load_scripts() -> dict[str, str]:
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("scripts", {})


# --- Extractors ---


def extract_tree_paths(content: str) -> list[tuple[int, str]]:
    """Parse file paths from the Project Structure tree block."""
    results: list[tuple[int, str]] = []
    lines = content.splitlines()
    in_section = False
    in_block = False
    stack: list[tuple[int, str]] = []  # (indent, dirname_with_slash)

    for i, line in enumerate(lines, 1):
        if line.startswith("## Project Structure"):
            in_section = True
            continue
        if in_section and not in_block:
            if line.strip().startswith("```"):
                in_block = True
                continue
            if line.startswith("## "):
                break
            continue
        if not in_block:
            continue
        if line.strip().startswith("```"):
            break

        stripped = line.rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        name = stripped.strip().split("#")[0].strip()
        if not name:
            continue

        # Pop deeper/equal entries from stack
        while stack and stack[-1][0] >= indent:
            stack.pop()

        if name.endswith("/"):
            stack.append((indent, name))
        else:
            parts = [d for _, d in stack] + [name]
            full = "".join(parts)
            if full.startswith("correspondence-kit/"):
                full = full[len("correspondence-kit/") :]
            results.append((i, full))

    return results


def extract_uv_commands(content: str) -> list[tuple[int, str]]:
    """Extract targets from `uv run <target>` in all contexts."""
    results: list[tuple[int, str]] = []
    pat = re.compile(r"uv run ([\w./-]+)")
    for i, line in enumerate(content.splitlines(), 1):
        for m in pat.finditer(line):
            results.append((i, m.group(1)))
    return results


# --- Checks ---


def check_tree_paths(rel: str, content: str) -> list[Issue]:
    issues: list[Issue] = []
    for line_no, path in extract_tree_paths(content):
        if re.search(r"\[.*?]", path):
            continue
        if path in SKIP_PATHS:
            continue
        if not (ROOT / path).exists():
            issues.append(
                Issue(rel, line_no, f"Referenced path does not exist: {path}")
            )
    return issues


def check_scripts(rel: str, content: str, registered: dict[str, str]) -> list[Issue]:
    issues: list[Issue] = []
    for line_no, target in extract_uv_commands(content):
        if "/" in target or target.endswith(".py"):
            if not (ROOT / target).exists():
                issues.append(
                    Issue(rel, line_no, f"Script file does not exist: {target}")
                )
        elif target not in TOOL_COMMANDS and target not in registered:
            issues.append(
                Issue(
                    rel, line_no, f"Script not registered in pyproject.toml: {target}"
                )
            )
    return issues


def check_type_conventions(rel: str, content: str) -> list[Issue]:
    issues: list[Issue] = []
    if "msgspec" not in content:
        return issues
    for py in sorted(ROOT.glob("src/**/*.py")):
        if py.name == "audit_docs.py":
            continue  # skip self — contains the check string as a literal
        text = py.read_text()
        if "from dataclasses import" in text or "import dataclasses" in text:
            py_rel = py.relative_to(ROOT)
            for i, line in enumerate(content.splitlines(), 1):
                if "msgspec" in line and (
                    "dataclass" in line.lower() or "struct" in line.lower()
                ):
                    issues.append(
                        Issue(
                            rel,
                            i,
                            f'Docs say "msgspec" but {py_rel} uses dataclasses',
                        )
                    )
                    break
            break  # one report per doc file is enough
    return issues


def check_line_budget(
    files: list[Path],
) -> tuple[list[Issue], dict[str, int], int]:
    counts: dict[str, int] = {}
    total = 0
    for f in files:
        n = len(f.read_text().splitlines())
        counts[str(f.relative_to(ROOT))] = n
        total += n
    issues: list[Issue] = []
    if total > LINE_BUDGET:
        issues.append(
            Issue("(all)", 0, f"Over line budget: {total} lines (max {LINE_BUDGET})")
        )
    return issues, counts, total


def check_staleness(files: list[Path]) -> list[Issue]:
    src_files = list(ROOT.glob("src/**/*.py"))
    if not src_files:
        return []
    newest_src = max(src_files, key=lambda f: f.stat().st_mtime)
    newest_mtime = newest_src.stat().st_mtime
    issues: list[Issue] = []
    for doc in files:
        if doc.stat().st_mtime < newest_mtime:
            issues.append(
                Issue(
                    str(doc.relative_to(ROOT)),
                    0,
                    f"Older than {newest_src.relative_to(ROOT)} — may be stale",
                )
            )
    return issues


def main() -> None:
    print("Auditing docs...\n")
    files = find_instruction_files()
    scripts = load_scripts()
    issues: list[Issue] = []

    for doc in files:
        rel = str(doc.relative_to(ROOT))
        content = doc.read_text()
        issues.extend(check_tree_paths(rel, content))
        issues.extend(check_scripts(rel, content, scripts))
        issues.extend(check_type_conventions(rel, content))

    budget_issues, counts, total = check_line_budget(files)
    issues.extend(budget_issues)
    issues.extend(check_staleness(files))

    for issue in issues:
        loc = f"  {issue.file}"
        if issue.line:
            loc += f":{issue.line}"
        print(f"{loc:<35} ✗ {issue.message}")

    mark = "✓" if total <= LINE_BUDGET else "✗"
    print(f"\nCombined instruction files: {total} lines (budget: {LINE_BUDGET}) {mark}")
    for name, n in sorted(counts.items()):
        print(f"  {name}: {n}")

    n = len(issues)
    print(f"\nFound {n} issue(s)" if n else "\nNo issues found ✓")
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
