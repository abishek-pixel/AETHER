"""
Live integration test — CORS preflight + login/register/auth
against the running backend at http://localhost:8000.

Run with:
    .venv\\Scripts\\pytest tests/test_login_live.py -v --tb=short -s
"""
import uuid
import httpx
import pytest

BASE    = "http://localhost:8000"
ORIGIN  = "http://localhost:8080"
TIMEOUT = 10  # seconds — every request uses this

# Unique per test-run so repeated runs don't clash on unique-email constraint
_RUN_ID       = uuid.uuid4().hex[:8]
TEST_EMAIL    = f"live_{_RUN_ID}@example.com"
TEST_PASSWORD = "TestPass123!"
TEST_NAME     = "Live Test User"

# Shared tokens populated by register/login tests
_tokens: dict = {}


def _get(path, **kwargs):
    return httpx.get(f"{BASE}{path}", timeout=TIMEOUT,
                     headers={"Origin": ORIGIN}, **kwargs)

def _post(path, **kwargs):
    return httpx.post(f"{BASE}{path}", timeout=TIMEOUT,
                      headers={"Origin": ORIGIN, "Content-Type": "application/json"},
                      **kwargs)

def _options(path):
    return httpx.options(
        f"{BASE}{path}", timeout=TIMEOUT,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )


# ===========================================================================
# 1. Backend health
# ===========================================================================

