import os

from app.audit import AuditLogger


def test_generate_request_id():

    request_id = AuditLogger.generate_request_id()

    assert isinstance(request_id, str)
    assert len(request_id) > 0


def test_audit_logger_creates_log_file(tmp_path):

    logger = AuditLogger(
        log_dir=str(tmp_path)
    )

    result = {
        "prompt": "What is the capital of India?",
        "decision": "ALLOW",
        "action": "ALLOW",
        "policy_decision": "ALLOW",
    }

    event = logger.log(result)

    assert event["request_id"]

    assert event["prompt"] == (
        "What is the capital of India?"
    )

    assert event["decision"] == "ALLOW"

    assert os.path.exists(
        logger.log_path
    )


def test_audit_logger_preserves_request_id(tmp_path):

    logger = AuditLogger(
        log_dir=str(tmp_path)
    )

    result = {
        "prompt": "Test prompt",
        "decision": "REVIEW",
    }

    event = logger.log(
        result,
        request_id="request-123"
    )

    assert event["request_id"] == "request-123"


def test_audit_logger_stores_inspections(tmp_path):

    logger = AuditLogger(
        log_dir=str(tmp_path)
    )

    result = {

        "prompt": "Test",

        "decision": "REVIEW",

        "request_inspection": {
            "decision": "ALLOW",
            "risk": 0.2,
        },

        "response_inspection": {
            "decision": "REVIEW",
            "risk": 0.7,
        },

        "events": [
            {
                "type": "review_required"
            }
        ],

        "metadata": {
            "use_case": "customer_support"
        },

        "latency_ms": 15.4,

        "model_latency_ms": 8.2,
    }

    event = logger.log(result)

    assert event["request_inspection"]["risk"] == 0.2

    assert event["response_inspection"]["risk"] == 0.7

    assert event["events"][0]["type"] == (
        "review_required"
    )

    assert event["metadata"]["use_case"] == (
        "customer_support"
    )

    assert event["latency_ms"] == 15.4

    assert event["model_latency_ms"] == 8.2


def test_read_events(tmp_path):

    logger = AuditLogger(
        log_dir=str(tmp_path)
    )

    logger.log({
        "prompt": "First",
        "decision": "ALLOW",
    })

    logger.log({
        "prompt": "Second",
        "decision": "BLOCK",
    })

    events = logger.read_events()

    assert len(events) == 2

    assert events[0]["prompt"] == "First"

    assert events[1]["prompt"] == "Second"


def test_read_events_limit(tmp_path):

    logger = AuditLogger(
        log_dir=str(tmp_path)
    )

    for i in range(10):

        logger.log({
            "prompt": f"Prompt {i}",
            "decision": "ALLOW",
        })

    events = logger.read_events(
        limit=3
    )

    assert len(events) == 3

    assert events[0]["prompt"] == "Prompt 7"

    assert events[2]["prompt"] == "Prompt 9"


def test_invalid_json_line_is_ignored(tmp_path):

    logger = AuditLogger(
        log_dir=str(tmp_path)
    )

    logger.log({
        "prompt": "Valid",
        "decision": "ALLOW",
    })

    with open(
        logger.log_path,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            "THIS IS NOT VALID JSON\n"
        )

    events = logger.read_events()

    assert len(events) == 1

    assert events[0]["prompt"] == "Valid"


def test_audit_failure_does_not_crash(tmp_path):

    logger = AuditLogger(
        log_dir=str(tmp_path)
    )

    logger.log_path = (
        os.path.join(
            str(tmp_path),
            "nonexistent",
            "audit.jsonl"
        )
    )

    # Logging must not crash the request pipeline.
    result = logger.log({
        "prompt": "Test",
        "decision": "ALLOW",
    })

    assert result["decision"] == "ALLOW"