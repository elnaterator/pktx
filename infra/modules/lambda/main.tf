data "aws_caller_identity" "current" {}

# ECR repository for the application container image
resource "aws_ecr_repository" "app" {
  #checkov:skip=CKV_AWS_136:Default AWS-managed encryption is sufficient for a personal app; KMS CMK adds cost/complexity without meaningful benefit
  #checkov:skip=CKV_AWS_51:Mutable image tags are required for the dev/prod deployment workflow (same :latest or :sha tag is re-pushed per environment)
  name = "pktx-${var.environment}"
  #trivy:ignore:AWS-0031 Mutable tags required: deploy re-pushes the same tag per environment
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

# IAM role assumed by the Lambda function at runtime
resource "aws_iam_role" "lambda_exec" {
  name = "pktx-${var.environment}-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

# Allow Lambda to pull its container image from ECR
resource "aws_iam_role_policy" "ecr_pull" {
  name = "ecr-pull"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
        ]
        Resource = aws_ecr_repository.app.arn
      },
      {
        # ecr:GetAuthorizationToken cannot be scoped to a repository ARN
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      }
    ]
  })
}

# Allow Lambda to read application secrets from SSM Parameter Store
resource "aws_iam_role_policy" "ssm_read" {
  name = "ssm-read"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_parameter_prefix}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
        ]
        # AWS-managed SSM key; resource scope not supported for alias/aws/ssm
        Resource = "arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:key/alias/aws/ssm"
      }
    ]
  })
}

# AWS-managed policy granting CloudWatch Logs write access
resource "aws_iam_role_policy_attachment" "cw_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# KMS key used to encrypt Lambda environment variables at rest
resource "aws_kms_key" "lambda_env" {
  description             = "Encrypts Lambda ${var.environment} environment variables at rest"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = var.tags

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowLambdaExecutionRoleUsage"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda_exec.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Resource = "*"
      }
    ]
  })
}

# Allow the Lambda execution role to decrypt environment variables using the KMS key
resource "aws_iam_role_policy" "lambda_env_kms" {
  name = "lambda-env-kms-decrypt"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Resource = aws_kms_key.lambda_env.arn
      }
    ]
  })
}

# Lambda function running the application as a container image
resource "aws_lambda_function" "app" {
  #checkov:skip=CKV_AWS_50:X-Ray tracing deferred to future — adds cost/complexity not warranted for a personal app (research Decision 4)
  #checkov:skip=CKV_AWS_117:No VPC required for a personal app with no private resources to isolate
  #checkov:skip=CKV_AWS_116:No DLQ required — Lambda errors are surfaced via CloudWatch alarm; async retry not applicable to synchronous HTTP workload
  #checkov:skip=CKV_AWS_272:Code signing not warranted for a personal app; images are built and pushed by the developer directly
  #checkov:skip=CKV_AWS_115:No reserved concurrency limit set — personal app with low traffic; limiting concurrency would cause avoidable throttling
  #checkov:skip=CKV2_AWS_75:Open CORS is intentional — app must be accessible from any browser origin and MCP clients
  function_name = "pktx-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  architectures = ["arm64"]
  memory_size   = var.memory_size
  timeout       = var.timeout
  kms_key_arn   = aws_kms_key.lambda_env.arn

  environment {
    variables = var.environment_variables
  }

  tags = var.tags
}

# Allow unauthenticated public invocation via the Function URL.
# IAM auth is skipped at the URL level; Clerk JWT validation enforces auth in the app.
# Both InvokeFunctionUrl AND InvokeFunction are required for Function URL access.
resource "aws_lambda_permission" "allow_public_url" {
  #checkov:skip=CKV_AWS_301:Public access is intentional — IAM auth is incompatible with browser and MCP clients; Clerk JWT validation enforces auth at the app layer
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.app.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "allow_invoke_via_url" {
  #checkov:skip=CKV_AWS_301:Public access is intentional — IAM auth is incompatible with browser and MCP clients; Clerk JWT validation enforces auth at the app layer
  statement_id  = "FunctionURLAllowInvokeFunction"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "*"
}

# Keep-warm: EventBridge invokes the Lambda every 5 minutes with a synthetic
# GET /health event (API Gateway payload v2 shape) so one execution environment
# stays warm and interactive requests avoid cold starts. The Lambda Web Adapter
# in the container translates the payload into a real HTTP request; /health is
# public and does not touch the database. Classic EventBridge rule (not
# Scheduler) — Lambda targets use resource-based permissions, no execution role.
resource "aws_cloudwatch_event_rule" "keep_warm" {
  count = var.keep_warm_enabled ? 1 : 0

  name                = "pktx-${var.environment}-keep-warm"
  description         = "Ping the pktx-${var.environment} Lambda every 5 minutes to keep one instance warm"
  schedule_expression = "rate(5 minutes)"

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "keep_warm" {
  count = var.keep_warm_enabled ? 1 : 0

  rule      = aws_cloudwatch_event_rule.keep_warm[0].name
  target_id = "pktx-${var.environment}-keep-warm"
  arn       = aws_lambda_function.app.arn

  input = jsonencode({
    version        = "2.0"
    routeKey       = "$default"
    rawPath        = "/health"
    rawQueryString = ""
    headers        = { "x-keep-warm" = "true" }
    requestContext = {
      http = {
        method    = "GET"
        path      = "/health"
        protocol  = "HTTP/1.1"
        sourceIp  = "127.0.0.1"
        userAgent = "keep-warm"
      }
    }
    isBase64Encoded = false
  })
}

resource "aws_lambda_permission" "allow_keep_warm" {
  count = var.keep_warm_enabled ? 1 : 0

  statement_id  = "AllowEventBridgeKeepWarm"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.keep_warm[0].arn
}

# Public HTTPS endpoint for the Lambda function (no auth at URL level;
# Clerk JWT validation is enforced by the application on every request)
resource "aws_lambda_function_url" "app" {
  #checkov:skip=CKV_AWS_258:AuthType=NONE is intentional — IAM auth is incompatible with browser and MCP clients; Clerk JWT validation enforces auth at the app layer
  function_name      = aws_lambda_function.app.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = ["*"]
    allow_methods = ["*"]
    allow_headers = ["*"]
  }
}
