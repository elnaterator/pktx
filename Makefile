.PHONY: build run run-local lint test check format tf-lint tf-check deploy setup help

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

check: ## Run lint + audit + test for both + terraform fmt check + Trivy IaC scan
	$(MAKE) -C frontend check
	$(MAKE) -C backend check
	$(MAKE) tf-check

format: ## Format both frontend and backend
	$(MAKE) -C frontend format
	$(MAKE) -C backend format

tf-lint: ## Check Terraform formatting (infra/)
	terraform fmt -check -recursive infra/

tf-check: ## Run tf-lint + Trivy IaC scan (infra/)
	$(MAKE) tf-lint
	@command -v trivy >/dev/null || { echo "trivy not found: brew install trivy (https://trivy.dev)"; exit 1; }
	trivy config --quiet --exit-code 1 --severity HIGH,CRITICAL infra/

deploy: ## Build image, push to ECR, and apply Terraform (requires ENV=dev|prod)
ifndef ENV
	$(error ENV is required. Usage: make deploy ENV=dev)
endif
	@[ "$(ENV)" = "dev" ] || [ "$(ENV)" = "prod" ] || \
	  { echo "Error: ENV must be 'dev' or 'prod', got '$(ENV)'"; exit 1; }
	@echo "==> [1/5] terraform init (infra/$(ENV))"
	terraform -chdir=infra/$(ENV) init -input=false
	@echo "==> [2/5] ensure ECR repository and SSM parameters exist"
	terraform -chdir=infra/$(ENV) apply \
	  -target=module.lambda.aws_ecr_repository.app \
	  -target=aws_ssm_parameter.database_url \
	  -target=aws_ssm_parameter.clerk_publishable_key \
	  -target=aws_ssm_parameter.clerk_jwks_url \
	  -target=aws_ssm_parameter.clerk_issuer \
	  -target=aws_ssm_parameter.clerk_webhook_secret \
	  -target=aws_ssm_parameter.clerk_secret_key \
	  -auto-approve
	@echo "==> [3/5] build and push Docker image to ECR"
	@set -e; \
	  ECR_URL=$$(terraform -chdir=infra/$(ENV) output -raw ecr_repository_url); \
	  ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text); \
	  CLERK_PK=$$(aws ssm get-parameter \
	    --name /pktx/$(ENV)/clerk_publishable_key \
	    --with-decryption \
	    --query Parameter.Value \
	    --output text \
	    --region $(AWS_REGION)); \
	  aws ecr get-login-password --region $(AWS_REGION) | \
	    docker login --username AWS --password-stdin $${ACCOUNT_ID}.dkr.ecr.$(AWS_REGION).amazonaws.com; \
	  docker buildx build --platform linux/arm64 --provenance=false \
	    --build-arg VITE_CLERK_PUBLISHABLE_KEY=$${CLERK_PK} \
	    --load -t $${ECR_URL}:latest .; \
	  docker push $${ECR_URL}:latest
	@echo "==> [4/5] terraform apply (full)"
	terraform -chdir=infra/$(ENV) apply
	@echo "==> [5/5] force Lambda to pull latest image from ECR"
	@set -e; \
	  ECR_URL=$$(terraform -chdir=infra/$(ENV) output -raw ecr_repository_url); \
	  DIGEST=$$(aws ecr describe-images \
	    --repository-name pktx-$(ENV) \
	    --image-ids imageTag=latest \
	    --query 'imageDetails[0].imageDigest' \
	    --output text \
	    --region $(AWS_REGION)); \
	  aws lambda update-function-code \
	    --function-name pktx-$(ENV) \
	    --image-uri $${ECR_URL}@$${DIGEST} \
	    --region $(AWS_REGION) \
	    --output json | jq -r '"    updated to " + .CodeSha256'
	@echo ""
	@echo "==> Deployed. Function URL:"
	@terraform -chdir=infra/$(ENV) output -raw lambda_function_url 2>/dev/null || true
