environment        = "prod"
aws_region         = "us-west-2"
image_tag          = "latest"
memory_size        = 512
timeout            = 30
log_retention_days = 14
error_threshold    = 1

# Hosted MCP client callbacks (loopback clients need no entry here).
extra_client_redirect_uris = [
  "https://chatgpt.com/connector/oauth/*",
  "https://chatgpt.com/connector_platform_oauth_redirect",
  "https://claude.ai/api/mcp/auth_callback",
  "https://claude.com/api/mcp/auth_callback",
  "https://vscode.dev/redirect",
  "cursor://anysphere.cursor-mcp/oauth/callback",
]

# REST JWT `azp` origins on top of the public URL origin. Empty = public only.
authorized_parties = []
