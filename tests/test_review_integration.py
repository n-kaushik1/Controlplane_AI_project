from app.audit import AuditLogger
from app.feedback import (
    FeedbackStore,
    ReviewQueue,
    ReviewService,
)
from app.gateway.request_gateway import (
    RequestGateway,
)
from app.gateway.review_gateway import (
    ReviewAwareGateway,
)


class FakeProvider:

    def __init__(self, response):

        self.response = response

    def generate(self, messages):

        return self.response


class ReviewOrchestrator:

    def inspect_request(self, prompt):

        return {
            "decision": "ALLOW",
            "risk_score": 0.1,
            "confidence": 0.9,
        }

    def inspect_response(self, response):

        return {
            "decision": "REVIEW",
            "risk_score": 0.72,
            "confidence": 0.6,
            "reason": "Potential factual uncertainty.",
        }


class AllowOrchestrator:

    def inspect_request(self, prompt):

        return {
            "decision": "ALLOW",
        }

    def inspect_response(self, response):

        return {
            "decision": "ALLOW",
        }


def build_review_gateway(tmp_path):

    provider = FakeProvider(
        "This response needs checking."
    )

    queue = ReviewQueue()

    feedback = FeedbackStore(
        file_path=str(
            tmp_path / "feedback.jsonl"
        )
    )

    audit = AuditLogger(
        log_dir=str(
            tmp_path / "audit"
        )
    )

    gateway = RequestGateway(
        model_provider=provider,
        orchestrator=ReviewOrchestrator(),
        audit_logger=audit,
    )

    service = ReviewService(
        review_queue=queue,
        feedback_store=feedback,
        audit_logger=audit,
    )

    return (
        ReviewAwareGateway(
            gateway=gateway,
            review_service=service,
        ),
        queue,
        feedback,
    )


def test_gateway_creates_review(
    tmp_path
):

    gateway, queue, _ = (
        build_review_gateway(
            tmp_path
        )
    )

    result = gateway.process(
        "Tell me something."
    )

    assert result["decision"] == "REVIEW"

    assert "review_id" in result

    assert result["review_status"] == (
        "PENDING"
    )

    assert len(
        queue.pending()
    ) == 1


def test_review_id_matches_queue_item(
    tmp_path
):

    gateway, queue, _ = (
        build_review_gateway(
            tmp_path
        )
    )

    result = gateway.process(
        "Test request"
    )

    review_id = result[
        "review_id"
    ]

    item = queue.get(
        review_id
    )

    assert item is not None

    assert item.review_id == (
        review_id
    )

    assert item.request_id == (
        result["request_id"]
    )


def test_resolve_review_persists_feedback(
    tmp_path
):

    gateway, queue, feedback = (
        build_review_gateway(
            tmp_path
        )
    )

    result = gateway.process(
        "Test request"
    )

    review_id = result[
        "review_id"
    ]

    resolved = gateway.resolve_review(
        review_id=review_id,
        final_decision="ALLOW",
        reviewer="admin",
        comment="Verified manually.",
    )

    assert (
        resolved["review"]["status"]
        == "RESOLVED"
    )

    assert (
        resolved["review"]["final_decision"]
        == "ALLOW"
    )

    records = feedback.read_all()

    assert len(records) == 1

    assert records[0]["review_id"] == (
        review_id
    )

    assert records[0][
        "final_decision"
    ] == "ALLOW"


def test_resolved_review_leaves_queue(
    tmp_path
):

    gateway, queue, _ = (
        build_review_gateway(
            tmp_path
        )
    )

    result = gateway.process(
        "Test request"
    )

    review_id = result[
        "review_id"
    ]

    gateway.resolve_review(
        review_id=review_id,
        final_decision="BLOCK",
        reviewer="security",
        comment="Unsafe.",
    )

    assert len(
        queue.pending()
    ) == 0


def test_allow_does_not_create_review(
    tmp_path
):

    provider = FakeProvider(
        "Safe response."
    )

    queue = ReviewQueue()

    feedback = FeedbackStore(
        file_path=str(
            tmp_path / "feedback.jsonl"
        )
    )

    gateway = RequestGateway(
        model_provider=provider,
        orchestrator=AllowOrchestrator(),
    )

    service = ReviewService(
        review_queue=queue,
        feedback_store=feedback,
    )

    review_gateway = ReviewAwareGateway(
        gateway=gateway,
        review_service=service,
    )

    result = review_gateway.process(
        "Normal request"
    )

    assert result["decision"] == "ALLOW"

    assert "review_id" not in result

    assert len(
        queue.pending()
    ) == 0


def test_feedback_summary_after_resolution(
    tmp_path
):

    gateway, _, _ = (
        build_review_gateway(
            tmp_path
        )
    )

    result = gateway.process(
        "Test"
    )

    gateway.resolve_review(
        review_id=result[
            "review_id"
        ],
        final_decision="BLOCK",
        reviewer="security",
    )

    summary = (
        gateway
        .feedback_summary()
    )

    assert summary["total"] == 1

    assert summary["blocked"] == 1