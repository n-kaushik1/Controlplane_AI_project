from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ActionResult:
    """
    Result produced by the ControlPlane action layer.
    """

    action: str

    output: str

    modified: bool = False

    blocked: bool = False

    review_required: bool = False

    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "output": self.output,
            "modified": self.modified,
            "blocked": self.blocked,
            "review_required": self.review_required,
            "metadata": self.metadata,
        }


class ActionExecutor:
    """
    Converts a PolicyEngine decision into an executable action.

    Supported actions:

        ALLOW
        MODIFY
        REVIEW
        BLOCK
    """

    def __init__(
        self,
        privacy_agent=None,
    ):
        self.privacy_agent = privacy_agent

    # ========================================================
    # PUBLIC API
    # ========================================================

    def execute(
        self,
        prompt: str,
        model_response: str,
        policy_decision: Dict[str, Any],
    ) -> Dict[str, Any]:

        decision = str(
            policy_decision.get(
                "decision",
                "BLOCK"
            )
        ).upper()

        # ----------------------------------------------------
        # ALLOW
        # ----------------------------------------------------

        if decision == "ALLOW":

            return ActionResult(
                action="ALLOW",
                output=model_response,
                modified=False,
                blocked=False,
                review_required=False,
                metadata={
                    "reason":
                        policy_decision.get(
                            "reason",
                            ""
                        )
                },
            ).to_dict()

        # ----------------------------------------------------
        # MODIFY
        # ----------------------------------------------------

        if decision == "MODIFY":

            modified_response = self._modify_response(
                model_response
            )

            return ActionResult(
                action="MODIFY",
                output=modified_response,
                modified=True,
                blocked=False,
                review_required=False,
                metadata={
                    "reason":
                        policy_decision.get(
                            "reason",
                            ""
                        )
                },
            ).to_dict()

        # ----------------------------------------------------
        # REVIEW
        # ----------------------------------------------------

        if decision == "REVIEW":

            return ActionResult(
                action="REVIEW",
                output=(
                    "🔎 CONTROLPLANE: "
                    "This response requires additional "
                    "review before it can be trusted.\n\n"
                    "The generated response has been "
                    "withheld by the governance policy."
                ),
                modified=False,
                blocked=False,
                review_required=True,
                metadata={
                    "reason":
                        policy_decision.get(
                            "reason",
                            ""
                        ),
                    "risk":
                        policy_decision.get(
                            "risk",
                            0.0
                        ),
                    "triggered_rules":
                        policy_decision.get(
                            "triggered_rules",
                            []
                        ),
                },
            ).to_dict()

        # ----------------------------------------------------
        # BLOCK
        # ----------------------------------------------------

        if decision == "BLOCK":

            return ActionResult(
                action="BLOCK",
                output=(
                    "🚫 CONTROLPLANE: "
                    "This request was blocked by "
                    "the active governance policy."
                ),
                modified=False,
                blocked=True,
                review_required=False,
                metadata={
                    "reason":
                        policy_decision.get(
                            "reason",
                            ""
                        ),
                    "risk":
                        policy_decision.get(
                            "risk",
                            0.0
                        ),
                    "triggered_rules":
                        policy_decision.get(
                            "triggered_rules",
                            []
                        ),
                },
            ).to_dict()

        # ----------------------------------------------------
        # FAIL CLOSED
        # ----------------------------------------------------

        return ActionResult(
            action="BLOCK",
            output=(
                "🚫 CONTROLPLANE: "
                "The governance engine returned an "
                "unknown decision. The response was "
                "blocked for safety."
            ),
            modified=False,
            blocked=True,
            review_required=False,
            metadata={
                "reason":
                    "Unknown policy decision",
                "received_decision":
                    decision,
            },
        ).to_dict()

    # ========================================================
    # RESPONSE MODIFICATION
    # ========================================================

    def _modify_response(
        self,
        response: str
    ) -> str:

        """
        Lightweight response sanitization.

        More advanced PII/entity redaction will later be
        connected to the Privacy Agent.
        """

        if not response:
            return ""

        cleaned = response

        # ----------------------------------------------------
        # Basic sensitive-data masking
        # ----------------------------------------------------

        sensitive_markers = [
            "api key:",
            "api_key:",
            "password:",
            "secret:",
            "access token:",
            "access_token:",
        ]

        lines = []

        for line in cleaned.splitlines():

            lower = line.lower()

            if any(
                marker in lower
                for marker in sensitive_markers
            ):

                lines.append(
                    "[REDACTED SENSITIVE INFORMATION]"
                )

            else:

                lines.append(line)

        cleaned = "\n".join(lines)

        return cleaned