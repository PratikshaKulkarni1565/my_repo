import os
import uuid

import pytest
import requests
from playwright.sync_api import expect


# ============================================================
# CONFIGURATION
# ============================================================

API_BASE_URL = os.environ.get("WFP_API_BASE_URL", "https://api.workflowpro.com")
BASE_URL = os.environ.get("WFP_BASE_URL", "https://app.workflowpro.com")
DEFAULT_TIMEOUT_MS = 15_000

BROWSERSTACK_USERNAME = os.environ.get("BROWSERSTACK_USERNAME", "your_bs_username")
BROWSERSTACK_ACCESS_KEY = os.environ.get("BROWSERSTACK_ACCESS_KEY", "your_bs_access_key")
BROWSERSTACK_URL = (
    f"https://{BROWSERSTACK_USERNAME}:{BROWSERSTACK_ACCESS_KEY}"
    "@hub.browserstack.com/wd/hub"
)


# ============================================================
# LOGIN HELPER
# ============================================================

def _login(page, base_url: str, email: str, password: str) -> None:
    """
    Navigates to login, fills credentials, clicks login button,
    and waits for redirect to /projects.

    Uses expect(page).to_have_url() instead of expect_navigation()
    to avoid race conditions on SPAs where the navigation event
    fires before React finishes rendering.
    """
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    expect(page.locator("#email")).to_be_visible(timeout=DEFAULT_TIMEOUT_MS)
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    page.locator("#login-btn").click()
    expect(page).to_have_url(f"{base_url}/projects", timeout=DEFAULT_TIMEOUT_MS)


# ============================================================
# MOBILE HELPER (BROWSERSTACK)
# ============================================================

def _verify_project_on_mobile(project_name: str, email: str, password: str) -> None:
    """
    Launches a real iOS device on BrowserStack via Appium,
    logs in, and verifies the project card is visible on mobile.

    Skipped gracefully when BrowserStack credentials are absent
    or appium-python-client is not installed.
    """
    try:
        from appium import webdriver as appium_webdriver
        from appium.webdriver.common.appiumby import AppiumBy
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        pytest.skip(
            "appium-python-client not installed. "
            "Run: pip install appium-python-client"
        )

    capabilities = {
        "bstack:options": {
            "userName": BROWSERSTACK_USERNAME,
            "accessKey": BROWSERSTACK_ACCESS_KEY,
            "deviceName": "iPhone 14",
            "osVersion": "16",
            "browserName": "Safari",
            "projectName": "WorkFlow Pro",
            "buildName": "integration-test",
            "sessionName": "mobile-project-visibility",
            "realMobile": "true",
        }
    }

    driver = appium_webdriver.Remote(BROWSERSTACK_URL, capabilities)

    try:
        wait = WebDriverWait(driver, DEFAULT_TIMEOUT_MS / 1000)
        driver.get(f"{BASE_URL}/login")
        wait.until(EC.presence_of_element_located(("id", "email"))).send_keys(email)
        driver.find_element("id", "password").send_keys(password)
        driver.find_element("id", "login-btn").click()
        wait.until(EC.url_contains("/projects"))

        card = wait.until(
            EC.visibility_of_element_located((
                AppiumBy.XPATH,
                f"//*[contains(@class,'project-card')"
                f" and contains(text(),'{project_name}')]",
            ))
        )
        assert card.is_displayed(), (
            f"Project '{project_name}' not visible on mobile"
        )
    finally:
        driver.quit()


# ============================================================
# FIXTURE — CREATE PROJECT VIA API
# ============================================================

