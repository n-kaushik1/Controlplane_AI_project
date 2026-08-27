from app.feedback import (
    ReviewQueue,
    FeedbackStore,
    ReviewItem,
)


def test_create_review():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-001",
        prompt="Test prompt",
        model_response="Test response",
        risk_score=0.72,
        reason="Potential factuality issue",
    )

    assert isinstance(
        item,
        ReviewItem
    )

    assert item.request_id == "req-001"

    assert item.status == "PENDING"

    assert item.final_decision is None

    assert item.risk_score == 0.72


def test_pending_reviews():

    queue = ReviewQueue()

    queue.create_review(
        request_id="req-001",
        prompt="First",
    )

    queue.create_review(
        request_id="req-002",
        prompt="Second",
    )

    assert len(
        queue.pending()
    ) == 2


def test_get_review():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-001",
        prompt="Test",
    )

    result = queue.get(
        item.review_id
    )

    assert result is item


def test_resolve_review_allow():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-001",
        prompt="Test",
    )

    resolved = queue.resolve(
        review_id=item.review_id,
        final_decision="ALLOW",
        reviewer="admin",
        comment="Looks safe.",
    )

    assert resolved.status == "RESOLVED"

    assert resolved.final_decision == "ALLOW"

    assert resolved.reviewer == "admin"

    assert resolved.reviewer_comment == (
        "Looks safe."
    )

    assert resolved.reviewed_at is not None

    assert len(
        queue.pending()
    ) == 0


def test_resolve_review_block():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-002",
        prompt="Sensitive request",
    )

    queue.resolve(
        review_id=item.review_id,
        final_decision="BLOCK",
        reviewer="security",
        comment="Unsafe content.",
    )

    result = queue.get(
        item.review_id
    )

    assert result.final_decision == "BLOCK"


def test_resolve_review_edit():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-003",
        prompt="Needs correction",
    )

    queue.resolve(
        review_id=item.review_id,
        final_decision="EDIT",
        reviewer="reviewer",
        comment="Correct factual error.",
    )

    assert (
        queue.get(
            item.review_id
        ).final_decision
        == "EDIT"
    )


def test_invalid_review_decision():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-004",
        prompt="Test",
    )

    try:

        queue.resolve(
            review_id=item.review_id,
            final_decision="UNKNOWN",
            reviewer="admin",
        )

        assert False

    except ValueError as exc:

        assert (
            "ALLOW, BLOCK, or EDIT"
            in str(exc)
        )


def test_missing_reviewer():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-005",
        prompt="Test",
    )

    try:

        queue.resolve(
            review_id=item.review_id,
            final_decision="ALLOW",
            reviewer="",
        )

        assert False

    except ValueError as exc:

        assert "reviewer" in str(exc)


def test_missing_review():

    queue = ReviewQueue()

    try:

        queue.resolve(
            review_id="does-not-exist",
            final_decision="ALLOW",
            reviewer="admin",
        )

        assert False

    except ValueError:

        assert True


def test_feedback_store(tmp_path):

    store = FeedbackStore(
        file_path=str(
            tmp_path / "feedback.jsonl"
        )
    )

    feedback = {
        "review_id": "review-001",
        "request_id": "request-001",
        "final_decision": "ALLOW",
        "reviewer": "admin",
    }

    store.save(
        feedback
    )

    records = store.read_all()

    assert len(records) == 1

    assert records[0]["review_id"] == (
        "review-001"
    )


def test_feedback_store_multiple_records(
    tmp_path
):

    store = FeedbackStore(
        file_path=str(
            tmp_path / "feedback.jsonl"
        )
    )

    store.save({
        "review_id": "1",
        "final_decision": "ALLOW",
    })

    store.save({
        "review_id": "2",
        "final_decision": "BLOCK",
    })

    records = store.read_all()

    assert len(records) == 2


def test_feedback_summary(tmp_path):

    store = FeedbackStore(
        file_path=str(
            tmp_path / "feedback.jsonl"
        )
    )

    store.save({
        "final_decision": "ALLOW",
    })

    store.save({
        "final_decision": "BLOCK",
    })

    store.save({
        "final_decision": "EDIT",
    })

    store.save({
        "final_decision": "BLOCK",
    })

    summary = store.summary()

    assert summary["total"] == 4

    assert summary["approved"] == 1

    assert summary["blocked"] == 2

    assert summary["edited"] == 1


def test_review_item_serialization():

    queue = ReviewQueue()

    item = queue.create_review(
        request_id="req-100",
        prompt="Hello",
        model_response="World",
        risk_score=0.5,
        reason="Needs review",
        metadata={
            "use_case": "internal"
        },
    )

    data = item.to_dict()

    assert data["request_id"] == "req-100"

    assert data["prompt"] == "Hello"

    assert data["model_response"] == "World"

    assert data["risk_score"] == 0.5

    assert data["metadata"]["use_case"] == (
        "internal"
    )


def test_review_item_from_dict():

    data = {
        "review_id": "review-100",
        "request_id": "req-100",
        "prompt": "Hello",
        "model_response": "World",
        "decision": "REVIEW",
        "risk_score": 0.8,
        "reason": "Risk",
        "status": "RESOLVED",
        "reviewer": "admin",
        "reviewer_comment": "Approved",
        "final_decision": "ALLOW",
    }

    item = ReviewItem.from_dict(
        data
    )

    assert item.review_id == "review-100"

    assert item.status == "RESOLVED"

    assert item.final_decision == "ALLOW"

    assert item.reviewer == "admin"