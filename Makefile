.PHONY: build run run-local lint test check format tf-lint tf-check ci-lint deploy release setup help

AWS_REGION ?= us-west-2

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install all managed dependencies (Python + Node)
	cd backend && uv sync
	cd frontend && npm ci

build: ## Build frontend then backend
	$(MAKE) -C frontend build
	$(MAKE) -C backend build

run: ## Start via Docker Compose
	docker compose up --build

run-local: ## Build frontend then run backend locally
	$(MAKE) -C frontend build
	$(MAKE) -C backend run

lint: ## Lint both frontend and backend
	$(MAKE) -C frontend lint
	$(MAKE) -C backend lint

test: ## Test both frontend and backend
	$(MAKE) -C frontend test
	$(MAKE) -C backend test

check: ## Run lint + audit + test for both + terraform fmt check + Trivy IaC scan + CI/script lint
	$(MAKE) -C frontend check
	$(MAKE) -C backend check
	$(MAKE) tf-check
	$(MAKE) ci-lint

ci-lint: ## Lint GitHub workflows (actionlint) and deploy scripts (shellcheck)
	@command -v actionlint >/dev/null || { echo "actionlint not found: brew install actionlint"; exit 1; }
	@command -v shellcheck >/dev/null || { echo "shellcheck not found: brew install shellcheck"; exit 1; }
	actionlint
	shellcheck -x scripts/deploy/*.sh

format: ## Format both frontend and backend
	$(MAKE) -C frontend format
	$(MAKE) -C backend format

tf-lint: ## Check Terraform formatting (infra/)
	terraform fmt -check -recursive infra/

tf-check: ## Run tf-lint + Trivy IaC scan (infra/)
	$(MAKE) tf-lint
	@command -v trivy >/dev/null || { echo "trivy not found: brew install trivy (https://trivy.dev)"; exit 1; }
	trivy config --quiet --exit-code 1 --severity HIGH,CRITICAL infra/

deploy: ## Break-glass deploy from a clean HEAD (ENV=dev builds; ENV=prod promotes the dev-verified image). CI normally does this.
ifndef ENV
	$(error ENV is required. Usage: make deploy ENV=dev)
endif
	@[ "$(ENV)" = "dev" ] || [ "$(ENV)" = "prod" ] || \
	  { echo "Error: ENV must be 'dev' or 'prod', got '$(ENV)'"; exit 1; }
	@[ -z "$$(git status --porcelain)" ] || \
	  { echo "Error: working tree is dirty; deploys are built from a commit"; exit 1; }
	@set -e; \
	  SHA=$$(git rev-parse HEAD); \
	  scripts/deploy/ensure-base.sh $(ENV); \
	  if [ "$(ENV)" = "dev" ]; then \
	    DIGEST=$$(scripts/deploy/build-push.sh $$SHA); \
	    VERSION=dev-$$(git rev-parse --short=7 HEAD); \
	  else \
	    DIGEST=$$(scripts/deploy/promote.sh $$SHA); \
	    VERSION=$$(git tag --points-at HEAD --list 'v*' --sort=-version:refname | head -n1); \
	    VERSION=$${VERSION:-prod-$$(git rev-parse --short=7 HEAD)}; \
	  fi; \
	  URL=$$(scripts/deploy/apply.sh $(ENV) $$DIGEST $$VERSION); \
	  scripts/deploy/smoke.sh $$URL $$VERSION; \
	  if [ "$(ENV)" = "dev" ]; then scripts/deploy/mark-verified.sh $$SHA; fi; \
	  echo "==> Deployed $$SHA ($$DIGEST) to $(ENV): $$URL"

release: ## Publish a CalVer GitHub Release (vYYYY.MM.DD[.N]) for SHA (default origin/main); triggers the prod deploy. DRY_RUN=1 to preview.
	DRY_RUN=$(DRY_RUN) scripts/deploy/release.sh $(SHA)
