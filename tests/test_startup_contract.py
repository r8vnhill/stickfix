"""Characterization tests for Stickfix's polling-only startup contract.

These tests pin down a security-relevant runtime invariant: Stickfix starts
through Telegram long polling and never starts PTB's Tornado-based webhook
server. Because no HTTP listening port is bound, the vulnerable Tornado
``multipart/form-data`` parser (CVE-2026-31958) is unreachable through the bot.

The tests exercise the ``start_polling_service`` seam and the public ``run``
entry point with a substituted ``Updater`` so no real Telegram connection or
network listener is created.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.stickfix import Stickfix, start_polling_service


def test_start_polling_service_starts_polling_and_never_webhook() -> None:
    """The startup seam starts polling exactly once and never a webhook server."""
    # Given a configured updater and logger,
    updater = MagicMock(name="Updater")
    logger = MagicMock(name="StickfixLogger")

    # when the startup seam runs,
    start_polling_service(updater, logger)

    # then polling is started exactly once and webhook startup is never requested.
    updater.start_polling.assert_called_once_with()
    updater.start_webhook.assert_not_called()


def test_run_delegates_to_polling_only_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Stickfix.run`` delegates to polling-only startup and binds no listener."""
    # Given a Stickfix whose heavy collaborators are substituted so construction
    # touches neither Telegram nor the filesystem,
    updater = MagicMock(name="Updater")
    monkeypatch.setattr("bot.stickfix.Updater", MagicMock(return_value=updater))
    monkeypatch.setattr("bot.stickfix.StickfixDB", MagicMock(name="StickfixDB"))
    for handler in ("HelperHandler", "UserHandler", "StickerHandler", "InlineHandler"):
        monkeypatch.setattr(f"bot.stickfix.{handler}", MagicMock(name=handler))

    bot = Stickfix("dummy-token")

    # when the public entry point runs,
    bot.run()

    # then it starts polling and would fail if it ever started a webhook server
    # or bound an HTTP listening port.
    updater.start_polling.assert_called_once_with()
    updater.start_webhook.assert_not_called()
    updater.listen.assert_not_called()
