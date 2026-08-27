from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ReviewItem:

    review_id: str

    request_id: str

    prompt: str

    model_response: str = ""

    decision: str = "REVIEW"

    risk_score: float = 0.0

    reason: str = ""

    status: str = "PENDING"

    reviewer: Optional[str] = None

    reviewer_comment: str = ""

    final_decision: Optional[str] = None

    created_at: str = field(
        default_factory=lambda:
        datetime.now(timezone.utc).isoformat()
    )

    reviewed_at: Optional[str] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "review_id": self.review_id,
            "request_id": self.request_id,
            "prompt": self.prompt,
            "model_response": self.model_response,
            "decision": self.decision,
            "risk_score": round(
                float(self.risk_score),
                4
            ),
            "reason": self.reason,
            "status": self.status,
            "reviewer": self.reviewer,
            "reviewer_comment": (
                self.reviewer_comment
            ),
            "final_decision": self.final_decision,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any]
    ) -> "ReviewItem":

        return cls(
            review_id=data["review_id"],
            request_id=data["request_id"],
            prompt=data.get("prompt", ""),
            model_response=data.get(
                "model_response",
                ""
            ),
            decision=data.get(
                "decision",
                "REVIEW"
            ),
            risk_score=float(
                data.get("risk_score", 0.0)
            ),
            reason=data.get(
                "reason",
                ""
            ),
            status=data.get(
                "status",
                "PENDING"
            ),
            reviewer=data.get(
                "reviewer"
            ),
            reviewer_comment=data.get(
                "reviewer_comment",
                ""
            ),
            final_decision=data.get(
                "final_decision"
            ),
            created_at=data.get(
                "created_at",
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            reviewed_at=data.get(
                "reviewed_at"
            ),
            metadata=data.get(
                "metadata",
                {}
            ),
        )