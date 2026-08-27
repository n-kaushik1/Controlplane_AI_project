from dataclasses import dataclass, field
from typing import Any, Dict, List

from .policies import (
    PolicyProfile,
    get_policy,
)


@dataclass
class PolicyDecision:

    decision: str

    risk: float

    reason: str

    policy: str

    triggered_rules: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "decision": self.decision,
            "risk": round(
                float(self.risk),
                4
            ),
            "reason": self.reason,
            "policy": self.policy,
            "triggered_rules": self.triggered_rules,
            "metadata": self.metadata,
        }


class PolicyEngine:

    """
    Central governance decision engine.

    Converts agent signals into a single
    enterprise policy decision.

    Backward compatibility is intentionally preserved:

        - Existing constructor remains valid.
        - Existing evaluate() arguments remain valid.
        - Existing policy thresholds remain valid.
        - Existing ALLOW / REVIEW / MODIFY / BLOCK
          decision ordering remains intact.

    Round 2 additions:

        - Profile-specific latency enforcement
        - Security-specific threshold
        - Explicit factuality/privacy/bias requirements
        - Human-review profile awareness
        - Consequential-action oversight
        - Profile metadata in policy output
    """

    def __init__(
        self,
        policy: PolicyProfile | str = "customer_support",
    ):

        if isinstance(
            policy,
            str
        ):

            self.policy = get_policy(
                policy
            )

        else:

            self.policy = policy

    # ========================================================
    # PUBLIC API
    # ========================================================

    def evaluate(
        self,
        agent_results,
        uncertainty: float = 0.0,
        cost: float = 0.0,
        verification_status: str = "UNKNOWN",
        latency_ms: float = 0.0,
        consequential_action: bool = False,
    ) -> Dict[str, Any]:

        rules = []

        risk = 0.0

        # ----------------------------------------------------
        # Normalize agent results
        # ----------------------------------------------------

        normalized = []

        for result in agent_results:

            if hasattr(
                result,
                "to_dict"
            ):

                result = result.to_dict()

            if not isinstance(
                result,
                dict
            ):

                continue

            normalized.append(
                result
            )

        # ----------------------------------------------------
        # Aggregate agent risk
        # ----------------------------------------------------

        for result in normalized:

            agent = str(
                result.get(
                    "agent",
                    "unknown"
                )
            ).lower()

            try:

                agent_risk = float(
                    result.get(
                        "risk",
                        0.0
                    )
                    or 0.0
                )

            except (
                TypeError,
                ValueError,
            ):

                agent_risk = 0.0

            status = str(
                result.get(
                    "status",
                    "PASS"
                )
            ).upper()

            risk = max(
                risk,
                agent_risk
            )

            # ------------------------------------------------
            # Explicit BLOCK from an agent
            # ------------------------------------------------

            if status == "BLOCK":

                rules.append(
                    f"{agent}:BLOCK"
                )

            # ------------------------------------------------
            # Explicit REVIEW
            # ------------------------------------------------

            elif status in {
                "REVIEW",
                "WARN",
                "ESCALATE",
            }:

                rules.append(
                    f"{agent}:REVIEW"
                )

            # ------------------------------------------------
            # Explicit privacy enforcement
            # ------------------------------------------------

            if (
                agent == "privacy"
                and self._privacy_required()
                and agent_risk >= 0.50
            ):

                rules.append(
                    "privacy:policy_threshold"
                )

            # ------------------------------------------------
            # Explicit bias enforcement
            # ------------------------------------------------

            if (
                agent == "bias"
                and self._bias_required()
                and agent_risk >= 0.50
            ):

                rules.append(
                    "bias:policy_threshold"
                )

            # ------------------------------------------------
            # Explicit security threshold
            # ------------------------------------------------

            if (
                agent == "security"
                and self.policy.security_threshold
                is not None
                and agent_risk
                >= self.policy.security_threshold
            ):

                rules.append(
                    "security:policy_threshold"
                )

                risk = max(
                    risk,
                    self.policy.security_threshold
                )

        # ----------------------------------------------------
        # Cost rule
        # ----------------------------------------------------

        if cost > self.policy.max_cost:

            rules.append(
                "cost:budget_exceeded"
            )

            risk = max(
                risk,
                0.80
            )

        # ----------------------------------------------------
        # Uncertainty rule
        # ----------------------------------------------------

        if (
            uncertainty
            > self.policy.max_uncertainty
        ):

            rules.append(
                "uncertainty:high"
            )

            risk = max(
                risk,
                0.70
            )

        # ----------------------------------------------------
        # Latency rule
        #
        # This is only activated for profiles that explicitly
        # configure max_latency_ms.
        # ----------------------------------------------------

        if (
            self.policy.max_latency_ms
            is not None
            and latency_ms
            > self.policy.max_latency_ms
        ):

            rules.append(
                "latency:budget_exceeded"
            )

            # Latency itself is not automatically treated as
            # catastrophic risk. We use the review threshold
            # as the conservative floor.
            risk = max(
                risk,
                self.policy.review_risk
            )

        # ----------------------------------------------------
        # Factual verification
        # ----------------------------------------------------

        verification = str(
            verification_status
        ).upper()

        if (
            self._factuality_required()
            and verification in {
                "FAILED",
                "UNVERIFIED",
                "UNKNOWN",
                "NOT_FOUND",
                "UNSUPPORTED",
                "NO_EVIDENCE",
            }
        ):

            rules.append(
                "factuality:unverified"
            )

            risk = max(
                risk,
                0.75
            )

        # ----------------------------------------------------
        # Consequential action
        # ----------------------------------------------------

        if (
            consequential_action
            and self.policy
            .require_human_for_consequential_action
        ):

            rules.append(
                "human_review:consequential_action"
            )

        # ----------------------------------------------------
        # Determine final decision
        # ----------------------------------------------------

        decision = "ALLOW"

        reason = (
            "Request passed governance policy."
        )

        # ====================================================
        # BLOCK
        # ====================================================

        if any(
            rule.endswith(":BLOCK")
            for rule in rules
        ):

            decision = "BLOCK"

            reason = (
                "Request blocked because a "
                "governance agent detected a "
                "high-risk condition."
            )

        elif (
            risk
            >= self.policy.block_risk
        ):

            decision = "BLOCK"

            reason = (
                "Aggregated risk exceeded the "
                "policy blocking threshold."
            )

        # ====================================================
        # SECURITY POLICY THRESHOLD
        # ====================================================

        elif any(
            rule
            == "security:policy_threshold"
            for rule in rules
        ):

            decision = "BLOCK"

            reason = (
                "Request blocked because the "
                "security risk exceeded the "
                "selected use-case threshold."
            )

        # ====================================================
        # CONSEQUENTUAL ACTION / HUMAN REVIEW
        # ====================================================

        elif any(
            rule
            == "human_review:consequential_action"
            for rule in rules
        ):

            decision = "REVIEW"

            reason = (
                "Consequential action requires "
                "human oversight under the "
                "selected governance profile."
            )

        # ====================================================
        # REVIEW
        # ====================================================

        elif (
            risk
            >= self.policy.review_risk
        ):

            decision = "REVIEW"

            reason = (
                "Request requires additional "
                "review because its risk exceeds "
                "the policy review threshold."
            )

        # ====================================================
        # MODIFY
        # ====================================================

        elif any(
            rule.startswith("privacy:")
            for rule in rules
        ):

            decision = "MODIFY"

            reason = (
                "Request can proceed after "
                "privacy-related modification."
            )

        # ====================================================
        # BUILD RESULT
        # ====================================================

        result = PolicyDecision(

            decision=decision,

            risk=risk,

            reason=reason,

            policy=self.policy.name,

            triggered_rules=rules,

            metadata={

                # Existing metadata preserved.
                "uncertainty":
                    uncertainty,

                "cost":
                    cost,

                "verification_status":
                    verification_status,

                "agent_count":
                    len(normalized),

                # Round 2 metadata.
                "risk_level":
                    self.policy.risk_level,

                "max_risk":
                    self._max_risk(),

                "block_risk":
                    self.policy.block_risk,

                "review_risk":
                    self.policy.review_risk,

                "max_uncertainty":
                    self.policy.max_uncertainty,

                "max_cost":
                    self.policy.max_cost,

                "max_latency_ms":
                    self.policy.max_latency_ms,

                "latency_ms":
                    latency_ms,

                "security_threshold":
                    self.policy.security_threshold,

                "human_review":
                    self.policy.human_review,

                "require_human_for_consequential_action":
                    self.policy
                    .require_human_for_consequential_action,

                "consequential_action":
                    consequential_action,

                "supports_multi_turn":
                    self.policy.supports_multi_turn,

                "regulatory_context":
                    self.policy.regulatory_context,

                "priorities":
                    list(
                        self.policy.priorities
                    ),
            },
        )

        return result.to_dict()

    # ========================================================
    # PROFILE HELPERS
    # ========================================================

    def _factuality_required(
        self,
    ) -> bool:

        if (
            self.policy.require_factuality
            is not None
        ):

            return bool(
                self.policy.require_factuality
            )

        return bool(
            self.policy
            .require_factual_verification
        )

    # --------------------------------------------------------

    def _privacy_required(
        self,
    ) -> bool:

        if (
            self.policy.require_privacy
            is not None
        ):

            return bool(
                self.policy.require_privacy
            )

        return bool(
            self.policy.enforce_privacy
        )

    # --------------------------------------------------------

    def _bias_required(
        self,
    ) -> bool:

        if (
            self.policy.require_bias_check
            is not None
        ):

            return bool(
                self.policy.require_bias_check
            )

        return bool(
            self.policy.enforce_bias
        )

    # --------------------------------------------------------

    def _max_risk(
        self,
    ) -> float:

        if (
            self.policy.max_risk
            is not None
        ):

            return float(
                self.policy.max_risk
            )

        return float(
            self.policy.block_risk
        )