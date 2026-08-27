from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PolicyProfile:
    """
    Governance policy for a specific AI use case.

    Lower thresholds mean stricter governance.

    Backward compatibility:
        - Existing fields such as block_risk, review_risk,
          max_uncertainty and max_cost are preserved.
        - Additional Round 2 fields are optional and therefore
          do not break existing PolicyProfile construction.
    """

    name: str

    # --------------------------------------------------------
    # Existing policy thresholds
    # --------------------------------------------------------

    # Maximum acceptable aggregated risk before blocking.
    block_risk: float

    # Risk above this level requires human review.
    review_risk: float

    # Maximum acceptable uncertainty.
    max_uncertainty: float

    # Maximum acceptable estimated cost.
    max_cost: float

    # --------------------------------------------------------
    # Existing governance controls
    # --------------------------------------------------------

    # Whether factual verification is mandatory.
    require_factual_verification: bool = True

    # Whether PII detection is enforced.
    enforce_privacy: bool = True

    # Whether bias detection is enforced.
    enforce_bias: bool = True

    # Whether security detection is enforced.
    enforce_security: bool = True

    # --------------------------------------------------------
    # Round 2 profile controls
    # --------------------------------------------------------

    # Maximum acceptable end-to-end latency.
    #
    # None means latency is not enforced by the policy engine.
    max_latency_ms: float | None = None

    # Optional security-specific threshold.
    #
    # This is intentionally separate from block_risk so that
    # security can be stricter than the aggregate risk threshold.
    security_threshold: float | None = None

    # Human review requirement for the use case.
    human_review: bool = True

    # Whether consequential actions require human oversight.
    require_human_for_consequential_action: bool = True

    # Whether the profile supports multi-turn interactions.
    supports_multi_turn: bool = True

    # Regulatory/governance context.
    regulatory_context: str = "enterprise"

    # Risk classification.
    risk_level: str = "high"

    # Ordered governance priorities.
    priorities: tuple[str, ...] = ()

    # Whether factuality is explicitly required for this profile.
    require_factuality: bool | None = None

    # Whether privacy is explicitly required for this profile.
    require_privacy: bool | None = None

    # Whether bias is explicitly required for this profile.
    require_bias_check: bool | None = None

    # Maximum risk exposed through the Round 2 profile API.
    #
    # This mirrors the existing block_risk value rather than
    # creating a second independent threshold.
    max_risk: float | None = None


# ============================================================
# ENTERPRISE POLICY PROFILES
# ============================================================

CUSTOMER_SUPPORT = PolicyProfile(
    name="customer_support",

    # Existing behavior preserved.
    block_risk=0.85,
    review_risk=0.60,

    max_uncertainty=0.75,

    max_cost=0.05,

    require_factual_verification=True,

    enforce_privacy=True,
    enforce_bias=True,
    enforce_security=True,

    # Round 2 configuration.
    max_latency_ms=3000.0,

    security_threshold=0.70,

    human_review=True,

    require_human_for_consequential_action=True,

    supports_multi_turn=True,

    regulatory_context="enterprise_privacy",

    risk_level="high",

    priorities=(
        "privacy",
        "security",
        "factuality",
        "bias",
    ),

    require_factuality=True,
    require_privacy=True,
    require_bias_check=True,

    max_risk=0.55,
)


INTERNAL_COPILOT = PolicyProfile(
    name="internal_copilot",

    # Existing behavior preserved.
    block_risk=0.80,
    review_risk=0.55,

    max_uncertainty=0.70,

    max_cost=0.10,

    require_factual_verification=True,

    enforce_privacy=True,
    enforce_bias=True,
    enforce_security=True,

    # Round 2 configuration.
    max_latency_ms=5000.0,

    security_threshold=0.75,

    human_review=True,

    require_human_for_consequential_action=True,

    supports_multi_turn=True,

    regulatory_context="enterprise_data_governance",

    risk_level="high",

    priorities=(
        "factuality",
        "privacy",
        "security",
        "bias",
    ),

    require_factuality=True,
    require_privacy=True,
    require_bias_check=True,

    max_risk=0.65,
)


DECISION_SUPPORT = PolicyProfile(
    name="decision_support",

    # Existing behavior preserved.
    block_risk=0.65,
    review_risk=0.35,

    max_uncertainty=0.45,

    max_cost=0.20,

    require_factual_verification=True,

    enforce_privacy=True,
    enforce_bias=True,
    enforce_security=True,

    # Round 2 configuration.
    max_latency_ms=8000.0,

    security_threshold=0.60,

    human_review=True,

    require_human_for_consequential_action=True,

    supports_multi_turn=True,

    regulatory_context="decision_support",

    risk_level="critical",

    priorities=(
        "factuality",
        "bias",
        "privacy",
        "security",
    ),

    require_factuality=True,
    require_privacy=True,
    require_bias_check=True,

    max_risk=0.40,
)


REGULATED = PolicyProfile(
    name="regulated",

    # Existing behavior preserved.
    block_risk=0.50,
    review_risk=0.25,

    max_uncertainty=0.30,

    max_cost=0.25,

    require_factual_verification=True,

    enforce_privacy=True,
    enforce_bias=True,
    enforce_security=True,

    # Round 2 configuration.
    max_latency_ms=10000.0,

    security_threshold=0.50,

    human_review=True,

    require_human_for_consequential_action=True,

    supports_multi_turn=True,

    regulatory_context="high_impact_ai",

    risk_level="critical",

    priorities=(
        "factuality",
        "bias",
        "privacy",
        "security",
    ),

    require_factuality=True,
    require_privacy=True,
    require_bias_check=True,

    max_risk=0.25,
)


# ============================================================
# POLICY REGISTRY
# ============================================================

POLICY_PROFILES: Dict[str, PolicyProfile] = {
    "customer_support": CUSTOMER_SUPPORT,

    "internal_copilot": INTERNAL_COPILOT,

    "decision_support": DECISION_SUPPORT,

    # Existing name preserved.
    "regulated": REGULATED,

    # Round 2 API/profile name.
    #
    # Alias deliberately points to the same PolicyProfile so
    # there cannot be two different definitions of regulated
    # governance.
    "regulated_decision": REGULATED,
}


def get_policy(name: str) -> PolicyProfile:
    """
    Return a policy profile by name.

    Falls back to customer_support for unknown profiles.

    Existing fallback behavior is intentionally preserved.
    """

    if not name:

        return CUSTOMER_SUPPORT

    normalized_name = (
        str(name)
        .lower()
        .strip()
    )

    return POLICY_PROFILES.get(
        normalized_name,
        CUSTOMER_SUPPORT,
    )