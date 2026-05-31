from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = APP_ROOT / "frontend"


def _read_frontend(path: str) -> str:
    return (FRONTEND_ROOT / path).read_text(encoding="utf-8")


def test_auth_session_records_absolute_expiry_and_idle_activity_metadata():
    client = _read_frontend("src/api/client.ts")

    assert "AUTH_EXPIRES_AT_KEY = 'claimguard.auth.expires_at'" in client
    assert "AUTH_LAST_ACTIVITY_AT_KEY = 'claimguard.auth.last_activity_at'" in client
    assert "AUTH_IDLE_TIMEOUT_SECONDS_KEY = 'claimguard.auth.idle_timeout_seconds'" in client
    assert "DEFAULT_SESSION_TIMEOUT_SECONDS = 30 * 60" in client
    assert "Math.min(safeExpiresInSeconds, DEFAULT_SESSION_TIMEOUT_SECONDS)" in client
    assert "storage.setItem(AUTH_EXPIRES_AT_KEY, String(now + safeExpiresInSeconds * 1000))" in client
    assert "storage.setItem(AUTH_LAST_ACTIVITY_AT_KEY, String(now))" in client
    assert "storage.setItem(AUTH_IDLE_TIMEOUT_SECONDS_KEY, String(idleTimeoutSeconds))" in client


def test_auth_session_enforces_idle_timeout_without_extending_token_expiry():
    client = _read_frontend("src/api/client.ts")

    assert "return now >= timing.expiresAt || now - timing.lastActivityAt >= idleTimeoutMs" in client
    assert "storage.setItem(AUTH_LAST_ACTIVITY_AT_KEY, String(now));" in client
    assert "markAuthActivity" in client
    mark_activity_block = client.split("export const markAuthActivity", 1)[1].split(
        "export const enforceAuthSessionTimeout",
        1,
    )[0]
    assert "AUTH_EXPIRES_AT_KEY" not in mark_activity_block


def test_request_interceptor_blocks_expired_sessions_before_bearer_header():
    client = _read_frontend("src/api/client.ts")

    timeout_check_index = client.index("if (enforceAuthSessionTimeout())")
    bearer_header_index = client.index("config.headers.Authorization")

    assert timeout_check_index < bearer_header_index
    assert "return Promise.reject(new Error('auth_session_expired'))" in client


def test_login_uses_backend_expiry_seconds_for_session_timing():
    login_page = _read_frontend("src/pages/Login.tsx")

    assert "setAuthSession(response.data.access_token, response.data.user, response.data.expires_in)" in login_page


def test_app_registers_activity_and_interval_timeout_checks():
    app = _read_frontend("src/App.tsx")

    assert "SESSION_TIMEOUT_CHECK_INTERVAL_MS" in app
    assert "enforceAuthSessionTimeout" in app
    assert "markAuthActivity" in app
    assert "const activityEvents = ['click', 'keydown', 'mousedown', 'mousemove', 'scroll', 'touchstart'];" in app
    assert "window.addEventListener(eventName, handleActivity, activityOptions)" in app
    assert "document.addEventListener('visibilitychange', handleVisibilityChange)" in app
    assert "window.setInterval(handleTimeoutCheck, SESSION_TIMEOUT_CHECK_INTERVAL_MS)" in app
    assert "setUser(null)" in app
