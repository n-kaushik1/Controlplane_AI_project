from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentResult:

    agent: str

    risk: float = 0.0

    status: str = "PASS"

    reason: str = ""

    confidence: float = 1.0

    signals: Dict[str, Any] = field(
        default_factory=dict
    )

    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:

        return {
            "agent": self.agent,
            "risk": round(float(self.risk), 4),
            "status": self.status,
            "reason": self.reason,
            "confidence": round(
                float(self.confidence),
                4
            ),
            "signals": self.signals,
            "latency_ms": round(
                float(self.latency_ms),
                3
            )
        }