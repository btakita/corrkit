"""
Validate a draft markdown file has required fields and correct format.

Usage:
  corrkit validate-draft drafts/2026-02-19-example.md
  corrkit validate-draft drafts/*.md
"""

import argparse
import re
import sys
from pathlib import Path

META_RE = re.compile(r"^\*\*(.+?)\*\*:\s*(.+)$", re.MULTILINE)

REQUIRED_FIELDS = {"To"}
RECOMMENDED_FIELDS = {"Status", "Author"}
VALID_STATUSES = {"draft", "review", "approved", "sent"}


def validate_draft(path: Path) -> list[str]:
    """Validate a draft file. Returns list of issues (empty = valid)."""
    issues: list[str] = []

    if not path.exists():
        return [f"File not found: {path}"]

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Check for subject heading
    has_subject = any(line.startswith("# ") for line in lines)
    if not has_subject:
        issues.append("Missing subject: no '# Subject' heading found")

    # Parse metadata fields
    meta: dict[str, str] = {}
    for m in META_RE.finditer(text):
        meta[m.group(1)] = m.group(2).strip()

    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in meta:
            issues.append(f"Missing required field: **{field}**")

    # Recommended fields (warn, don't error)
    for field in RECOMMENDED_FIELDS:
        if field not in meta:
            issues.append(f"Warning: missing recommended field: **{field}**")

    # Status validation
    status = meta.get("Status", "").lower()
    if status and status not in VALID_STATUSES:
        issues.append(
            f"Invalid status '{meta['Status']}'. "
            f"Valid: {', '.join(sorted(VALID_STATUSES))}"
        )

    # Check status is 'review' (common mistake: leaving as 'draft')
    if status == "draft":
        issues.append(
            "Warning: Status is 'draft'. Set to 'review' when ready for Brian"
        )

    # Check for --- separator
    has_separator = any(line.strip() == "---" for line in lines)
    if not has_separator:
        issues.append("Missing '---' separator between metadata and body")

    # Check body exists after separator
    if has_separator:
        sep_idx = next(i for i, line in enumerate(lines) if line.strip() == "---")
        body = "\n".join(lines[sep_idx + 1 :]).strip()
        if not body:
            issues.append("Warning: empty body after --- separator")

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate draft markdown files"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Draft markdown file(s) to validate",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in args.files]
    all_ok = True

    for path in paths:
        issues = validate_draft(path)
        if issues:
            all_ok = False
            errors = [i for i in issues if not i.startswith("Warning:")]
            warnings = [i for i in issues if i.startswith("Warning:")]
            print(f"{path}:")
            for issue in errors:
                print(f"  ERROR: {issue}")
            for issue in warnings:
                print(f"  {issue}")
            print()
        else:
            print(f"{path}: OK")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
