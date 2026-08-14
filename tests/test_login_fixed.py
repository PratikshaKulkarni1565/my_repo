import os
import pytest
from playwright.sync_api import Page, expect

TEST_USERS = {
    "company1_admin": {
        "email": os.environ.get("C1_ADMIN_EMAIL", "admin@company1.com"),
        "password": os.environ.get("C1_ADMIN_PASSWORD", "password123"),
        "tenant": "company1",
        "has_2fa": False,
    },
    "company2_user": {
        "email": os.environ.get("C2_USER_EMAIL", "user@company2.com"),
        "password": os.environ.get("C2_USER_PASSWORD", "password123"),
        "tenant": "company2",
        "has_2fa": False,
    },
}

BASE_URL = os.environ.get("WFP_BASE_URL", "https://app.workflowpro.com")

DEFAULT_TIMEOUT_MS = 15_000


def login(page: Page, user: dict) -> None:
    """Shared login helper so every test performs auth identically."""
    page.goto(f"{BASE_URL}/login")

    email_input = page.locator("#email")
    expect(email_input).to_be_visible(timeout=DEFAULT_TIMEOUT_MS)

    email_input.fill(user["email"])
    page.locator("#password").fill(user["password"])

    with page.expect_navigation(wait_until="networkidle", timeout=DEFAULT_TIMEOUT_MS):
        page.locator("#login-btn").click()

    if user["has_2fa"] or page.locator("#otp-input").is_visible():
        otp = os.environ.get("TEST_OTP_CODE", "000000")  # test-env static/bypass code
        page.locator("#otp-input").fill(otp)
        with page.expect_navigation(wait_until="networkidle", timeout=DEFAULT_TIMEOUT_MS):
            page.locator("#otp-submit-btn").click()


def test_user_login(page: Page):
    login(page, TEST_USERS["company1_admin"])

    expect(page).to_have_url(f"{BASE_URL}/dashboard", timeout=DEFAULT_TIMEOUT_MS)

    welcome = page.locator(".welcome-message")
    expect(welcome).to_be_visible(timeout=DEFAULT_TIMEOUT_MS)


def test_multi_tenant_access(page: Page):
    user = TEST_USERS["company2_user"]
    login(page, user)

    expect(page).to_have_url(f"{BASE_URL}/dashboard", timeout=DEFAULT_TIMEOUT_MS)

    page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT_MS)
    cards = page.locator(".project-card")
    expect(cards.first).to_be_visible(timeout=DEFAULT_TIMEOUT_MS)

    count = cards.count()
    assert count > 0, "Expected at least one project card to load for company2"

    for i in range(count):
        text = cards.nth(i).text_content()
        assert "Company2" in text, f"Tenant leak detected in card: {text!r}"
