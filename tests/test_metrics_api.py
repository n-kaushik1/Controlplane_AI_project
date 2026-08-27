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