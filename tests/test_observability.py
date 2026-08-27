from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_observability_dashboard():

    response = client.get(
        "/api/observability"
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(
        data,
        dict,
    )

    assert "system" in data
    assert "governance" in data
    assert "risk" in data
    assert "performance" in data
    assert "cost" in data
    assert "human_review" in data
    assert "decisions" in data


def test_observability_metrics():

    response = client.get(
        "/api/observability/metrics"
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(
        data,
        dict,
    )

    assert "total_requests" in data
    assert "decisions" in data


def test_observability_events():

    response = client.get(
        "/api/observability/events"
    )

    assert response.status_code == 200

    data = response.json()

    assert "events" in data

    assert isinstance(
        data["events"],
        list,
    )


def test_observability_events_limit():

    response = client.get(
        "/api/observability/events?limit=5"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(
        data["events"]
    ) <= 5


def test_observability_health():

    response = client.get(
        "/api/observability/health"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["observability"] == "enabled"