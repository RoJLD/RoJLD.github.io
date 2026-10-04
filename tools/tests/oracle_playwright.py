"""Porte Playwright : skip honnête si absent, échec si ELYSIUM_REQUIRE_PLAYWRIGHT=1."""
import os
import pytest


def porte():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        if os.environ.get("ELYSIUM_REQUIRE_PLAYWRIGHT") == "1":
            pytest.fail("playwright exigé (ELYSIUM_REQUIRE_PLAYWRIGHT=1) et absent")
        pytest.skip("playwright absent — smoke navigateur ignoré")
