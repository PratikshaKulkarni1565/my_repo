import os
import pytest


# ============================================================
# PYTEST COMMAND-LINE OPTIONS
# ============================================================

def pytest_addoption(parser):
    parser.addoption(
        "--tenant",
        action="store",
        default="company1",
        help="Tenant used for the test run",
    )
    parser.addoption(
        "--env",
        action="store",
        default="staging",
        help="Environment to run against: staging | local",
    )


# ============================================================
# URLS
# ============================================================

@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("WFP_BASE_URL", "https://app.workflowpro.com")


@pytest.fixture(scope="session")
def api_base_url():
    return os.environ.get("WFP_API_BASE_URL", "https://api.workflowpro.com")


# ============================================================
# COMPANY 1
# ============================================================

@pytest.fixture(scope="session")
def tenant():
    return {
        "id": os.environ.get("C1_TENANT_ID", "company1"),
        "api_token": os.environ.get("C1_API_TOKEN", "test-token-company1"),
        "ui_email": os.environ.get("C1_ADMIN_EMAIL", "admin@company1.com"),
        "ui_password": os.environ.get("C1_ADMIN_PASSWORD", "password123"),
    }


# ============================================================
# COMPANY 2
# ============================================================

@pytest.fixture(scope="session")
def other_tenant():
    return {
        "id": os.environ.get("C2_TENANT_ID", "company2"),
        "api_token": os.environ.get("C2_API_TOKEN", "test-token-company2"),
        "ui_email": os.environ.get("C2_USER_EMAIL", "user@company2.com"),
        "ui_password": os.environ.get("C2_USER_PASSWORD", "password123"),
    }


# ============================================================
# PLAYWRIGHT BROWSER CONTEXT
# ============================================================

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        # Covers self-signed certs in staging/local environments.
        # Does NOT affect requests.post() — only Playwright browser.
        "ignore_https_errors": True,
    }
