import time

from app.agents.base import AgentResult


class CostAgent:

    name = "cost"

    def __init__(
        self,
        max_output_tokens=1000,
        max_prompt_tokens=4000
    ):

        self.max_output_tokens = (
            max_output_tokens
        )

        self.max_prompt_tokens = (
            max_prompt_tokens
        )

    def scan(
        self,
        prompt: str,
        estimated_output_tokens: int = 0
    ) -> AgentResult:

        started = time.perf_counter()

        input_tokens = max(
            1,
            len(prompt.split())
        )

        signals = {
            "input_tokens": input_tokens,
            "estimated_output_tokens":
                estimated_output_tokens
        }

        if input_tokens > self.max_prompt_tokens:

            risk = 0.90
            status = "BLOCK"
            reason = (
                "Prompt exceeds configured compute budget."
            )

        elif (
            estimated_output_tokens
            > self.max_output_tokens
        ):

            risk = 0.75
            status = "REVIEW"
            reason = (
                "Estimated generation exceeds output budget."
            )

        else:

            risk = min(
                0.50,
                input_tokens
                /
                self.max_prompt_tokens
                *
                0.5
            )

            status = "PASS"

            reason = (
                "Request is within configured compute limits."
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

            confidence=0.95,

            signals=signals,

            latency_ms=latency
        )