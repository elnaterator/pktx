"""Unit tests for pktx.config module."""

import logging

import pytest


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_default_log_level_is_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        from pktx.config import configure_logging

        logger = configure_logging()
        assert logger.level == logging.INFO

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        from pktx.config import configure_logging

        logger = configure_logging()
        assert logger.level == logging.DEBUG


class TestExtraClientRedirectUris:
    """PKTX_EXTRA_CLIENT_REDIRECT_URIS: opt-in allowlist for hosted MCP clients."""

    def test_unset_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PKTX_EXTRA_CLIENT_REDIRECT_URIS", raising=False)
        from pktx.config import resolve_extra_client_redirect_uris

        assert resolve_extra_client_redirect_uris() == []

    def test_blank_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PKTX_EXTRA_CLIENT_REDIRECT_URIS", "   ")
        from pktx.config import resolve_extra_client_redirect_uris

        assert resolve_extra_client_redirect_uris() == []

    def test_comma_separated_patterns_are_split_and_stripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "PKTX_EXTRA_CLIENT_REDIRECT_URIS",
            "https://client.example.com/callback, https://*.other.example/cb ,",
        )
        from pktx.config import resolve_extra_client_redirect_uris

        assert resolve_extra_client_redirect_uris() == [
            "https://client.example.com/callback",
            "https://*.other.example/cb",
        ]


class TestAuthorizedParties:
    """CLERK_AUTHORIZED_PARTIES: allowed azp values for REST JWTs (027 / M12)."""

    def test_explicit_list_trimmed_and_slash_stripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "CLERK_AUTHORIZED_PARTIES", " https://a.example/ ,http://localhost:5173,"
        )
        from pktx.config import resolve_authorized_parties

        assert resolve_authorized_parties() == [
            "https://a.example",
            "http://localhost:5173",
        ]

    def test_defaults_to_public_url_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
        monkeypatch.setenv("PKTX_PUBLIC_URL", "https://pktx.example:8443/some/path/")
        from pktx.config import resolve_authorized_parties

        assert resolve_authorized_parties() == ["https://pktx.example:8443"]

    def test_neither_set_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
        monkeypatch.delenv("PKTX_PUBLIC_URL", raising=False)
        from pktx.config import resolve_authorized_parties

        with pytest.raises(ValueError):
            resolve_authorized_parties()
