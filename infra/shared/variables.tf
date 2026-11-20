variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-west-2"
}

variable "github_sub_prefix" {
  description = <<-EOF
    Prefix of the GitHub OIDC `sub` claim for this repo. The repo uses immutable
    subject claims (owner and repo ids, not just names), so a renamed or re-created
    repo can't claim these roles. Read it with:
      gh api repos/<owner>/<repo>/actions/oidc/customization/sub --jq .sub_claim_prefix
  EOF
  type        = string
  default     = "repo:elnaterator@1914672/pktx@1152434568"
  validation {
    condition     = can(regex("^repo:[^:]+$", var.github_sub_prefix))
    error_message = "github_sub_prefix must look like repo:<owner>[@id]/<repo>[@id] (no trailing context)."
  }
}

variable "environments" {
  description = <<-EOT
    App environments CI may deploy, keyed by env name. `github_environment` is the
    GitHub Environment whose OIDC subject may assume that env's deploy role;
    `promotes_from` is the env whose ECR images it may copy (build once, promote).
  EOT
  type = map(object({
    github_environment = string
    promotes_from      = optional(string)
  }))
  default = {
    dev  = { github_environment = "dev" }
    prod = { github_environment = "production", promotes_from = "dev" }
  }
}