class TestBackendHealth:
    def test_health_endpoint_returns_200(self):
        r = _get("/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        data = r.json()
        assert data["status"] == "healthy"
        print(f"\n  ✅ Health OK — postgresql={data['postgresql']}")

    def test_root_endpoint(self):
        r = _get("/")
        assert r.status_code == 200
        assert "Aether" in r.json()["name"]
        print(f"\n  ✅ Root endpoint OK")


# ===========================================================================
# 2. CORS preflight — the bug that was causing 400
# ===========================================================================

class TestCORSPreflight:
    def test_login_options_not_400(self):
        r = _options("/api/v1/auth/login")
        assert r.status_code != 400, \
            f"OPTIONS /login returned 400 — CORS still broken! headers={dict(r.headers)}"
        assert r.status_code in (200, 204), \
            f"Expected 200/204 for OPTIONS preflight, got {r.status_code}"
        print(f"\n  ✅ OPTIONS /login → {r.status_code} (not 400)")

    def test_register_options_not_400(self):
        r = _options("/api/v1/auth/register")
        assert r.status_code not in (400, 405), \
            f"OPTIONS /register returned {r.status_code}"
        assert r.status_code in (200, 204)
        print(f"\n  ✅ OPTIONS /register → {r.status_code}")

    def test_cors_allow_origin_header_echoed(self):
        r = _options("/api/v1/auth/login")
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao in (ORIGIN, "*"), \
            f"Access-Control-Allow-Origin wrong: '{acao}'"
        print(f"\n  ✅ Access-Control-Allow-Origin: {acao}")

    def test_cors_allows_credentials(self):
        r = _options("/api/v1/auth/login")
        allow_creds = r.headers.get("access-control-allow-credentials", "")
        assert allow_creds.lower() == "true", \
            f"Expected 'true', got '{allow_creds}'"
        print(f"\n  ✅ Access-Control-Allow-Credentials: {allow_creds}")

    def test_cors_allows_authorization_header(self):
        r = _options("/api/v1/auth/login")
        allow_hdrs = r.headers.get("access-control-allow-headers", "").lower()
        assert "authorization" in allow_hdrs or allow_hdrs == "*", \
            f"Authorization not in allow-headers: '{allow_hdrs}'"
        print(f"\n  ✅ Access-Control-Allow-Headers includes authorization")

    def test_research_preflight(self):
        r = _options("/api/v1/research")
        assert r.status_code in (200, 204)
        print(f"\n  ✅ OPTIONS /research → {r.status_code}")


# ===========================================================================
# 3. Register
# ===========================================================================

class TestRegister:
    def test_register_new_user_returns_201_and_tokens(self):
        r = _post("/api/v1/auth/register",
                  json={"name": TEST_NAME, "email": TEST_EMAIL,
                        "password": TEST_PASSWORD})
        assert r.status_code == 201, \
            f"Register failed {r.status_code}: {r.text}"
        data = r.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        _tokens["access"]  = data["access_token"]
        _tokens["refresh"] = data["refresh_token"]
        print(f"\n  ✅ Register OK → 201, token: {data['access_token'][:20]}…")

    def test_register_duplicate_email_returns_409(self):
        r = _post("/api/v1/auth/register",
                  json={"name": TEST_NAME, "email": TEST_EMAIL,
                        "password": TEST_PASSWORD})
        assert r.status_code == 409, \
            f"Expected 409 for duplicate, got {r.status_code}: {r.text}"
        print(f"\n  ✅ Duplicate register → 409 Conflict")


# ===========================================================================
# 4. Login
# ===========================================================================

class TestLogin:
    def test_login_valid_credentials_returns_200(self):
        r = _post("/api/v1/auth/login",
                  json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code == 200, \
            f"Login failed {r.status_code}: {r.text}"
        data = r.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        _tokens["access"]  = data["access_token"]
        _tokens["refresh"] = data["refresh_token"]
        print(f"\n  ✅ Login OK → 200, no 400")

    def test_login_never_returns_400(self):
        """Core assertion — the CORS-related 400 must never appear on login."""
        r = _post("/api/v1/auth/login",
                  json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code != 400, \
            f"Login returned 400 Bad Request — CORS bug still present!\n{r.text}"
        print(f"\n  ✅ Login status={r.status_code}, confirmed NOT 400")

    def test_login_wrong_password_returns_401(self):
        r = _post("/api/v1/auth/login",
                  json={"email": TEST_EMAIL, "password": "WrongPass!!"})
        assert r.status_code == 401
        print(f"\n  ✅ Wrong password → 401")

    def test_login_unknown_email_returns_401(self):
        r = _post("/api/v1/auth/login",
                  json={"email": f"ghost_{_RUN_ID}@example.com",
                        "password": TEST_PASSWORD})
        assert r.status_code == 401
        print(f"\n  ✅ Unknown email → 401")


# ===========================================================================
# 5. Authenticated endpoints
# ===========================================================================

class TestAuthenticatedEndpoints:
    def _fresh_token(self) -> str:
        r = _post("/api/v1/auth/login",
                  json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code == 200, f"Login failed: {r.text}"
        return r.json()["access_token"]

    def test_me_returns_user_profile(self):
        token = self._fresh_token()
        r = _get("/api/v1/auth/me",
                 headers={"Authorization": f"Bearer {token}",
                          "Origin": ORIGIN})
        assert r.status_code == 200, f"/me failed: {r.text}"
        data = r.json()
        assert data["email"] == TEST_EMAIL
        assert data["name"]  == TEST_NAME
        print(f"\n  ✅ /me OK — email={data['email']}, plan={data['plan']}")

    def test_me_without_token_returns_401(self):
        r = _get("/api/v1/auth/me")
        assert r.status_code == 401
        print(f"\n  ✅ /me without token → 401")

    def test_rate_limit_endpoint_returns_correct_shape(self):
        token = self._fresh_token()
        r = _get("/api/v1/users/me/rate-limit",
                 headers={"Authorization": f"Bearer {token}",
                          "Origin": ORIGIN})
        assert r.status_code == 200, \
            f"/rate-limit failed {r.status_code}: {r.text}"
        data = r.json()
        for key in ("prompts_used", "prompts_allowed", "is_limited", "hours_remaining"):
            assert key in data, f"Missing key '{key}' in rate-limit response"
        print(f"\n  ✅ /rate-limit OK — "
              f"used={data['prompts_used']}/{data['prompts_allowed']}, "
              f"limited={data['is_limited']}")

    def test_rate_limit_without_token_returns_401(self):
        r = _get("/api/v1/users/me/rate-limit")
        assert r.status_code == 401
        print(f"\n  ✅ /rate-limit without token → 401")


# ===========================================================================
# 6. Token refresh
# ===========================================================================

class TestTokenRefresh:
    def test_valid_refresh_token_returns_new_tokens(self):
        # Register fresh user
        email = f"ref_{uuid.uuid4().hex[:6]}@example.com"
        reg = _post("/api/v1/auth/register",
                    json={"name": "Ref User", "email": email,
                          "password": TEST_PASSWORD})
        assert reg.status_code == 201, f"Register failed: {reg.text}"
        refresh_tok = reg.json()["refresh_token"]

        r = _post("/api/v1/auth/refresh",
                  json={"refresh_token": refresh_tok})
        assert r.status_code == 200, f"Refresh failed {r.status_code}: {r.text}"
        data = r.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        print(f"\n  ✅ Token refresh → 200, new token: {data['access_token'][:20]}…")

    def test_invalid_refresh_token_returns_401(self):
        r = _post("/api/v1/auth/refresh",
                  json={"refresh_token": "bad.token.value"})
        assert r.status_code == 401
        print(f"\n  ✅ Invalid refresh → 401")
