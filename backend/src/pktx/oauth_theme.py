"""pktx look for the HTML pages FastMCP's OAuth proxy renders itself.

The consent screen (``/consent``) and the proxy's error pages (``/authorize``,
``/auth/callback``) come from FastMCP with a light, generic theme and no styling
hook. ``ThemedAuthPagesMiddleware`` appends a ``<style>`` block to those HTML
responses so they match the SPA (dark, monospace, green accent). Their CSP
already allows inline styles; only presentation changes — markup, form fields
and security behavior stay FastMCP's.
"""

from __future__ import annotations

import base64

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Paths whose HTML responses are FastMCP-rendered OAuth pages.
THEMED_PATHS = frozenset({"/consent", "/authorize", "/auth/callback"})

# Square app icon: green "p" on the app background. Also advertised as the MCP
# server icon, so clients that show server icons get it too.
_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" fill="#1a1a1a"/>'
    '<rect x="18" y="16" width="8" height="36" fill="#52b788"/>'
    '<circle cx="34" cy="28" r="10" fill="none" stroke="#52b788" stroke-width="8"/>'
    "</svg>"
)
ICON_DATA_URI = (
    "data:image/svg+xml;base64," + base64.b64encode(_ICON_SVG.encode()).decode()
)

# Mirrors frontend/src/index.css tokens. Selectors match FastMCP's
# utilities/ui.py + oauth_proxy/ui.py; appended last, so equal specificity wins.
THEME_CSS = """
:root {
  --bg: #1a1a1a;
  --bg-input: #141414;
  --bg-hover: #222222;
  --border: #2a2a2a;
  --text: #e0e0e0;
  --text-2: #b3b3b3;
  --muted: #949494;
  --green: #52b788;
  --green-dim: #40916c;
  --green-bg: rgba(82, 183, 136, 0.07);
  --warn: #ffaa00;
  --warn-bg: rgba(255, 170, 0, 0.08);
  --error: #ff4444;
  --error-bg: rgba(255, 68, 68, 0.08);
  --mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', 'Cascadia Code',
    ui-monospace, monospace;
  color-scheme: dark;
}
body {
  background:
    radial-gradient(80% 60% at 50% 0%, rgba(82, 183, 136, 0.08), transparent 70%),
    var(--bg);
  color: var(--text);
  font-family: var(--mono);
  -webkit-font-smoothing: antialiased;
}
.container {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-top: 3px solid var(--green);
  border-radius: 0;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
  max-width: 34rem;
  text-align: left;
}
.logo {
  width: 48px;
  margin: 0 0 1.25rem;
}
h1 {
  color: var(--text);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  margin-bottom: 1.25rem;
}
.info-box {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  margin-bottom: 1.25rem;
  color: var(--text-2);
  font-size: 0.875rem;
  line-height: 1.6;
  text-align: left;
}
.info-box strong {
  color: var(--green);
  font-weight: 600;
}
.info-box .server-name-link {
  color: var(--green);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.info-box.error {
  background: var(--error-bg);
  border: 1px solid var(--error);
  padding: 0.75rem 1rem;
  color: var(--text);
}
.cimd-badge {
  background: var(--green-bg);
  border: 1px solid var(--green-dim);
  border-radius: 0;
  color: var(--text-2);
  font-size: 0.8125rem;
  text-align: left;
}
.cimd-badge strong, .cimd-check {
  color: var(--green);
}
.redirect-section {
  background: var(--warn-bg);
  border: 1px solid rgba(255, 170, 0, 0.45);
  border-left: 3px solid var(--warn);
  border-radius: 0;
  text-align: left;
}
.redirect-section .label {
  color: var(--warn);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.redirect-section .value {
  color: var(--text);
  font-family: var(--mono);
  font-size: 0.8125rem;
}
details {
  text-align: left;
}
summary {
  color: var(--muted);
  font-size: 0.8125rem;
}
summary:hover {
  color: var(--text);
}
.detail-box {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0;
}
.detail-row {
  border-bottom-color: var(--border);
}
.detail-label {
  color: var(--muted);
  font-size: 0.75rem;
}
.detail-value {
  color: var(--text);
  font-family: var(--mono);
}
.button-group {
  justify-content: stretch;
}
button {
  border-radius: 0;
  font-family: var(--mono);
  font-weight: 600;
  flex: 1;
}
button:hover {
  transform: none;
  box-shadow: none;
}
button:focus-visible {
  outline: 2px solid var(--green);
  outline-offset: 2px;
}
.btn-approve, .btn-primary {
  background: var(--green);
  color: var(--bg);
}
.btn-approve:hover, .btn-primary:hover {
  background: var(--green-dim);
}
.btn-deny, .btn-secondary {
  background: transparent;
  color: var(--text-2);
  border: 1px solid var(--border);
}
.btn-deny:hover, .btn-secondary:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.message, .close-instruction, .help-text {
  color: var(--text-2);
}
.status-icon.success {
  background: var(--green-bg);
  color: var(--green);
}
.status-icon.error {
  background: var(--error-bg);
  color: var(--error);
}
.help-link {
  color: var(--muted);
  border-bottom-color: var(--muted);
  background: transparent;
  box-shadow: none;
}
.help-link:hover {
  color: var(--text);
  border-bottom-color: var(--text);
}
@media (max-width: 640px) {
  .help-link {
    background: var(--bg-input);
    border: 1px solid var(--border);
  }
}
.tooltip {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 0;
  color: var(--text-2);
}
.tooltip::after {
  border-top-color: var(--bg-hover);
}
.tooltip-link {
  color: var(--green);
}
a {
  color: var(--green);
}
"""

_STYLE_TAG = f"<style>{THEME_CSS}</style>".encode()


class ThemedAuthPagesMiddleware:
    """Append the pktx theme to HTML responses from FastMCP's OAuth pages."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in THEMED_PATHS:
            await self.app(scope, receive, send)
            return

        start: Message | None = None
        chunks: list[bytes] = []

        async def themed_send(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                if not headers.get(b"content-type", b"").startswith(b"text/html"):
                    await send(message)
                    return
                start = message
                return
            if start is None:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return
            body = b"".join(chunks)
            marker = body.rfind(b"</head>")
            if marker != -1:
                body = body[:marker] + _STYLE_TAG + body[marker:]
            headers = [
                (k, v) for k, v in start.get("headers", []) if k != b"content-length"
            ]
            headers.append((b"content-length", str(len(body)).encode()))
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, themed_send)
