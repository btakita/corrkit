.PHONY: build release test clippy check install clean init-python

# Build debug binary
build:
	cargo build

# Build release binary and symlink to .bin/
release:
	cargo build --release
	@mkdir -p .bin
	@ln -sf ../target/release/corrkit .bin/corrkit
	@echo "Installed .bin/corrkit -> target/release/corrkit"

# Run tests
test:
	cargo test

# Lint
clippy:
	cargo clippy -- -D warnings

# clippy + test
check: clippy test

# Install to ~/.cargo/bin
install:
	cargo install --path .

# Remove build artifacts
clean:
	cargo clean
	rm -f .bin/corrkit

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
	@echo "Python wrapper installed in .venv (corrkit binary still comes from .bin/)"
