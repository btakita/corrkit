"""App-level config for corrkit (spaces, defaults).

Reads/writes {platformdirs.user_config_dir("corrkit")}/config.toml.

Example config.toml:

    default_space = "personal"

    [spaces.personal]
    path = "~/Documents/correspondence"

    [spaces.work]
    path = "~/work/correspondence"
"""

import sys
import tomllib
from pathlib import Path

import tomli_w
from platformdirs import user_config_dir


def app_config_dir() -> Path:
    """Return the OS-native corrkit config directory."""
    return Path(user_config_dir("corrkit"))


def app_config_path() -> Path:
    """Return the path to config.toml."""
    return app_config_dir() / "config.toml"


def load() -> dict:
    """Read config.toml, returning empty dict if missing."""
    path = app_config_path()
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def save(config: dict) -> None:
    """Write config.toml, creating parent dir if needed."""
    path = app_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tomli_w.dumps(config).encode())


def resolve_space(name: str | None) -> Path | None:
    """Resolve a space name to a data directory path.

    - If name given: look up, error if not found.
    - No name + default_space set: use default.
    - No name + exactly 1 space: use it implicitly.
    - No name + multiple spaces, no default: SystemExit with list.
    - No spaces configured: return None.
    """
    config = load()
    spaces = config.get("spaces", {})

    if not spaces:
        return None

    if name:
        if name not in spaces:
            available = ", ".join(sorted(spaces))
            print(
                f"Unknown space '{name}'. Available: {available}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        return Path(spaces[name]["path"]).expanduser()

    # No name given — try defaults
    default = config.get("default_space")
    if default:
        if default in spaces:
            return Path(spaces[default]["path"]).expanduser()
        # default_space points to a missing space — fall through

    if len(spaces) == 1:
        only = next(iter(spaces.values()))
        return Path(only["path"]).expanduser()

    # Multiple spaces, no default
    print(
        "Multiple spaces configured. Use --space NAME or set default_space.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    for sname, sconf in spaces.items():
        print(f"  {sname}  {sconf['path']}", file=sys.stderr)
    raise SystemExit(1)


def add_space(name: str, path: str) -> None:
    """Register a space, auto-default if first."""
    config = load()
    spaces = config.setdefault("spaces", {})
    spaces[name] = {"path": path}
    if len(spaces) == 1:
        config["default_space"] = name
    save(config)
