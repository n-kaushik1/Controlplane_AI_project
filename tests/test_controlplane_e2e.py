import pytest

from app.api.routes import gateway

from app.gateway.request_gateway import (
    RequestGateway,
)

from app.models.provider import (
    MockModelProvider,
)

from app.audit import (
    AuditLogger,
)


# ============================================================
# TEST GATEWAY
# ============================================================
#
# These E2E tests must not depend on an external LLM provider.
#
# The production gateway remains completely unchanged.
#
# We create a separate RequestGateway using the existing
# MockModelProvider so that:
#
#     pytest
#         ↓
#     deterministic model response
#         ↓
#     response governance
#         ↓
#     factuality
#         ↓
#     audit
#
# This prevents provider rate limits, API outages, or network
# failures from making governance tests nondeterministic.
# ============================================================

@pytest.fixture
def test_gateway():

    return RequestGateway(
        model_provider=MockModelProvider(),
        orchestrator=gateway.orchestrator,
        audit_logger=gateway.audit_logger,
        metrics_collector=gateway.metrics_collector,
    )


# ============================================================
# NORMAL REQUEST
# ============================================================

def test_allow_normal_request(
    test_gateway,
):

    result = test_gateway.process(
        "Hello, how are you?"
    )

    assert isinstance(
        result,
        dict,
    )

    assert result["decision"] in {
        "ALLOW",
        "REVIEW",
        "BLOCK",
    }

    assert result.get(
        "metadata",
        {},
    ).get(
        "request_id"
    )


# ============================================================
# RESPONSE GOVERNANCE
# ============================================================

def test_factual_request_has_response_governance(
    test_gateway,
):

    result = test_gateway.process(
        "What is the capital of India?"
    )

    assert isinstance(
        result,
        dict,
    )

    assert "request_governance" in result

    assert "response_governance" in result

    response_governance = (
        result[
            "response_governance"
        ]
    )

    assert isinstance(
        response_governance,
        dict,
    )

    assert "decision" in (
        response_governance
    )

    assert "agents" in (
        response_governance
    )


# ============================================================
# FACTUALITY AGENT
# ============================================================

def test_factuality_agent_is_present(
    test_gateway,
):

    result = test_gateway.process(
        "What is the capital of India?"
    )

    agents = result[
        "response_governance"
    ]["agents"]

    factuality_agents = [
        agent
        for agent in agents
        if agent.get(
            "agent"
        ) == "factuality"
    ]

    assert factuality_agents

    factuality = (
        factuality_agents[0]
    )

    assert "signals" in factuality

    assert (
        "verification"
        in factuality[
            "signals"
        ]
    )


# ============================================================
# REQUEST ID
# ============================================================

def test_request_id_is_preserved(
    test_gateway,
):

    result = test_gateway.process(
        "What is the capital of India?"
    )

    request_id = (
        result
        .get(
            "metadata",
            {},
        )
        .get(
            "request_id"
        )
    )

    assert request_id

    assert isinstance(
        request_id,
        str,
    )


# ============================================================
# AUDIT
# ============================================================

def test_audit_is_written_for_request(
    test_gateway,
):

    result = test_gateway.process(
        "What is the capital of India?"
    )

    request_id = (
        result
        .get(
            "metadata",
            {},
        )
        .get(
            "request_id"
        )
    )

    assert request_id

    audit_logger = AuditLogger()

    events = (
        audit_logger.read_events(
            20
        )
    )

    assert events

    matching = [
        event
        for event in events
        if event.get(
            "request_id"
        ) == request_id
    ]

    assert matching

    event = matching[-1]

    assert event.get(
        "prompt"
    ) == (
        "What is the capital of India?"
    )

    assert "governance" in event

    assert "factuality" in event


# ============================================================
# AUDIT FACTUALITY STRUCTURE
# ============================================================

def test_audit_factuality_structure(
    test_gateway,
):

    result = test_gateway.process(
        "What is the capital of India?"
    )

    request_id = (
        result
        .get(
            "metadata",
            {},
        )
        .get(
            "request_id"
        )
    )

    assert request_id

    audit_logger = AuditLogger()

    events = (
        audit_logger.read_events(
            20
        )
    )

    matching = [
        event
        for event in events
        if event.get(
            "request_id"
        ) == request_id
    ]

    assert matching

    factuality = (
        matching[-1].get(
            "factuality"
        )
    )

    assert isinstance(
        factuality,
        dict,
    )

    assert "enabled" in factuality

    assert "status" in factuality

    assert "claims" in factuality

    assert "verified_count" in factuality

    assert "failed_count" in factuality

    assert "unknown_count" in factuality