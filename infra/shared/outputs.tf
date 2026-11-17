output "plan_role_arn" {
  description = "Read-only role for `terraform plan` on pull requests (GitHub repo variable AWS_PLAN_ROLE_ARN)."
  value       = aws_iam_role.plan.arn
}

output "deploy_role_arns" {
  description = "Deploy role per env (GitHub Environment variable AWS_ROLE_ARN on the matching Environment)."
  value       = { for env, role in aws_iam_role.deploy : env => role.arn }
}

output "lambda_permissions_boundary_arns" {
  description = "Boundary every role a deploy role creates must carry, per env."
  value       = { for env, p in aws_iam_policy.lambda_boundary : env => p.arn }
}
