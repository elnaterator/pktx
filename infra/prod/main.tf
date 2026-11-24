# Observability must be created before the Lambda function to ensure the CloudWatch
# Log Group exists with the correct retention policy before Lambda can auto-create
# an unretained one on first invocation.
module "observability" {
  source = "../modules/observability"

  environment          = var.environment
  lambda_function_name = "pktx-${var.environment}"
  log_retention_days   = var.log_retention_days
  error_threshold      = var.error_threshold

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

data "aws_caller_identity" "current" {}

module "lambda" {
  source = "../modules/lambda"

  environment          = var.environment
  aws_region           = var.aws_region
  image_digest         = var.image_digest
  memory_size          = var.memory_size
  timeout              = var.timeout
  ssm_parameter_prefix = "/pktx/${var.environment}"

  # Created by infra/shared; required for CI deploy roles to manage the exec role.
  permissions_boundary_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/pktx-${var.environment}-lambda-boundary"

  # Secrets are not passed in: the app reads these SecureStrings under
  # /pktx/<env>/ at cold start with the exec role (backend/src/pktx/secrets.py),
  # so no secret value reaches Terraform state or the Lambda config. Owners set
  # them out of band (docs/deployment.md); keep in sync with SECRET_PARAMETERS.
  secret_names = [
    "database_url",
    "clerk_secret_key",
    "clerk_webhook_secret",
    "clerk_oauth_client_secret",
  ]

  environment_variables = {
    PKTX_SSM_PREFIX = "/pktx/${var.environment}"
    PKTX_VERSION    = var.app_version

    # Public configuration (served to browsers / OAuth clients), so tfvars.
    PKTX_PUBLIC_URL       = var.public_url
    CLERK_PUBLISHABLE_KEY = var.clerk_publishable_key
    CLERK_ISSUER          = var.clerk_issuer
    CLERK_JWKS_URL        = "${var.clerk_issuer}/.well-known/jwks.json"
    CLERK_OAUTH_CLIENT_ID = var.clerk_oauth_client_id

    # Redirect URIs allowed for hosted MCP clients, on top of the loopback
    # patterns the app always allows.
    PKTX_EXTRA_CLIENT_REDIRECT_URIS = join(",", var.extra_client_redirect_uris)

    # Allowed `azp` origins for REST session JWTs. Empty → the app defaults to
    # the PKTX_PUBLIC_URL origin; otherwise that origin is kept and the extra
    # origins are appended.
    CLERK_AUTHORIZED_PARTIES = length(var.authorized_parties) == 0 ? "" : join(",", concat(
      [regex("^[^:/]+://[^/]+", var.public_url)],
      var.authorized_parties,
    ))
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }

  depends_on = [module.observability]
}

# SSM parameters used to be Terraform-managed (placeholders + decrypting data
# sources), which put every secret in state and required CI to decrypt them.
# Forget them without deleting: secrets stay in SSM, owned out of band; the
# non-secret ones are now tfvars and get deleted by hand after cutover.

removed {
  from = aws_ssm_parameter.database_url

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.clerk_secret_key

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.pktx_public_url

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.clerk_oauth_client_id

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.clerk_oauth_client_secret

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.clerk_publishable_key

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.clerk_jwks_url

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.clerk_issuer

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_ssm_parameter.clerk_webhook_secret

  lifecycle {
    destroy = false
  }
}
