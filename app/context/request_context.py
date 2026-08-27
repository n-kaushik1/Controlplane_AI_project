from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.context.risk_profiles import (
    RiskProfile,
    get_risk_profile
)


@dataclass
class RequestContext:

    request_id: str

    prompt: str

    use_case: str

    risk_profile: RiskProfile

    created_at: str

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    conversation_id: Optional[str] = None

    user_id: Optional[str] = None

    turn_number: int = 1

    def to_dict(self) -> Dict[str, Any]:

        return {
            "request_id": self.request_id,

            "prompt": self.prompt,

            "use_case": self.use_case,

            "risk_profile": self.risk_profile.name,

            "created_at": self.created_at,

            "conversation_id": self.conversation_id,

            "user_id": self.user_id,

            "turn_number": self.turn_number,

            "metadata": self.metadata
        }


def create_request_context(
    prompt: str,
    use_case: str = "customer_support",
    metadata: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    turn_number: int = 1
) -> RequestContext:

    if not prompt or not prompt.strip():

        raise ValueError(
            "Prompt cannot be empty."
        )

    profile = get_risk_profile(
        use_case
    )

    return RequestContext(

        request_id=str(
            uuid4()
        ),

        prompt=prompt,

        use_case=profile.name,

        risk_profile=profile,

        created_at=datetime.now(
            timezone.utc
        ).isoformat(),

        metadata=metadata or {},

        conversation_id=conversation_id,

        user_id=user_id,

        turn_number=turn_number
    )