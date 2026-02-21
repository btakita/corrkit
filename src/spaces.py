"""List configured corrkit spaces.

Usage:
    corrkit spaces
"""

import app_config


def main() -> None:
    config = app_config.load()
    spaces = config.get("spaces", {})
    default = config.get("default_space")

    if not spaces:
        print("No spaces configured.")
        print("Run 'corrkit init --user EMAIL' to create one.")
        return

    print("corrkit spaces\n")
    name_w = max(len(n) for n in spaces)
    for name, conf in spaces.items():
        marker = " (default)" if name == default else ""
        print(f"  {name:<{name_w}}  {conf['path']}{marker}")
