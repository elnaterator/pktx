"""FastMCP's OAuth pages can see the pktx server (name, icon, website)."""

import pytest

from pktx.oauth_theme import ICON_DATA_URI
from pktx.resume_service import ResumeService
from pktx.server import create_app


@pytest.fixture
def app(db_conn, monkeypatch):
    monkeypatch.setenv("PKTX_PUBLIC_URL", "https://pktx.example.com/")
    return create_app(service=ResumeService(db_conn), conn=db_conn)


def test_app_state_exposes_mcp_server_for_consent_page(app):
    # Consent/authorize handlers read request.app.state.fastmcp_server; without
    # it the consent screen says "FastMCP" and shows FastMCP's logo.
    server = app.state.fastmcp_server
    assert server.name == "pktx"
    assert server.icons[0].src == ICON_DATA_URI
    assert server.website_url == "https://pktx.example.com"
