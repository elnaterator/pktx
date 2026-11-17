# CI identity for GitHub Actions: an OIDC provider plus one read-only plan role
# and one deploy role per app environment. No long-lived AWS keys exist anywhere.
#
# This stack is applied by the owner only (`terraform -chdir=infra/shared apply`),
# never by CI: a role must not be able to widen its own permissions. CI only plans it.
#
# Deploy roles are resource-scoped to their env (pktx-<env>* names, /pktx/<env>/*
# SSM, keys tagged environment=<env>, that env's state). Roles they create must
# carry the env's permissions boundary, so a deploy role cannot mint a role more
# powerful than the Lambda execution role.

data "aws_caller_identity" "current" {}

locals {
  account = data.aws_caller_identity.current.account_id
  region  = var.aws_region
  oidc    = "token.actions.githubusercontent.com"

  ecr_repo   = "arn:aws:ecr:${local.region}:${local.account}:repository"
  lambda_fn  = "arn:aws:lambda:${local.region}:${local.account}:function"
  ssm_param  = "arn:aws:ssm:${local.region}:${local.account}:parameter"
  log_group  = "arn:aws:logs:${local.region}:${local.account}:log-group"
  alarm      = "arn:aws:cloudwatch:${local.region}:${local.account}:alarm"
  event_rule = "arn:aws:events:${local.region}:${local.account}:rule"
  kms_key    = "arn:aws:kms:${local.region}:${local.account}:key/*"
  iam_role   = "arn:aws:iam::${local.account}:role"
  iam_policy = "arn:aws:iam::${local.account}:policy"
  ddb_table  = "arn:aws:dynamodb:${local.region}:${local.account}:table"

  state_stacks = concat(keys(var.environments), ["shared"])
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.oidc}"
  client_id_list = ["sts.amazonaws.com"]
  # AWS validates GitHub's OIDC certs against its own trust store; the list is
  # required by the API but no longer consulted for this provider.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]

  tags = { managed_by = "terraform" }
}

# Trust only this repo, only the exact subject (PR / GitHub Environment).
data "aws_iam_policy_document" "trust" {
  for_each = merge(
    { plan = "repo:${var.github_repository}:pull_request" },
    { for env, cfg in var.environments : env => "repo:${var.github_repository}:environment:${cfg.github_environment}" },
  )

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc}:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc}:sub"
      values   = [each.value]
    }
  }
}

# ---------------------------------------------------------------------------
# Plan role: read-only, used by `terraform plan` on same-repo pull requests.
# Reading SSM SecureStrings (and the state that mirrors them) is unavoidable for
# a full refresh, so decrypt is allowed only through SSM for /pktx/*.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "plan" {
  name                 = "pktx-gha-plan"
  description          = "GitHub Actions: read-only terraform plan on pull requests"
  assume_role_policy   = data.aws_iam_policy_document.trust["plan"].json
  max_session_duration = 3600
  tags                 = { managed_by = "terraform" }
}

data "aws_iam_policy_document" "plan" {
  statement {
    sid       = "IamRead"
    actions   = ["iam:Get*", "iam:List*"]
    resources = ["*"]
  }
  statement {
    sid = "AccountWideDescribe"
    actions = [
      "cloudwatch:DescribeAlarms",
      "kms:ListAliases",
      "logs:DescribeLogGroups",
      "ssm:DescribeParameters",
    ]
    resources = ["*"]
  }
  statement {
    sid = "AppRead"
    actions = [
      "cloudwatch:ListTagsForResource",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetLifecyclePolicy",
      "ecr:GetRepositoryPolicy",
      "ecr:ListTagsForResource",
      "events:DescribeRule",
      "events:ListTagsForResource",
      "events:ListTargetsByRule",
      "lambda:Get*",
      "lambda:List*",
      "logs:ListTagsForResource",
      "logs:ListTagsLogGroup",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:ListTagsForResource",
    ]
    resources = [
      "${local.alarm}:pktx-*",
      "${local.ecr_repo}/pktx-*",
      "${local.event_rule}/pktx-*",
      "${local.lambda_fn}:pktx-*",
      "${local.log_group}:/aws/lambda/pktx-*",
      "${local.ssm_param}/pktx/*",
    ]
  }
  statement {
    sid       = "KmsRead"
    actions   = ["kms:DescribeKey", "kms:GetKeyPolicy", "kms:GetKeyRotationStatus", "kms:ListResourceTags"]
    resources = [local.kms_key]
  }
  statement {
    sid       = "SsmDecrypt"
    actions   = ["kms:Decrypt"]
    resources = [local.kms_key]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${local.region}.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "kms:EncryptionContext:PARAMETER_ARN"
      values   = ["${local.ssm_param}/pktx/*"]
    }
  }
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = [for s in local.state_stacks : "arn:aws:s3:::pktx-terraform-state-${s}/${s}/terraform.tfstate"]
  }
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [for s in local.state_stacks : "arn:aws:s3:::pktx-terraform-state-${s}"]
  }
}