@pytest.fixture
def created_project(tenant):
    """
    Creates a project via API before the test and deletes it after,
    regardless of test outcome.

    Fixture-based teardown guarantees cleanup even when the test
    body raises — unlike a try/finally block in the test itself.
    """
    project_name = f"QA Automation Test {uuid.uuid4().hex[:8]}"

    headers = {
        "Authorization": f"Bearer {tenant['api_token']}",
        "X-Tenant-ID": tenant["id"],
    }

    # -- CREATE --
    response = requests.post(
        f"{API_BASE_URL}/api/v1/projects",
        headers=headers,
        json={
            "name": project_name,
            "description": "Created by automated integration test",
            "team_members": [],
        },
        timeout=10,
    )

    assert response.status_code == 201, (
        f"Project creation failed: {response.status_code} - {response.text}"
    )

    body = response.json()

    assert body["name"] == project_name
    assert body["status"] == "active"
    assert "id" in body

    yield body

    # -- CLEANUP --
    delete_response = requests.delete(
        f"{API_BASE_URL}/api/v1/projects/{body['id']}",
        headers=headers,
        timeout=10,
    )
    assert delete_response.status_code in (200, 204), (
        f"Project cleanup failed: "
        f"{delete_response.status_code} - {delete_response.text}"
    )


# ============================================================
# INTEGRATION TEST — PROJECT CREATION FLOW  (Part 3)
# ============================================================

@pytest.mark.integration
def test_project_creation_flow(page, tenant, other_tenant, created_project):
    """
    End-to-end integration test covering all 4 steps from Part 3:

      1. API    — project created and response validated (fixture)
      2. Web UI — Company 1 sees the project in the browser
      3. Mobile — project visible on real iOS device via BrowserStack
      4. Security — Company 2 cannot see or access the project

    Assumptions:
    - App redirects to /projects after successful login.
    - Project cards use CSS class .project-card.
    - BrowserStack credentials set via env vars for Step 3.
    - Tenant isolation enforced at both UI and API layers.
    """

    project_name = created_project["name"]

    # --------------------------------------------------------
    # STEP 1 — API
    # Project already created and validated inside the fixture.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # STEP 2 — WEB UI: COMPANY 1 SEES THE PROJECT
    # --------------------------------------------------------
    # expect().to_be_visible() with explicit timeout handles
    # dynamic/lazy-loaded dashboards reliably, unlike a bare
    # .is_visible() which returns immediately without retrying.

    _login(page, BASE_URL, tenant["ui_email"], tenant["ui_password"])

    page.goto(f"{BASE_URL}/projects", wait_until="domcontentloaded")

    expect(
        page.locator(".project-card", has_text=project_name)
    ).to_be_visible(timeout=DEFAULT_TIMEOUT_MS)

    # --------------------------------------------------------
    # STEP 3 — MOBILE: REAL iOS DEVICE VIA BROWSERSTACK
    # --------------------------------------------------------
    # Skipped automatically when BS credentials are not set,
    # so local dev runs are not blocked.

    if (
        BROWSERSTACK_USERNAME != "your_bs_username"
        and BROWSERSTACK_ACCESS_KEY != "your_bs_access_key"
    ):
        _verify_project_on_mobile(
            project_name,
            tenant["ui_email"],
            tenant["ui_password"],
        )
    else:
        pytest.skip(
            "BrowserStack credentials not configured — "
            "skipping mobile verification. "
            "Set BROWSERSTACK_USERNAME and BROWSERSTACK_ACCESS_KEY to enable."
        )

    # --------------------------------------------------------
    # STEP 4 — SECURITY: COMPANY 2 CANNOT SEE THE PROJECT
    # --------------------------------------------------------

    # 4a. UI isolation —
    # to_have_count(0) catches hidden elements that
    # not to_be_visible() would miss (data-leak scenario).
    _login(page, BASE_URL, other_tenant["ui_email"], other_tenant["ui_password"])

    page.goto(f"{BASE_URL}/projects", wait_until="domcontentloaded")

    expect(
        page.locator(".project-card", has_text=project_name)
    ).to_have_count(0, timeout=DEFAULT_TIMEOUT_MS)

    # 4b. API isolation —
    # 404 preferred over 403 — avoids leaking resource existence
    # to unauthorised tenants.
    resp = requests.get(
        f"{API_BASE_URL}/api/v1/projects/{created_project['id']}",
        headers={
            "Authorization": f"Bearer {other_tenant['api_token']}",
            "X-Tenant-ID": other_tenant["id"],
        },
        timeout=10,
    )

    assert resp.status_code in (403, 404), (
        f"Tenant isolation breach: "
        f"Company 2 received status {resp.status_code}"
    )
