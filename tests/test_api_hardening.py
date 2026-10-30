import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    SlidingWindowRateLimiter,
    rate_limiter,
    sanitize_request_id,
)
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_security_state(monkeypatch):

    monkeypatch.setattr(settings, "API_KEY", None)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 0)

    rate_limiter.reset()

    yield

    rate_limiter.reset()


GENERATE = "/api/generate"


# ---------------------------------------------------------
# API key authentication
# ---------------------------------------------------------

def test_generate_open_when_no_api_key_configured():

    response = client.post(GENERATE, json={"prompt": "Hello"})

    assert response.status_code == 200


def test_generate_rejects_missing_api_key(monkeypatch):

    monkeypatch.setattr(settings, "API_KEY", "s3cret")

    response = client.post(GENERATE, json={"prompt": "Hello"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"


def test_generate_rejects_wrong_api_key(monkeypatch):

    monkeypatch.setattr(settings, "API_KEY", "s3cret")

    response = client.post(
        GENERATE,
        json={"prompt": "Hello"},
        headers={"X-API-Key": "nope"},
    )

    assert response.status_code == 401


def test_generate_accepts_valid_api_key(monkeypatch):

    monkeypatch.setattr(settings, "API_KEY", "s3cret")

    response = client.post(
        GENERATE,
        json={"prompt": "Hello"},
        headers={"X-API-Key": "s3cret"},
    )

    assert response.status_code == 200


def test_resolve_review_requires_api_key(monkeypatch):

    monkeypatch.setattr(settings, "API_KEY", "s3cret")

    response = client.post(
        "/api/reviews/does-not-exist/resolve",
        json={"final_decision": "ALLOW", "reviewer": "qa"},
    )

    assert response.status_code == 401


def test_read_endpoints_stay_public_with_api_key(monkeypatch):

    monkeypatch.setattr(settings, "API_KEY", "s3cret")

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/metrics").status_code == 200


def test_health_reports_hardening_state(monkeypatch):

    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 5)

    data = client.get("/api/health").json()

    assert data["auth_required"] is True
    assert data["rate_limit_per_minute"] == 5
    assert "s3cret" not in str(data)


# ---------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------

def test_rate_limit_returns_429_with_retry_after(monkeypatch):

    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)

    body = {"prompt": "Hello"}

    assert client.post(GENERATE, json=body).status_code == 200
    assert client.post(GENERATE, json=body).status_code == 200

    limited = client.post(GENERATE, json=body)

    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


def test_limiter_window_slides():

    limiter = SlidingWindowRateLimiter()

    assert limiter.check("a", 2, now=0.0) is None
    assert limiter.check("a", 2, now=1.0) is None
    assert limiter.check("a", 2, now=2.0) is not None

    # A different client is unaffected.
    assert limiter.check("b", 2, now=2.0) is None

    # After the window passes, the first client may retry.
    assert limiter.check("a", 2, now=61.5) is None


# ---------------------------------------------------------
# Input validation
# ---------------------------------------------------------

def test_oversized_prompt_is_rejected():

    response = client.post(
        GENERATE,
        json={"prompt": "x" * (settings.MAX_PROMPT_CHARS + 1)},
    )

    assert response.status_code == 422


def test_unknown_risk_profile_is_400():

    response = client.post(
        GENERATE,
        json={"prompt": "Hello", "use_case": "does_not_exist"},
    )

    assert response.status_code == 400


# ---------------------------------------------------------
# Request ID propagation + headers
# ---------------------------------------------------------

def test_caller_request_id_is_propagated():

    response = client.post(
        GENERATE,
        json={"prompt": "Hello"},
        headers={"X-Request-ID": "trace-abc-123"},
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["request_id"] == "trace-abc-123"
    assert response.headers["x-request-id"] == "trace-abc-123"


def test_unsafe_request_id_is_discarded():

    response = client.post(
        GENERATE,
        json={"prompt": "Hello"},
        headers={"X-Request-ID": "bad id\twith spaces"},
    )

    assert response.status_code == 200
    request_id = response.json()["metadata"]["request_id"]

    assert request_id != "bad id\twith spaces"
    assert request_id.startswith("req-")
    assert response.headers["x-request-id"] == request_id


@pytest.mark.parametrize(
    "value, expected",
    [
        ("ok-123_A.b", "ok-123_A.b"),
        ("", None),
        (None, None),
        ("x" * 65, None),
        ("a b", None),
        ("a\nb", None),
    ],
)
def test_sanitize_request_id(value, expected):

    assert sanitize_request_id(value) == expected


def test_security_headers_present():

    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "x-process-time-ms" in response.headers


def test_dashboard_is_served():

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
