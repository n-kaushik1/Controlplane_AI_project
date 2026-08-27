from app.monitoring import (
    MetricEvent,
    MetricsCollector,
    MetricsAggregator,
)


def test_metric_event_from_result():

    result = {
        "request_id": "req-1",
        "prompt": "Hello",
        "decision": "ALLOW",
        "risk_score": 0.25,
        "latency_ms": 42.5,
        "token_count": 10,
        "estimated_cost": 0.002,
    }

    event = MetricEvent.from_result(
        result
    )

    assert event.request_id == (
        "req-1"
    )

    assert event.decision == (
        "ALLOW"
    )

    assert event.risk_score == 0.25

    assert event.latency_ms == 42.5

    assert event.token_count == 10

    assert event.estimated_cost == 0.002

    assert event.prompt_chars == 5


def test_metric_event_supports_existing_fields():

    result = {
        "prompt": "Test",
        "action": "BLOCK",
        "responsibility": 0.91,
        "latency": 15,
        "tokens": 20,
        "cost": 0.01,
    }

    event = MetricEvent.from_result(
        result
    )

    assert event.decision == (
        "BLOCK"
    )

    assert event.risk_score == 0.91

    assert event.latency_ms == 15

    assert event.token_count == 20

    assert event.estimated_cost == 0.01


def test_empty_collector():

    collector = MetricsCollector()

    snapshot = collector.snapshot()

    assert snapshot[
        "total_requests"
    ] == 0

    assert snapshot[
        "decisions"
    ]["ALLOW"] == 0

    assert snapshot[
        "risk"
    ]["average"] == 0.0


def test_decision_counts():

    collector = MetricsCollector()

    collector.record({
        "decision": "ALLOW",
    })

    collector.record({
        "decision": "ALLOW",
    })

    collector.record({
        "decision": "REVIEW",
    })

    collector.record({
        "decision": "BLOCK",
    })

    collector.record({
        "decision": "EDIT",
    })

    counts = (
        collector
        .decision_counts()
    )

    assert counts["ALLOW"] == 2

    assert counts["REVIEW"] == 1

    assert counts["BLOCK"] == 1

    assert counts["EDIT"] == 1


def test_decision_rates():

    collector = MetricsCollector()

    collector.record({
        "decision": "ALLOW",
    })

    collector.record({
        "decision": "BLOCK",
    })

    rates = (
        collector
        .decision_rates()
    )

    assert rates["ALLOW"] == 50.0

    assert rates["BLOCK"] == 50.0

    assert rates["REVIEW"] == 0.0


def test_risk_statistics():

    collector = MetricsCollector()

    collector.record({
        "decision": "ALLOW",
        "risk_score": 0.2,
    })

    collector.record({
        "decision": "REVIEW",
        "risk_score": 0.8,
    })

    collector.record({
        "decision": "BLOCK",
        "risk_score": 0.9,
    })

    stats = (
        collector
        .risk_statistics()
    )

    assert stats["average"] == 0.6333

    assert stats["minimum"] == 0.2

    assert stats["maximum"] == 0.9

    assert stats[
        "high_risk_rate"
    ] == 66.67


def test_latency_statistics():

    collector = MetricsCollector()

    collector.record({
        "latency_ms": 10,
    })

    collector.record({
        "latency_ms": 30,
    })

    stats = (
        collector
        .latency_statistics()
    )

    assert stats["average_ms"] == 20.0

    assert stats["minimum_ms"] == 10.0

    assert stats["maximum_ms"] == 30.0


def test_cost_statistics():

    collector = MetricsCollector()

    collector.record({
        "cost": 0.01,
    })

    collector.record({
        "cost": 0.03,
    })

    stats = (
        collector
        .cost_statistics()
    )

    assert stats["total"] == 0.04

    assert stats["average"] == 0.02

    assert stats["maximum"] == 0.03


def test_review_statistics():

    collector = MetricsCollector()

    collector.record({
        "decision": "ALLOW",
    })

    collector.record({
        "decision": "REVIEW",
        "review_id": "review-1",
        "review_status": "PENDING",
    })

    collector.record({
        "decision": "REVIEW",
        "review_id": "review-2",
        "review_status": "RESOLVED",
    })

    stats = (
        collector
        .review_statistics()
    )

    assert stats[
        "total_review_events"
    ] == 2

    assert stats["pending"] == 1

    assert stats["resolved"] == 1

    assert stats["review_rate"] == 66.67


def test_snapshot_contains_all_sections():

    collector = MetricsCollector()

    collector.record({
        "decision": "ALLOW",
    })

    snapshot = (
        collector.snapshot()
    )

    assert "total_requests" in snapshot

    assert "decisions" in snapshot

    assert "decision_rates" in snapshot

    assert "risk" in snapshot

    assert "latency" in snapshot

    assert "cost" in snapshot

    assert "reviews" in snapshot


def test_aggregator_ingest():

    aggregator = MetricsAggregator()

    count = aggregator.ingest_many([
        {
            "decision": "ALLOW",
        },
        {
            "decision": "BLOCK",
        },
        {
            "decision": "REVIEW",
        },
    ])

    assert count == 3

    snapshot = (
        aggregator.snapshot()
    )

    assert snapshot[
        "total_requests"
    ] == 3

    assert snapshot[
        "decisions"
    ]["ALLOW"] == 1

    assert snapshot[
        "decisions"
    ]["BLOCK"] == 1

    assert snapshot[
        "decisions"
    ]["REVIEW"] == 1


def test_aggregator_load_jsonl(
    tmp_path,
):

    audit_file = (
        tmp_path / "audit.jsonl"
    )

    audit_file.write_text(
        (
            '{"decision": "ALLOW", '
            '"risk_score": 0.1}\n'
            '{"decision": "BLOCK", '
            '"risk_score": 0.9}\n'
            'invalid-json\n'
        ),
        encoding="utf-8",
    )

    aggregator = (
        MetricsAggregator()
    )

    count = (
        aggregator
        .load_jsonl(
            str(audit_file)
        )
    )

    assert count == 2

    assert (
        aggregator.collector
        .total_requests
        == 2
    )


def test_aggregator_missing_jsonl():

    aggregator = MetricsAggregator()

    count = (
        aggregator
        .load_jsonl(
            "does-not-exist.jsonl"
        )
    )

    assert count == 0


def test_dashboard():

    aggregator = MetricsAggregator()

    aggregator.ingest({
        "decision": "ALLOW",
        "risk_score": 0.2,
        "latency_ms": 20,
        "cost": 0.01,
    })

    aggregator.ingest({
        "decision": "BLOCK",
        "risk_score": 0.9,
        "latency_ms": 40,
        "cost": 0.02,
    })

    dashboard = (
        aggregator.dashboard()
    )

    assert (
        dashboard["system"]["requests"]
        == 2
    )

    assert (
        dashboard["system"]["status"]
        == "ACTIVE"
    )

    assert (
        dashboard[
            "governance"
        ]["allow_rate"]
        == 50.0
    )

    assert (
        dashboard[
            "governance"
        ]["block_rate"]
        == 50.0
    )

    assert (
        dashboard["risk"]["maximum"]
        == 0.9
    )


def test_reset():

    collector = MetricsCollector()

    collector.record({
        "decision": "ALLOW",
    })

    assert (
        collector.total_requests
        == 1
    )

    collector.reset()

    assert (
        collector.total_requests
        == 0
    )