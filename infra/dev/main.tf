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

module "lambda" {
  source = "../modules/lambda"

  environment          = var.environment
  aws_region           = var.aws_region
  image_tag            = var.image_tag
  memory_size          = var.memory_size
  timeout              = var.timeout
  ssm_parameter_prefix = "/pktx/${var.environment}"

  environment_variables = {
    PKTX_DB_URL               = data.aws_ssm_parameter.database_url.value
    PKTX_PUBLIC_URL           = data.aws_ssm_parameter.pktx_public_url.value
    CLERK_JWKS_URL            = data.aws_ssm_parameter.clerk_jwks_url.value
    CLERK_ISSUER              = data.aws_ssm_parameter.clerk_issuer.value
    CLERK_OAUTH_CLIENT_ID     = data.aws_ssm_parameter.clerk_oauth_client_id.value
    CLERK_OAUTH_CLIENT_SECRET = data.aws_ssm_parameter.clerk_oauth_client_secret.value
    CLERK_WEBHOOK_SECRET      = data.aws_ssm_parameter.clerk_webhook_secret.value
    CLERK_SECRET_KEY          = data.aws_ssm_parameter.clerk_secret_key.value

    # Redirect URIs allowed for hosted MCP clients, on top of the loopback
    # patterns the app always allows. Not a secret, so it lives in tfvars
    # rather than SSM.
    PKTX_EXTRA_CLIENT_REDIRECT_URIS = join(",", var.extra_client_redirect_uris)

    # Allowed `azp` origins for REST session JWTs. Empty → the app defaults to
    # the PKTX_PUBLIC_URL origin; otherwise that origin is kept and the extra
    # origins are appended.
    CLERK_AUTHORIZED_PARTIES = length(var.authorized_parties) == 0 ? "" : join(",", concat(
      [regex("^[^:/]+://[^/]+", data.aws_ssm_parameter.pktx_public_url.value)],
      var.authorized_parties,
    ))
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }

  depends_on = [module.observability]
}

# SSM SecureString parameters for runtime secrets.
# Terraform creates each parameter with a placeholder value. Real values must be
# set manually before the first full terraform apply (see quickstart.md Step 4):
#   aws ssm put-parameter --name /pktx/dev/database_url --value "..." \
#     --type SecureString --overwrite
#
# lifecycle.ignore_changes = [value] prevents Terraform from reverting
# developer-set values on subsequent applies.

resource "aws_ssm_parameter" "database_url" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/database_url"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "clerk_secret_key" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/clerk_secret_key"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "pktx_public_url" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/pktx_public_url"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "clerk_oauth_client_id" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/clerk_oauth_client_id"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "clerk_oauth_client_secret" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/clerk_oauth_client_secret"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "clerk_publishable_key" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/clerk_publishable_key"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "clerk_jwks_url" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/clerk_jwks_url"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "clerk_issuer" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/clerk_issuer"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "aws_ssm_parameter" "clerk_webhook_secret" {
  #checkov:skip=CKV_AWS_337:Default AWS-managed SSM key (alias/aws/ssm) is sufficient; KMS CMK adds recurring cost without meaningful benefit for a personal app
  name  = "/pktx/${var.environment}/clerk_webhook_secret"
  type  = "SecureString"
  value = "TO_BE_SET"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Data sources read the current (possibly developer-overridden) value from SSM
# on every terraform apply, so Lambda env vars always reflect the live secret.
data "aws_ssm_parameter" "database_url" {
  name            = aws_ssm_parameter.database_url.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.database_url]
}

data "aws_ssm_parameter" "clerk_jwks_url" {
  name            = aws_ssm_parameter.clerk_jwks_url.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.clerk_jwks_url]
}

data "aws_ssm_parameter" "clerk_issuer" {
  name            = aws_ssm_parameter.clerk_issuer.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.clerk_issuer]
}

data "aws_ssm_parameter" "clerk_webhook_secret" {
  name            = aws_ssm_parameter.clerk_webhook_secret.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.clerk_webhook_secret]
}

data "aws_ssm_parameter" "clerk_secret_key" {
  name            = aws_ssm_parameter.clerk_secret_key.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.clerk_secret_key]
}

data "aws_ssm_parameter" "pktx_public_url" {
  name            = aws_ssm_parameter.pktx_public_url.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.pktx_public_url]
}

data "aws_ssm_parameter" "clerk_oauth_client_id" {
  name            = aws_ssm_parameter.clerk_oauth_client_id.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.clerk_oauth_client_id]
}

data "aws_ssm_parameter" "clerk_oauth_client_secret" {
  name            = aws_ssm_parameter.clerk_oauth_client_secret.name
  with_decryption = true
  depends_on      = [aws_ssm_parameter.clerk_oauth_client_secret]
}
