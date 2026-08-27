from app.gateway.request_gateway import RequestGateway
from app.gateway.review_gateway import ReviewAwareGateway
from app.models.provider import ModelProvider, ModelResponse
from app.agents.security_agent import SecurityAgent
from app.agents.privacy_agent import PrivacyAgent
from app.agents.bias_agent import BiasAgent
from app.agents.cost_agent import CostAgent
from app.agents.factuality_agent import FactualityAgent
from app.agents.orchestrator import AgentOrchestrator
from app.core.factuality_engine import FactualityEngine
from app.audit import AuditLogger
from app.feedback import ReviewQueue, FeedbackStore, ReviewService


class ControlledFactualProvider(ModelProvider):

    def __init__(self, response):
        self.response = response

    def generate(self, prompt, **kwargs):
        return ModelResponse(
            text=self.response,
            input_tokens=len(prompt.split()),
            output_tokens=len(self.response.split()),
            latency_ms=0.0,
            model="controlled-test-model",
            provider="test",
            cost=0.0,
            metadata={
                "controlled_test": True
            },
        )


def build_gateway(tmp_path, response):

    provider = ControlledFactualProvider(response)

    audit_logger = AuditLogger(
        log_path=str(
            tmp_path / "audit.jsonl"
        )
    )

    review_queue = ReviewQueue()

    feedback_store = FeedbackStore()

    review_service = ReviewService(
        review_queue=review_queue,
        feedback_store=feedback_store,
        audit_logger=audit_logger,
    )

    factuality_engine = FactualityEngine()

    factuality_agent = FactualityAgent(
        claim_extractor=factuality_engine.extract_claims,
        verifier=factuality_engine.verify_claims,
        evidence=factuality_engine.evidence,
    )

    orchestrator = AgentOrchestrator(
        security_agent=SecurityAgent(),
        privacy_agent=PrivacyAgent(),
        bias_agent=BiasAgent(),
        factuality_agent=factuality_agent,
        cost_agent=CostAgent(),
    )

    gateway = RequestGateway(
        model_provider=provider,
        orchestrator=orchestrator,
        audit_logger=audit_logger,
    )

    review_gateway = ReviewAwareGateway(
        gateway=gateway,
        review_service=review_service,
    )

    return (
        review_gateway,
        audit_logger,
    )


def test_verified_factual_response_is_allowed(tmp_path):

    gateway, audit_logger = build_gateway(
        tmp_path,
        "The capital of India is New Delhi.",
    )

    result = gateway.process(
        "What is the capital of India?"
    )

    assert isinstance(result, dict)

    assert result["decision"] == "ALLOW"

    assert (
        result["response_governance"]["decision"]
        == "ALLOW"
    )

    factuality = next(
        agent
        for agent
        in result[
            "response_governance"
        ]["agents"]
        if agent["agent"] == "factuality"
    )

    assert (
        factuality["signals"]
        ["factuality_status"]
        == "VERIFIED"
    )

    assert (
        factuality["signals"]
        ["verification"]
        ["status"]
        == "VERIFIED"
    )

    assert (
        result.get("review_id")
        is None
        or result.get("review_id") == ""
    )


def test_failed_factual_response_goes_to_review(tmp_path):

    gateway, audit_logger = build_gateway(
        tmp_path,
        "The capital of India is Mumbai.",
    )

    result = gateway.process(
        "What is the capital of India?"
    )

    assert isinstance(result, dict)

    assert result["decision"] == "REVIEW"

    assert (
        result["response_governance"]["decision"]
        == "REVIEW"
    )

    factuality = next(
        agent
        for agent
        in result[
            "response_governance"
        ]["agents"]
        if agent["agent"] == "factuality"
    )

    verification = (
        factuality["signals"]
        ["verification"]
    )

    assert verification["status"] == "FAILED"

    assert (
        factuality["signals"]
        ["factuality_status"]
        in {
            "FAILED",
            "REVIEW",
            "BLOCK",
        }
    )

    assert result.get("review_id")

    events = audit_logger.read_events(10)

    assert events

    event = events[-1]

    assert event["request_id"] == (
        result["metadata"]["request_id"]
    )

    assert event["factuality"]["enabled"] is True

    assert (
        event["factuality"]["status"]
        == "FAILED"
    )

    assert (
        event["factuality"]["failed_count"]
        == 1
    )


def test_failed_factual_response_can_be_human_resolved(
    tmp_path,
):

    gateway, audit_logger = build_gateway(
        tmp_path,
        "The capital of India is Mumbai.",
    )

    result = gateway.process(
        "What is the capital of India?"
    )

    assert result["decision"] == "REVIEW"

    review_id = result.get(
        "review_id"
    )

    assert review_id

    pending = gateway.pending_reviews()

    assert any(
        item.get("review_id")
        == review_id
        for item in pending
    )

    resolved = gateway.resolve_review(
        review_id=review_id,
        final_decision="REJECT",
        reviewer="test-reviewer",
        comment=(
            "Rejected because factual "
            "evidence contradicts the response."
        ),
    )

    assert isinstance(
        resolved,
        dict
    )

    assert resolved.get(
        "status"
    ) in {
        "RESOLVED",
        "REJECTED",
        "CLOSED",
    }

    summary = gateway.feedback_summary()

    assert isinstance(
        summary,
        dict
    )