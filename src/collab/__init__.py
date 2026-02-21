"""Collaborator configuration — parse collaborators.toml."""

import tomllib
from pathlib import Path

import msgspec

CONFIG_PATH = Path("collaborators.toml")


class Collaborator(msgspec.Struct):
    labels: list[str]
    repo: str = ""
    github_user: str = ""
    name: str = ""
    account: str = ""


def collab_dir(collab: Collaborator) -> Path:
    """Return the local collab directory (correspondence/for/{gh_user}/)."""
    return Path("correspondence") / "for" / collab.github_user.lower()


def _auto_repo(owner_gh: str, collab_gh: str) -> str:
    """Derive the default repo name: {owner}/to-{collab}."""
    return f"{owner_gh}/to-{collab_gh.lower()}"


def load_collaborators(path: Path | None = None) -> dict[str, Collaborator]:
    """Load collaborators.toml and return {github_user: Collaborator} mapping.

    The TOML section key is the collaborator's GitHub username.
    ``repo`` is auto-derived from owner config if not explicitly set.
    """
    if path is None:
        path = CONFIG_PATH
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    # Load owner for repo auto-derivation
    owner_gh = ""
    try:
        from accounts import load_owner

        owner = load_owner()
        owner_gh = owner.github_user
    except (SystemExit, ImportError):
        pass

    result: dict[str, Collaborator] = {}
    for gh_user, data in raw.items():
        collab = msgspec.convert(data, Collaborator)
        # github_user is always the TOML key
        collab = msgspec.structs.replace(collab, github_user=gh_user)
        # Auto-derive repo if not explicit
        if not collab.repo and owner_gh:
            collab = msgspec.structs.replace(collab, repo=_auto_repo(owner_gh, gh_user))
        result[gh_user] = collab
    return result


def save_collaborators(
    collabs: dict[str, Collaborator], path: Path | None = None
) -> None:
    """Write collaborators back to TOML. Simple serializer — no third-party dep."""
    if path is None:
        path = CONFIG_PATH
    lines: list[str] = []
    for gh_user, c in sorted(collabs.items()):
        lines.append(f"[{gh_user}]")
        labels = ", ".join(f'"{lbl}"' for lbl in c.labels)
        lines.append(f"labels = [{labels}]")
        if c.name:
            lines.append(f'name = "{c.name}"')
        if c.repo:
            lines.append(f'repo = "{c.repo}"')
        if c.account:
            lines.append(f'account = "{c.account}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
