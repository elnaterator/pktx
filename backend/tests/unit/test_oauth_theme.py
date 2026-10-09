"""ThemedAuthPagesMiddleware: pktx styling on FastMCP's OAuth HTML pages only."""

import base64

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from pktx.oauth_theme import ICON_DATA_URI, THEME_CSS, ThemedAuthPagesMiddleware

PAGE = "<!DOCTYPE html><html><head><style>body{}</style></head><body>hi</body></html>"


def _client() -> TestClient:
    async def html_page(request):
        return HTMLResponse(PAGE)

    async def streamed_page(request):
        async def chunks():
            yield PAGE[:30].encode()
            yield PAGE[30:].encode()

        return StreamingResponse(chunks(), media_type="text/html")

    async def json_page(request):
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    app = Starlette(
        routes=[
            Route("/consent", html_page),
            Route("/auth/callback", streamed_page),
            Route("/authorize", json_page),
            Route("/other", html_page),
        ]
    )
    app.add_middleware(ThemedAuthPagesMiddleware)
    return TestClient(app)


def test_injects_theme_before_head_close_on_consent():
    resp = _client().get("/consent")
    assert resp.status_code == 200
    assert THEME_CSS in resp.text
    assert resp.text.index(THEME_CSS) < resp.text.index("</head>")
    # Appended after FastMCP's own <style>, so it wins at equal specificity.
    assert resp.text.index("body{}") < resp.text.index(THEME_CSS)
    assert int(resp.headers["content-length"]) == len(resp.content)


def test_handles_streamed_html():
    resp = _client().get("/auth/callback")
    assert THEME_CSS in resp.text
    assert resp.text.endswith("</html>")
    assert int(resp.headers["content-length"]) == len(resp.content)


def test_leaves_non_html_responses_alone():
    resp = _client().get("/authorize")
    assert resp.status_code == 400
    assert resp.json() == {"error": "invalid_request"}


def test_leaves_other_paths_alone():
    assert _client().get("/other").text == PAGE


def test_icon_is_svg_data_uri():
    prefix = "data:image/svg+xml;base64,"
    assert ICON_DATA_URI.startswith(prefix)
    assert base64.b64decode(ICON_DATA_URI[len(prefix) :]).startswith(b"<svg")