resource "aws_iam_role_policy" "plan" {
  name   = "terraform-plan-read-only"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan.json
}

# ---------------------------------------------------------------------------
# Permissions boundary for roles a deploy role creates (the Lambda exec role).
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_boundary" {
  for_each = var.environments

  statement {
    sid       = "EcrPull"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = ["${local.ecr_repo}/pktx-${each.key}"]
  }
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid       = "SsmRead"
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = ["${local.ssm_param}/pktx/${each.key}/*"]
  }
  statement {
    sid       = "Kms"
    actions   = ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey"]
    resources = [local.kms_key]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group}:/aws/lambda/pktx-${each.key}", "${local.log_group}:/aws/lambda/pktx-${each.key}:*"]
  }
}

resource "aws_iam_policy" "lambda_boundary" {
  for_each = var.environments

  name        = "pktx-${each.key}-lambda-boundary"
  description = "Ceiling for roles created by the pktx-${each.key} deploy role"
  policy      = data.aws_iam_policy_document.lambda_boundary[each.key].json
  tags        = { environment = each.key, managed_by = "terraform" }
}

# ---------------------------------------------------------------------------
# Deploy roles: one per env, assumable only from its GitHub Environment.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "deploy" {
  for_each = var.environments

  name                 = "pktx-gha-deploy-${each.key}"
  description          = "GitHub Actions: build/promote and terraform apply for pktx-${each.key}"
  assume_role_policy   = data.aws_iam_policy_document.trust[each.key].json
  max_session_duration = 3600
  tags                 = { environment = each.key, managed_by = "terraform" }
}

