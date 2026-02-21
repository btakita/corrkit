"""
Add a new contact: scaffold correspondence/contacts/{name}/ with AGENTS.md.

Usage:
  corrkit contact-add alex --email alex@example.com
  corrkit contact-add alex --email alex@example.com --email alex@work.com \
    --label correspondence
"""

import argparse
import os
import sys

import resolve

from . import Contact, load_contacts, save_contacts


def _generate_agents_md(name: str) -> str:
    return f"""# Contact: {name}

Context for drafting emails to or about {name}.

## Relationship

<!-- How you know this person, what they work on, shared history -->

## Tone

<!-- Communication style for this person.
     Defaults to voice.md; note overrides here.
     e.g. "More formal than usual" or "Very casual, first-name basis" -->

## Topics

<!-- Recurring subjects, current projects, things to reference or avoid -->

## Notes

<!-- Freeform: quirks, preferences, pending items, important dates -->
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a new contact")
    parser.add_argument("name", help="Contact name (used for directory name)")
    parser.add_argument(
        "--email",
        action="append",
        required=True,
        help="Email address(es) for this contact (repeatable)",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="Conversation label(s) containing this person's threads (repeatable)",
    )
    parser.add_argument(
        "--account",
        default="",
        help="Bind contact labels to a specific account name",
    )
    args = parser.parse_args()

    name: str = args.name
    emails: list[str] = args.email
    labels: list[str] = args.label
    account: str = args.account

    # Check not already configured
    contacts = load_contacts()
    if name in contacts:
        print(f"Contact '{name}' already exists in contacts.toml")
        sys.exit(1)

    contact_dir = resolve.contacts_dir() / name
    if contact_dir.exists():
        print(f"Directory {contact_dir} already exists")
        sys.exit(1)

    # 1. Create contact directory with AGENTS.md + CLAUDE.md symlink
    contact_dir.mkdir(parents=True, exist_ok=True)
    agents_md = contact_dir / "AGENTS.md"
    agents_md.write_text(_generate_agents_md(name), encoding="utf-8")
    os.symlink("AGENTS.md", contact_dir / "CLAUDE.md")
    print(f"Created {contact_dir}/AGENTS.md")

    # 2. Update contacts.toml
    contacts[name] = Contact(
        emails=emails,
        labels=labels,
        account=account,
    )
    save_contacts(contacts)
    print("Updated contacts.toml")

    # 3. Add labels to account sync config if both --label and --account given
    if labels and account:
        from accounts import add_label_to_account

        for label in labels:
            added = add_label_to_account(account, label)
            if added:
                print(f"Added label '{label}' to account '{account}' in accounts.toml")

    # 4. Next steps
    print()
    print("Done! Next steps:")
    print(f"  - Edit {contact_dir}/AGENTS.md with relationship context")
    if not labels:
        print("  - Add --label flags or edit contacts.toml to map conversation labels")


if __name__ == "__main__":
    main()
