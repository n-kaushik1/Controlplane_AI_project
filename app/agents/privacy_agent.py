import re
import time

from app.agents.base import AgentResult


class PrivacyAgent:

    name = "privacy"

    PATTERNS = {

        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",

        "phone": r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b",

        "credit_card": r"\b(?:\d[ -]*?){13,19}\b",

        "api_key": (
            r"\b(?:api[_-]?key|secret|token)"
            r"\s*[:=]\s*[A-Za-z0-9_\-]{12,}"
        ),

        "password": (
            r"\bpassword\s*[:=]\s*\S+"
        ),

        "ssn": (
            r"\b\d{3}-\d{2}-\d{4}\b"
        )
    }

    def scan(self, text: str) -> AgentResult:

        started = time.perf_counter()

        matches = {}

        for name, pattern in self.PATTERNS.items():

            found = re.findall(
                pattern,
                text,
                flags=re.IGNORECASE
            )

            if found:
                matches[name] = len(found)

        if not matches:

            risk = 0.01
            status = "PASS"

        elif "credit_card" in matches:

            risk = 0.99
            status = "BLOCK"

        elif (
            "password" in matches
            or
            "api_key" in matches
        ):

            risk = 0.98
            status = "BLOCK"

        else:

            risk = min(
                0.95,
                0.55 + (
                    0.10 * len(matches)
                )
            )

            status = "MODIFY"

        latency = (
            time.perf_counter()
            - started
        ) * 1000

        return AgentResult(

            agent=self.name,

            risk=risk,

            status=status,

            reason=(
                "Sensitive information detected."
                if matches
                else
                "No obvious sensitive information detected."
            ),

            confidence=0.96,

            signals={
                "types": matches
            },

            latency_ms=latency
        )