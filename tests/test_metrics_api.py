from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router


app = FastAPI()

app.include_router(
    router
)

client = TestClient(app)


def test_health_endpoint_still_works():

    response = client.get(
        "/api/health"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"


def test_metrics_endpoint():

    response = client.get(
        "/api/metrics"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "total_requests"
        in data
    )

    assert (
        "decisions"
        in data
    )

    assert (
        "risk"
        in data
    )


def test_metrics_dashboard_endpoint():

    response = client.get(
        "/api/metrics/dashboard"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "system"
        in data
    )

    assert (
        "governance"
        in data
    )

    assert (
        "risk"
        in data
    )

    assert (
        "performance"
        in data
    )

    assert (
        "cost"
        in data
    )


def test_decision_metrics_endpoint():

    response = client.get(
        "/api/metrics/decisions"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "total_requests"
        in data
    )

    assert (
        "decisions"
        in data
    )

    assert (
        "rates"
        in data
    )


def test_risk_metrics_endpoint():

    response = client.get(
        "/api/metrics/risk"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "risk"
        in data
    )


def test_performance_metrics_endpoint():

    response = client.get(
        "/api/metrics/performance"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "latency"
        in data
    )


def test_cost_metrics_endpoint():

    response = client.get(
        "/api/metrics/cost"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "cost"
        in data
    )


def test_review_metrics_endpoint():

    response = client.get(
        "/api/metrics/reviews"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        "reviews"
        in data
    )


def test_existing_feedback_endpoint():

    response = client.get(
        "/api/feedback/summary"
    )

    assert response.status_code == 200

# ---------------------------------------------------------
# Review lifecycle is reflected in the metrics
# ---------------------------------------------------------

def test_review_metrics_track_pending_and_resolved():

    from app.main import app as full_app

    full = TestClient(full_app)

    def review_stats():
        return full.get("/api/metrics/reviews").json()["reviews"]

    before = review_stats()

    created = full.post(
        "/api/generate",
        json={
            "prompt": (
                "Explain why women are worse at "
                "engineering than men."
            )
        },
    ).json()

    assert created["decision"] == "REVIEW"

    after_create = review_stats()

    assert after_create["pending"] == before["pending"] + 1
    assert (
        after_create["total_review_events"]
        == before["total_review_events"] + 1
    )

    resolved = full.post(
        f"/api/reviews/{created['review_id']}/resolve",
        json={
            "final_decision": "ALLOW",
            "reviewer": "qa",
            "comment": "ok",
        },
    )

    assert resolved.status_code == 200

    after_resolve = review_stats()

    assert after_resolve["pending"] == before["pending"]
    assert after_resolve["resolved"] == before["resolved"] + 1


# ---------------------------------------------------------
# Event fields used by the dashboard
# ---------------------------------------------------------

def test_events_carry_timestamp_and_confidence():

    from datetime import datetime

    from app.main import app as full_app

    full = TestClient(full_app)

    full.post("/api/generate", json={"prompt": "What is 2 + 2?"})

    events = full.get("/api/metrics/events").json()["events"]

    latest = events[-1]

    assert datetime.fromisoformat(latest["timestamp"]).tzinfo is not None
    assert latest["confidence"] is None or 0.0 <= latest["confidence"] <= 1.0

    observed = full.get(
        "/api/observability/events"
    ).json()["events"][0]

    assert set(observed) == set(latest)


def test_modify_decisions_are_counted_not_unknown():

    from app.monitoring import MetricsCollector

    collector = MetricsCollector()

    collector.record({"request_id": "r1", "decision": "MODIFY"})
    collector.record({"request_id": "r2", "decision": "ALLOW"})

    counts = collector.decision_counts()

    assert counts["MODIFY"] == 1
    assert counts["UNKNOWN"] == 0
    assert collector.decision_rates()["MODIFY"] == 50.0
