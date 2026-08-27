from app.agents.bias_agent import BiasAgent
from app.agents.cost_agent import CostAgent
from app.agents.factuality_agent import FactualityAgent
from app.agents.orchestrator import AgentOrchestrator
from app.agents.privacy_agent import PrivacyAgent
from app.agents.security_agent import SecurityAgent
from app.audit import AuditLogger
from app.core.factuality_engine import FactualityEngine
from app.gateway.request_gateway import RequestGateway


class FakeProvider:

    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate(self, messages):
        self.calls += 1

        return {
            "response": self.response
        }


def build_factuality_gateway(tmp_path):

    # ---------------------------------------------------------
    # Factuality Engine
    # ---------------------------------------------------------

    factuality_engine = FactualityEngine()

    factuality_agent = FactualityAgent(
        claim_extractor=(
            factuality_engine.extract_claims
        ),
        verifier=(
            factuality_engine.verify_claims
        ),
        evidence=(
            factuality_engine.evidence
        ),
    )

    # ---------------------------------------------------------
    # Full Governance Orchestrator
    # ---------------------------------------------------------

    orchestrator = AgentOrchestrator(
        security_agent=SecurityAgent(),
        privacy_agent=PrivacyAgent(),
        bias_agent=BiasAgent(),
        factuality_agent=factuality_agent,
        cost_agent=CostAgent(),
    )

    # ---------------------------------------------------------
    # Audit Logger
    # ---------------------------------------------------------

    audit_logger = AuditLogger(
        log_dir=str(
            tmp_path / "audit"
        )
    )

    # ---------------------------------------------------------
    # Model
    # ---------------------------------------------------------

    provider = FakeProvider(
        "The capital of India is Mumbai."
    )

    # ---------------------------------------------------------
    # Gateway
    # ---------------------------------------------------------

    gateway = RequestGateway(
        model_provider=provider,
        orchestrator=orchestrator,
        audit_logger=audit_logger,
    )

    return (
        gateway,
        provider,
        audit_logger,
    )


def _find_factuality_agent(
    inspection
):
    """
    Locate the factuality agent inside
    the orchestrator inspection result.
    """

    agents = inspection.get(
        "agents",
        []
    )

    for agent in agents:

        if (
            isinstance(agent, dict)
            and
            agent.get("agent")
            == "factuality"
        ):
            return agent

    return None


def test_factuality_reaches_governance(
    tmp_path
):

    (
        gateway,
        provider,
        audit_logger,
    ) = build_factuality_gateway(
        tmp_path
    )

    result = gateway.process(
        "What is the capital of India?"
    )

    # ---------------------------------------------------------
    # Model was actually called.
    # ---------------------------------------------------------

    assert provider.calls == 1

    # ---------------------------------------------------------
    # Response governance exists.
    # ---------------------------------------------------------

    response_governance = (
        result.get(
            "response_governance",
            {}
        )
    )

    assert isinstance(
        response_governance,
        dict
    )

    # ---------------------------------------------------------
    # Factuality agent must be present.
    # ---------------------------------------------------------

    factuality_agent = (
        _find_factuality_agent(
            response_governance
        )
    )

    assert factuality_agent is not None

    # ---------------------------------------------------------
    # Factuality signals must be preserved.
    # ---------------------------------------------------------

    signals = factuality_agent.get(
        "signals",
        {}
    )

    assert isinstance(
        signals,
        dict
    )

    assert (
        "verification"
        in signals
    )

    assert (
        "factuality_status"
        in signals
    )


def test_factuality_result_reaches_audit(
    tmp_path
):

    (
        gateway,
        provider,
        audit_logger,
    ) = build_factuality_gateway(
        tmp_path
    )

    result = gateway.process(
        "What is the capital of India?"
    )

    # ---------------------------------------------------------
    # Gateway result exists.
    # ---------------------------------------------------------

    assert isinstance(
        result,
        dict
    )

    # ---------------------------------------------------------
    # Audit must contain the request.
    # ---------------------------------------------------------

    events = (
        audit_logger
        .read_events(
            10
        )
    )

    assert len(events) >= 1

    event = events[-1]

    # ---------------------------------------------------------
    # Core audit fields.
    # ---------------------------------------------------------

    assert (
        event.get("request_id")
        == result.get("metadata", {}).get(
            "request_id"
        )
    )

    assert (
        event.get("prompt")
        == "What is the capital of India?"
    )

    # ---------------------------------------------------------
    # Factuality must be persisted.
    # ---------------------------------------------------------

    factuality = event.get(
        "factuality"
    )

    assert isinstance(
        factuality,
        dict
    )

    assert (
        factuality.get("enabled")
        is True
    )

    assert (
        "status"
        in factuality
    )

    assert (
        "claims"
        in factuality
    )

    assert (
        "details"
        in factuality
    )


def test_factuality_does_not_bypass_other_governance(
    tmp_path
):

    (
        gateway,
        provider,
        audit_logger,
    ) = build_factuality_gateway(
        tmp_path
    )

    result = gateway.process(
        "What is the capital of India?"
    )

    response_governance = (
        result.get(
            "response_governance",
            {}
        )
    )

    agents = response_governance.get(
        "agents",
        []
    )

    agent_names = {
        agent.get("agent")
        for agent in agents
        if isinstance(agent, dict)
    }

    # ---------------------------------------------------------
    # Factuality must coexist with the existing
    # governance agents.
    # ---------------------------------------------------------

    assert "factuality" in agent_names
    assert "bias" in agent_names
    assert "privacy" in agent_names