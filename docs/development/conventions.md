# Conventions

## Code style

- Use `serde` derive for all data types
- Use `anyhow` for application errors, `thiserror` for domain errors
- Use `toml_edit` for format-preserving TOML edits (add-label)
- Use `std::process::Command` for git operations (not `git2`)
- Use `regex` + `once_cell::Lazy` for compiled regex patterns
- Keep sync, draft, mailbox, contact logic in separate modules

## Instruction files

- `AGENTS.md` is canonical (committed). `CLAUDE.md` is a symlink.
- Personal overrides: `CLAUDE.local.md` / `AGENTS.local.md` (gitignored).
- Each module directory can contain its own `AGENTS.md` with package-specific conventions.
- Keep the root `AGENTS.md` focused on cross-cutting concerns.
- **Actionable over informational.** Instruction files contain the minimum needed to generate correct code. Reference material belongs in `README.md`.
- **Update with the code.** When a change affects patterns, conventions, or module boundaries, update instruction files as part of the same change.
- Combined root + package files should stay well under 1000 lines.

## Version management

- Never bump versions automatically — the user will bump versions explicitly.
- Commits that include a version change should include the version number in the commit message.
- Use `BREAKING CHANGE:` prefix in VERSIONS.md entries for incompatible changes.
- Update `SPEC.md` when corky functionality changes (commands, formats, algorithms).

## Workflow

Follow a research → plan → implement cycle:

1. **Research** — Read the relevant code deeply. Document findings in `research.md`.
2. **Plan** — Write a detailed implementation plan in `plan.md`.
3. **Todo** — Produce a granular todo list from the approved plan.
4. **Implement** — Execute the plan. Run `make check` continuously.
5. **Precommit** — Run `make precommit` and `corky audit-docs` before committing.
