"""Contact configuration — parse contacts.toml."""

import tomllib
from pathlib import Path

import msgspec

CONFIG_PATH = Path("contacts.toml")


class Contact(msgspec.Struct):
    emails: list[str] = []
    labels: list[str] = []
    account: str = ""


def load_contacts(path: Path | None = None) -> dict[str, Contact]:
    """Load contacts.toml and return {name: Contact} mapping."""
    if path is None:
        path = CONFIG_PATH
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    result: dict[str, Contact] = {}
    for name, data in raw.items():
        result[name] = msgspec.convert(data, Contact)
    return result


def save_contacts(contacts: dict[str, Contact], path: Path | None = None) -> None:
    """Write contacts back to TOML. Simple serializer — no third-party dep."""
    if path is None:
        path = CONFIG_PATH
    lines: list[str] = []
    for name, c in sorted(contacts.items()):
        lines.append(f"[{name}]")
        if c.emails:
            emails = ", ".join(f'"{e}"' for e in c.emails)
            lines.append(f"emails = [{emails}]")
        if c.labels:
            labels = ", ".join(f'"{lbl}"' for lbl in c.labels)
            lines.append(f"labels = [{labels}]")
        if c.account:
            lines.append(f'account = "{c.account}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
