variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-west-2"
}

variable "github_repository" {
  description = "owner/name of the GitHub repository whose workflows may assume the CI roles."
  type        = string
  default     = "elnaterator/pktx"
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
