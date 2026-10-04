.PHONY: build run lint test audit check format install help

help:
	@echo "Frontend Makefile targets:"
	@echo "  install - Install Node.js dependencies"
	@echo "  build   - Build production bundle"
	@echo "  run     - Start dev server"
	@echo "  lint    - Run ESLint"
	@echo "  test    - Run tests with Vitest"
	@echo "  audit   - Scan runtime deps for HIGH+ advisories (npm audit)"
	@echo "  check   - Run lint + audit + test"
	@echo "  format  - Auto-format code (no formatter configured yet)"

node_modules: package.json package-lock.json
	npm ci
	@touch node_modules

install: node_modules

build: node_modules
	npm run build

run: node_modules
	npm run dev

lint: node_modules
	npm run lint

test: node_modules
	npm run test

# Dev deps excluded: they never ship. Renovate surfaces their fixes as PRs.
audit: node_modules
	npm audit --audit-level=high --omit=dev

check: lint audit test

format: node_modules
	@echo "No formatter configured yet (consider adding prettier)"