data "aws_iam_policy_document" "deploy" {
  for_each = var.environments

  # --- Terraform state + lock (this env only) ---
  statement {
    sid       = "State"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::pktx-terraform-state-${each.key}/${each.key}/terraform.tfstate"]
  }
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::pktx-terraform-state-${each.key}"]
  }
  statement {
    sid       = "StateLock"
    actions   = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
    resources = ["${local.ddb_table}/pktx-terraform-locks-${each.key}"]
  }

  # --- Account-wide reads that cannot be resource-scoped ---
  statement {
    sid = "Describe"
    actions = [
      "cloudwatch:DescribeAlarms",
      "ecr:GetAuthorizationToken",
      "kms:ListAliases",
      "logs:DescribeLogGroups",
      "ssm:DescribeParameters",
    ]
    resources = ["*"]
  }

  # --- ECR: push/manage this env's repo; never delete repo or images ---
  statement {
    sid = "Ecr"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:CreateRepository",
      "ecr:DeleteLifecyclePolicy",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:GetLifecyclePolicy",
      "ecr:GetRepositoryPolicy",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:ListTagsForResource",
      "ecr:PutImage",
      "ecr:PutImageScanningConfiguration",
      "ecr:PutImageTagMutability",
      "ecr:PutLifecyclePolicy",
      # Lambda adds itself to a same-account repo's policy on function create.
      "ecr:SetRepositoryPolicy",
      "ecr:TagResource",
      "ecr:UntagResource",
      "ecr:UploadLayerPart",
    ]
    resources = ["${local.ecr_repo}/pktx-${each.key}"]
  }

  # --- Promotion: read-only pull from the env this one promotes from ---
  dynamic "statement" {
    for_each = each.value.promotes_from == null ? [] : [each.value.promotes_from]
    content {
      sid = "EcrPromoteFrom"
      actions = [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:DescribeImages",
        "ecr:GetDownloadUrlForLayer",
      ]
      resources = ["${local.ecr_repo}/pktx-${statement.value}"]
    }
  }

  # --- Lambda function (incl. URL, permissions, aliases) ---
  statement {
    sid       = "Lambda"
    actions   = ["lambda:*"]
    resources = ["${local.lambda_fn}:pktx-${each.key}", "${local.lambda_fn}:pktx-${each.key}:*"]
  }

  # --- IAM: only pktx-<env>-* roles, only under the env boundary ---
  statement {
    sid = "IamRead"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
    ]
    resources = ["${local.iam_role}/pktx-${each.key}-*"]
  }
  statement {
    sid = "IamWriteBounded"
    actions = [
      "iam:AttachRolePolicy",
      "iam:CreateRole",
      "iam:PutRolePermissionsBoundary",
      "iam:PutRolePolicy",
    ]
    resources = ["${local.iam_role}/pktx-${each.key}-*"]
    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [aws_iam_policy.lambda_boundary[each.key].arn]
    }
  }
  statement {
    sid = "IamManage"
    actions = [
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
      "iam:UpdateRoleDescription",
    ]
    resources = ["${local.iam_role}/pktx-${each.key}-*"]
  }
  statement {
    sid       = "IamPassExecRole"
    actions   = ["iam:PassRole"]
    resources = ["${local.iam_role}/pktx-${each.key}-lambda-exec"]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com"]
    }
  }
  statement {
    sid       = "IamReadAwsManagedPolicies"
    actions   = ["iam:GetPolicy", "iam:GetPolicyVersion"]
    resources = ["arn:aws:iam::aws:policy/*", "${local.iam_policy}/pktx-${each.key}-lambda-boundary"]
  }
  statement {
    sid       = "IamNeverDropBoundary"
    effect    = "Deny"
    actions   = ["iam:DeleteRolePermissionsBoundary"]
    resources = ["*"]
  }

  # --- KMS: only keys tagged for this env (Lambda env-var key) ---
  statement {
    sid       = "KmsCreateTagged"
    actions   = ["kms:CreateKey", "kms:TagResource"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/environment"
      values   = [each.key]
    }
  }
  statement {
    sid = "KmsEnvKey"
    actions = [
      "kms:CreateGrant",
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:EnableKeyRotation",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:GetKeyPolicy",
      "kms:GetKeyRotationStatus",
      "kms:ListResourceTags",
      "kms:PutKeyPolicy",
      "kms:ScheduleKeyDeletion",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:UpdateKeyDescription",
    ]
    resources = [local.kms_key]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/environment"
      values   = [each.key]
    }
  }
  statement {
    sid       = "KmsViaSsm"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [local.kms_key]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${local.region}.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "kms:EncryptionContext:PARAMETER_ARN"
      values   = ["${local.ssm_param}/pktx/${each.key}/*"]
    }
  }

  # --- SSM parameters (values are set by the owner; TF keeps placeholders) ---
  statement {
    sid = "Ssm"
    actions = [
      "ssm:AddTagsToResource",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:ListTagsForResource",
      "ssm:PutParameter",
      "ssm:RemoveTagsFromResource",
    ]
    resources = ["${local.ssm_param}/pktx/${each.key}/*"]
  }

  # --- Observability + keep-warm ---
  statement {
    sid = "Logs"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteRetentionPolicy",
      "logs:ListTagsForResource",
      "logs:ListTagsLogGroup",
      "logs:PutRetentionPolicy",
      "logs:TagLogGroup",
      "logs:TagResource",
      "logs:UntagLogGroup",
      "logs:UntagResource",
    ]
    resources = ["${local.log_group}:/aws/lambda/pktx-${each.key}", "${local.log_group}:/aws/lambda/pktx-${each.key}:*"]
  }
  statement {
    sid = "Alarms"
    actions = [
      "cloudwatch:ListTagsForResource",
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
    ]
    resources = ["${local.alarm}:pktx-${each.key}-*"]
  }
  statement {
    sid = "Events"
    actions = [
      "events:DeleteRule",
      "events:DescribeRule",
      "events:ListTagsForResource",
      "events:ListTargetsByRule",
      "events:PutRule",
      "events:PutTargets",
      "events:RemoveTargets",
      "events:TagResource",
      "events:UntagResource",
    ]
    resources = ["${local.event_rule}/pktx-${each.key}-*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  for_each = var.environments

  name   = "deploy-pktx-${each.key}"
  role   = aws_iam_role.deploy[each.key].id
  policy = data.aws_iam_policy_document.deploy[each.key].json
}
