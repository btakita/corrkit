"""Collaborator configuration — parse collaborators.toml."""

import tomllib
from pathlib import Path

import msgspec

CONFIG_PATH = Path("collaborators.toml")


class Collaborator(msgspec.Struct):
    labels: list[str]
    repo: str
    github_user: str = ""


def load_collaborators(path: Path | None = None) -> dict[str, Collaborator]:
    """Load collaborators.toml and return {name: Collaborator} mapping."""
    if path is None:
        path = CONFIG_PATH
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    result: dict[str, Collaborator] = {}
    for name, data in raw.items():
        result[name] = msgspec.convert(data, Collaborator)
    return result


def save_collaborators(
    collabs: dict[str, Collaborator], path: Path | None = None
) -> None:
    """Write collaborators back to TOML. Simple serializer — no third-party dep."""
    if path is None:
        path = CONFIG_PATH
    lines: list[str] = []
    for name, c in sorted(collabs.items()):
        lines.append(f"[{name}]")
        labels = ", ".join(f'"{lbl}"' for lbl in c.labels)
        lines.append(f"labels = [{labels}]")
        lines.append(f'repo = "{c.repo}"')
        if c.github_user:
            lines.append(f'github_user = "{c.github_user}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
