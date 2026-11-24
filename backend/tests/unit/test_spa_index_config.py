"""index.html gets runtime config (Clerk key, version, git sha) at serve time."""

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from pktx.server import (
    CLERK_KEY_PLACEHOLDER,
    GIT_SHA_PLACEHOLDER,
    VERSION_PLACEHOLDER,
    SPAStaticFiles,
)

INDEX = (
    "<!doctype html><html><head>"
    f'<meta name="pktx-clerk-publishable-key" content="{CLERK_KEY_PLACEHOLDER}" />'
    f'<meta name="pktx-version" content="{VERSION_PLACEHOLDER}" />'
    f'<meta name="pktx-git-sha" content="{GIT_SHA_PLACEHOLDER}" />'
    "</head><body>spa</body></html>"
)


def _client(
    tmp_path: Path, key: str, version: str = "", git_sha: str = ""
) -> TestClient:
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "app.js").write_text("console.log(1)")
    app = Starlette()
    app.mount(
        "/",
        SPAStaticFiles(
            directory=str(tmp_path),
            publishable_key=key,
            version=version,
            git_sha=git_sha,
        ),
    )
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/index.html", "/resumes/3", "/a/b/"])
def test_index_paths_carry_key_and_no_cache(tmp_path: Path, path: str) -> None:
    response = _client(tmp_path, "pk_test_abc").get(path)
    assert response.status_code == 200
    assert 'content="pk_test_abc"' in response.text
    assert CLERK_KEY_PLACEHOLDER not in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_key_is_html_escaped(tmp_path: Path) -> None:
    response = _client(tmp_path, '"><script>x</script>').get("/")
    assert "<script>x" not in response.text
    assert "&quot;&gt;&lt;script&gt;" in response.text


def test_unset_key_renders_empty(tmp_path: Path) -> None:
    response = _client(tmp_path, "").get("/")
    assert 'content=""' in response.text


def test_assets_untouched(tmp_path: Path) -> None:
    response = _client(tmp_path, "pk_test_abc").get("/app.js")
    assert response.text == "console.log(1)"
    assert response.headers.get("cache-control") != "no-cache"


def test_version_and_sha_filled(tmp_path: Path) -> None:
    text = (
        _client(tmp_path, "pk", version="v2026.11.24", git_sha="b" * 40).get("/").text
    )
    assert '<meta name="pktx-version" content="v2026.11.24" />' in text
    assert f'<meta name="pktx-git-sha" content="{"b" * 40}" />' in text
    assert VERSION_PLACEHOLDER not in text
    assert GIT_SHA_PLACEHOLDER not in text


def test_version_is_html_escaped(tmp_path: Path) -> None:
    text = _client(tmp_path, "pk", version='"><b>').get("/").text
    assert "<b>" not in text
    assert "&quot;&gt;&lt;b&gt;" in text
