from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class RiskProfile:

    name: str

    description: str

    # Maximum acceptable aggregate risk
    max_risk: float

    # Maximum acceptable uncertainty
    max_uncertainty: float

    # Maximum estimated request cost
    max_cost: float

    # Maximum acceptable latency
    max_latency_ms: float

    # Whether factual verification is mandatory
    require_factuality: bool

    # Whether human review is available
    human_review: bool

    # Whether PII protection is mandatory
    require_privacy: bool

    # Whether bias checks are mandatory
    require_bias_check: bool

    # How strict prompt-injection detection should be
    security_threshold: float

    # ------------------------------------------------------------------
    # Round 2 additions
    # ------------------------------------------------------------------

    # Human-readable enterprise use-case category
    risk_level: str = "high"

    # Governance priorities for this use case
    priorities: tuple = ()

    # Whether consequential actions require human approval
    require_human_for_consequential_action: bool = True

    # Regulatory context identifier
    regulatory_context: str = "enterprise"

    # Whether the profile supports conversation/turn-level tracking
    supports_multi_turn: bool = True


# ======================================================================
# ENTERPRISE RISK PROFILES
# ======================================================================

RISK_PROFILES: Dict[str, RiskProfile] = {

    # ------------------------------------------------------------------
    # CUSTOMER SUPPORT
    # ------------------------------------------------------------------

    "customer_support": RiskProfile(

        name="customer_support",

        description=(
            "Customer-facing AI with balanced latency and safety "
            "requirements. Privacy, security, factuality and bias "
            "controls are enabled while maintaining responsive "
            "interaction."
        ),

        max_risk=0.55,

        max_uncertainty=0.70,

        max_cost=0.03,

        max_latency_ms=3000,

        require_factuality=True,

        human_review=True,

        require_privacy=True,

        require_bias_check=True,

        security_threshold=0.70,

        risk_level="high",

        priorities=(
            "privacy",
            "security",
            "factuality",
            "bias",
        ),

        require_human_for_consequential_action=True,

        regulatory_context="enterprise_privacy",

        supports_multi_turn=True,
    ),

    # ------------------------------------------------------------------
    # INTERNAL KNOWLEDGE ASSISTANT
    # ------------------------------------------------------------------

    "internal_copilot": RiskProfile(

        name="internal_copilot",

        description=(
            "Internal employee-facing AI with stronger emphasis on "
            "grounded factual answers, enterprise data protection, "
            "source traceability and productivity."
        ),

        max_risk=0.65,

        max_uncertainty=0.75,

        max_cost=0.05,

        max_latency_ms=5000,

        require_factuality=True,

        human_review=True,

        require_privacy=True,

        require_bias_check=True,

        security_threshold=0.75,

        risk_level="high",

        priorities=(
            "factuality",
            "privacy",
            "security",
            "bias",
        ),

        require_human_for_consequential_action=True,

        regulatory_context="enterprise_data_governance",

        supports_multi_turn=True,
    ),

    # ------------------------------------------------------------------
    # REGULATED DECISION SUPPORT
    # ------------------------------------------------------------------

    "regulated_decision": RiskProfile(

        name="regulated_decision",

        description=(
            "High-risk AI used in regulated or decision-support "
            "workflows. The strictest controls are applied across "
            "factuality, bias, privacy, security and human oversight."
        ),

        max_risk=0.25,

        max_uncertainty=0.35,

        max_cost=0.10,

        max_latency_ms=10000,

        require_factuality=True,

        human_review=True,

        require_privacy=True,

        require_bias_check=True,

        security_threshold=0.50,

        risk_level="critical",

        priorities=(
            "factuality",
            "bias",
            "privacy",
            "security",
        ),

        require_human_for_consequential_action=True,

        regulatory_context="high_impact_ai",

        supports_multi_turn=True,
    ),
}


# ======================================================================
# PROFILE ALIASES
# ======================================================================

PROFILE_ALIASES = {

    "customer-support":
        "customer_support",

    "customer support":
        "customer_support",

    "customer":
        "customer_support",

    "internal-copilot":
        "internal_copilot",

    "internal copilot":
        "internal_copilot",

    "internal":
        "internal_copilot",

    "regulated-decision":
        "regulated_decision",

    "regulated decision":
        "regulated_decision",

    "decision_support":
        "regulated_decision",

    "decision-support":
        "regulated_decision",

    "decision support":
        "regulated_decision",

    "regulated":
        "regulated_decision",
}


# ======================================================================
# PROFILE HELPERS
# ======================================================================

def get_risk_profile(name: str) -> RiskProfile:

    if not name:

        raise ValueError(
            "Risk profile name is required."
        )

    normalized = (
        name
        .strip()
        .lower()
        .replace("-", "_")
    )

    normalized = PROFILE_ALIASES.get(
        normalized,
        normalized
    )

    if normalized not in RISK_PROFILES:

        raise ValueError(
            f"Unknown risk profile: {name}"
        )

    return RISK_PROFILES[normalized]


def list_risk_profiles():

    return list(
        RISK_PROFILES.keys()
    )


def get_profile_summary(
    name: str
):

    profile = get_risk_profile(
        name
    )

    return {

        "name":
            profile.name,

        "description":
            profile.description,

        "risk_level":
            profile.risk_level,

        "max_risk":
            profile.max_risk,

        "max_uncertainty":
            profile.max_uncertainty,

        "max_cost":
            profile.max_cost,

        "max_latency_ms":
            profile.max_latency_ms,

        "require_factuality":
            profile.require_factuality,

        "human_review":
            profile.human_review,

        "require_privacy":
            profile.require_privacy,

        "require_bias_check":
            profile.require_bias_check,

        "security_threshold":
            profile.security_threshold,

        "priorities":
            list(profile.priorities),

        "require_human_for_consequential_action":
            profile.require_human_for_consequential_action,

        "regulatory_context":
            profile.regulatory_context,

        "supports_multi_turn":
            profile.supports_multi_turn,
    }


def get_all_profile_summaries():

    return [
        get_profile_summary(
            name
        )
        for name in RISK_PROFILES
    ]