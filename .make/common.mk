.PHONY: build release test clippy check precommit install install-hooks clean init-python

# Build debug binary
build:
	cargo build

# Build release binary and symlink to .bin/
release:
	cargo build --release
	@mkdir -p .bin
	@ln -sf ../target/release/corky .bin/corky
	@echo "Installed .bin/corky -> target/release/corky"

# Run tests
test:
	cargo test

# Lint
clippy:
	cargo clippy -- -D warnings

# clippy + test
check: clippy test

# Pre-commit: clippy + test + audit-docs
precommit: check
	cargo run --quiet -- audit-docs

# Install to ~/.cargo/bin
install:
	cargo install --path .

# Install git hooks
install-hooks:
	@mkdir -p .git/hooks
	@printf '#!/bin/sh\nmake precommit\n' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Installed .git/hooks/pre-commit"

# Remove build artifacts
clean:
	cargo clean
	rm -f .bin/corky

# Set up Python venv (for wrapper development)
init-python: PY_VERSION = $(shell [ -f .python-version ] && \
	cat .python-version || echo "3.14")
init-python:
	@echo "Setting up Python $(PY_VERSION) venv for wrapper development..."
	@if command -v mise >/dev/null 2>&1; then \
		mise install; \
	fi
	uv venv .venv --python "$(PY_VERSION)" --no-project --clear --seed $(VENV_ARGS)
	uv pip install -e wrapper/
	@echo "Python wrapper installed in .venv (corky binary still comes from .bin/)"
