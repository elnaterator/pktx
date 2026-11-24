variable "environment" {
  description = "Environment name. Used as a suffix in all resource names."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be 'dev' or 'prod'."
  }
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-west-2"
}

variable "image_digest" {
  description = <<-EOT
    Digest (sha256:...) of the image Lambda runs. No default: always passed by
    scripts/deploy/apply.sh (deploy) or scripts/deploy/current-digest.sh (plan).
  EOT
  type        = string
}

variable "app_version" {
  description = <<-EOT
    Release the app reports (PKTX_VERSION: /health, MCP serverInfo, UI badge):
    the release tag in prod, dev-<short sha> in dev. Deploy-time config so one
    image serves both envs. No default: always passed by scripts/deploy/apply.sh
    (deploy) or scripts/deploy/current-version.sh (plan).
  EOT
  type        = string
}

variable "memory_size" {
  description = "Lambda function memory allocation in MB."
  type        = number
  default     = 512
  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "memory_size must be between 128 and 10240 MB."
  }
}

variable "timeout" {
  description = "Lambda function timeout in seconds."
  type        = number
  default     = 30
  validation {
    condition     = var.timeout >= 1 && var.timeout <= 900
    error_message = "timeout must be between 1 and 900 seconds."
  }
}

variable "log_retention_days" {
  description = "Number of days to retain Lambda CloudWatch logs."
  type        = number
  default     = 14
}

variable "error_threshold" {
  description = "Number of Lambda errors in one period to trigger the CloudWatch alarm."
  type        = number
  default     = 1
}

variable "extra_client_redirect_uris" {
  description = <<-EOT
    Redirect URI patterns allowed for hosted (non-loopback) MCP clients, in
    addition to the loopback patterns the app always allows. Wildcards are
    supported. ChatGPT derives a per-connector callback under
    https://chatgpt.com/connector/oauth/, so it needs a wildcard entry.
  EOT
  type        = list(string)
  default     = []
}

variable "authorized_parties" {
  description = <<-EOT
    Extra origins (scheme://host[:port]) whose Clerk session JWTs the REST API
    accepts, checked against the token's `azp` claim. The PKTX_PUBLIC_URL origin
    is always allowed; empty = public origin only.
  EOT
  type        = list(string)
  default     = []
}

# Public app configuration. None of these are secrets: the publishable key and
# issuer are served to browsers and the OAuth client id appears in authorize
# redirects. Secrets live only in SSM (see secret_names in main.tf).
variable "public_url" {
  description = "Public base URL of the app (PKTX_PUBLIC_URL), no trailing slash."
  type        = string
  validation {
    condition     = can(regex("^https://[^/]+$", var.public_url))
    error_message = "public_url must be https://host with no path or trailing slash."
  }
}

variable "clerk_publishable_key" {
  description = "Clerk publishable key (pk_test_/pk_live_), injected into index.html."
  type        = string
  validation {
    condition     = can(regex("^pk_(test|live)_", var.clerk_publishable_key))
    error_message = "clerk_publishable_key must start with pk_test_ or pk_live_."
  }
}

variable "clerk_issuer" {
  description = "Clerk frontend API URL (JWT issuer); the JWKS URL is derived from it."
  type        = string
  validation {
    condition     = can(regex("^https://[^/]+$", var.clerk_issuer))
    error_message = "clerk_issuer must be https://host with no path or trailing slash."
  }
}

variable "clerk_oauth_client_id" {
  description = "Client id of the Clerk OAuth app the MCP OAuth proxy uses upstream."
  type        = string
}
