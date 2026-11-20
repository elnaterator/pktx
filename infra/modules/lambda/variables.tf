variable "environment" {
  description = "Environment name (dev or prod)."
  type        = string
}

variable "aws_region" {
  description = "AWS region."
  type        = string
}

variable "image_digest" {
  description = "Digest (sha256:...) of the image in this env's ECR repo that Lambda runs."
  type        = string
  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.image_digest))
    error_message = "image_digest must look like sha256:<64 hex chars>."
  }
}

variable "images_to_keep" {
  description = "Release images (tag prefix sha-) kept in ECR for rollback."
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Lambda memory in MB."
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 30
}

variable "ssm_parameter_prefix" {
  description = "SSM parameter path prefix for this environment (e.g., /pktx/dev)."
  type        = string
}

variable "environment_variables" {
  description = "Environment variables injected into the Lambda function at runtime."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "keep_warm_enabled" {
  description = "Whether the EventBridge keep-warm rule pings the Lambda every 5 minutes to avoid cold starts."
  type        = bool
  default     = true
}

variable "tags" {
  description = "AWS resource tags applied to all resources in this module."
  type        = map(string)
  default     = {}
}

variable "permissions_boundary_arn" {
  description = "Permissions boundary for the Lambda execution role (infra/shared: pktx-<env>-lambda-boundary)."
  type        = string
  default     = null
}
