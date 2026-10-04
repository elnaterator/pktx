.PHONY: build run lint test typecheck audit check format help
unexport VIRTUAL_ENV

help:
	@echo "Backend Makefile targets:"
	@echo "  build     - Install Python dependencies"
	@echo "  run       - Start HTTP server locally"
	@echo "  lint      - Run ruff check + format check + pyright"
	@echo "  test      - Run pytest"
	@echo "  typecheck - Run pyright"
	@echo "  audit     - Scan locked runtime deps for known CVEs (pip-audit)"
	@echo "  check     - Run lint + typecheck + audit + test"
	@echo "  format    - Auto-format with ruff"

build:
	uv sync

run:
	uv run pktx

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

test:
	uv run pytest

typecheck:
	uv run pyright

# Waivers: one ID per line with why + expiry. Remove once a fix ships.
# PYSEC-2026-1325: ecdsa timing side channel, no fix upstream. Pulled in only by
#   python-jose, which signs/verifies with the cryptography backend. Expires 2027-01-01.
PIP_AUDIT_IGNORE := PYSEC-2026-1325

audit:
	@uv export --frozen --no-dev --no-emit-project --format requirements-txt > .audit-reqs.txt
	uvx pip-audit --strict --disable-pip --no-deps --progress-spinner off \
	  $(addprefix --ignore-vuln ,$(PIP_AUDIT_IGNORE)) -r .audit-reqs.txt; \
	  status=$$?; rm -f .audit-reqs.txt; exit $$status

check: lint audit test

format:
	uv run ruff format .
