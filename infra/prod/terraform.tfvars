environment        = "prod"
aws_region         = "us-west-2"
memory_size        = 512
timeout            = 30
log_retention_days = 14
error_threshold    = 1

# Public app config (not secrets; secrets are SSM-only, read by the app).
public_url            = "https://pktx.nathanhadzariga.com"
clerk_publishable_key = "pk_live_Y2xlcmsubmF0aGFuaGFkemFyaWdhLmNvbSQ"
clerk_issuer          = "https://clerk.nathanhadzariga.com"
clerk_oauth_client_id = "uou7A49adjxpELH3"

# Hosted MCP client callbacks (loopback clients need no entry here).
extra_client_redirect_uris = [
  "https://chatgpt.com/connector/oauth/*",
  "https://chatgpt.com/connector_platform_oauth_redirect",
  "https://claude.ai/api/mcp/auth_callback",
  "https://claude.com/api/mcp/auth_callback",
  "https://vscode.dev/redirect",
  "https://www.cursor.com/agents/mcp/oauth/callback",
]

# REST JWT `azp` origins on top of the public URL origin. Empty = public only.
authorized_parties = []
