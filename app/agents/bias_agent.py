import re
import time

from app.agents.base import AgentResult


class BiasAgent:

    name = "bias"

    GROUP_PATTERNS = [

        r"\b(women|men)\s+are\s+(naturally|inherently|always|usually)",

        r"\b(all|most)\s+(women|men)\s+are",

        r"\b(all|most)\s+(muslims|christians|hindus|jews)\s+are",

        r"\b(all|most)\s+(immigrants|foreigners)\s+are",

        r"\b(people\s+from|people\s+of)\s+\w+\s+are",

        r"\b(black|white|asian|indian)\s+people\s+are\s+(naturally|inherently)",

        r"\b(old|young)\s+people\s+are\s+(bad|lazy|stupid|incompetent)"
    ]

    def scan(self, text: str) -> AgentResult:

        started = time.perf_counter()

        matches = []

        for pattern in self.GROUP_PATTERNS:

            if re.search(
                pattern,
                text.lower()
            ):
                matches.append(pattern)

        if matches:

            risk = min(
                0.95,
                0.70 + 0.08 * len(matches)
            )

            status = "REVIEW"

            reason = (
                "Potential group-based generalization or "
                "stereotyping detected."
            )

        else:

            risk = 0.02
            status = "PASS"

            reason = (
                "No obvious group-based bias pattern detected."
            )

        latency = (
            time.perf_counter()
            - started
        ) * 1000

        return AgentResult(

            agent=self.name,

            risk=risk,

            status=status,

            reason=reason,

            confidence=0.82,

            signals={
                "matches": len(matches)
            },

            latency_ms=latency
        )