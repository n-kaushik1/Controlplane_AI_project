from app.context import (
    create_request_context,
    get_risk_profile,
    list_risk_profiles
)


def test_default_context():

    context = create_request_context(
        "What is the capital of India?"
    )

    assert context.prompt == (
        "What is the capital of India?"
    )

    assert context.use_case == (
        "customer_support"
    )

    assert context.risk_profile.name == (
        "customer_support"
    )

    assert context.request_id


def test_internal_copilot_profile():

    context = create_request_context(
        "Summarize this internal document.",
        use_case="internal_copilot"
    )

    assert context.risk_profile.name == (
        "internal_copilot"
    )


def test_regulated_profile_is_stricter():

    customer = get_risk_profile(
        "customer_support"
    )

    regulated = get_risk_profile(
        "regulated_decision"
    )

    assert (
        regulated.max_risk
        <
        customer.max_risk
    )

    assert (
        regulated.max_uncertainty
        <
        customer.max_uncertainty
    )


def test_profile_aliases():

    profile = get_risk_profile(
        "regulated-decision"
    )

    assert profile.name == (
        "regulated_decision"
    )


def test_all_profiles_exist():

    profiles = list_risk_profiles()

    assert "customer_support" in profiles
    assert "internal_copilot" in profiles
    assert "regulated_decision" in profiles