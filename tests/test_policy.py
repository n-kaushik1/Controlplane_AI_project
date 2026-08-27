from app.policies import PolicyEngine


def test_safe_request():

    engine = PolicyEngine(
        "customer_support"
    )

    result = engine.evaluate(
        agent_results=[],
        uncertainty=0.10,
        cost=0.001,
        verification_status="VERIFIED",
    )

    assert result["decision"] == "ALLOW"


def test_high_uncertainty():

    engine = PolicyEngine(
        "customer_support"
    )

    result = engine.evaluate(
        agent_results=[],
        uncertainty=0.95,
        cost=0.001,
        verification_status="VERIFIED",
    )

    assert result["decision"] in {
        "REVIEW",
        "BLOCK",
    }


def test_unverified_claim():

    engine = PolicyEngine(
        "customer_support"
    )

    result = engine.evaluate(
        agent_results=[],
        uncertainty=0.10,
        cost=0.001,
        verification_status="UNVERIFIED",
    )

    assert result["decision"] in {
        "REVIEW",
        "BLOCK",
    }


def test_security_block():

    engine = PolicyEngine(
        "customer_support"
    )

    result = engine.evaluate(

        agent_results=[
            {
                "agent": "security",
                "risk": 0.95,
                "status": "BLOCK",
            }
        ],

        uncertainty=0.10,

        cost=0.001,

        verification_status="VERIFIED",
    )

    assert result["decision"] == "BLOCK"


def test_regulated_policy_is_stricter():

    engine = PolicyEngine(
        "regulated"
    )

    result = engine.evaluate(
        agent_results=[],
        uncertainty=0.40,
        cost=0.001,
        verification_status="VERIFIED",
    )

    assert result["decision"] in {
        "REVIEW",
        "BLOCK",
    }