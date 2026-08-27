import re
import time

from app.agents.base import AgentResult


class SecurityAgent:

    name = "security"

    PATTERNS = [

        # ====================================================
        # PROMPT INJECTION
        # ====================================================

        r"ignore\s+(all\s+)?previous\s+instructions",

        r"ignore\s+the\s+system\s+prompt",

        r"disregard\s+(all\s+)?previous",

        r"reveal\s+(the\s+)?system\s+prompt",

        r"show\s+(me\s+)?your\s+hidden\s+instructions",

        r"developer\s+message",

        r"jailbreak",

        r"bypass\s+(the\s+)?safety",

        r"bypass\s+(the\s+)?policy",

        r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",

        r"forget\s+your\s+instructions",

        r"override\s+(your\s+)?instructions",

        # ====================================================
        # CREDENTIAL / PASSWORD THEFT
        # ====================================================

        r"steal\s+(someone'?s\s+)?password",

        r"steal\s+(a\s+)?password",

        r"hack\s+(someone'?s\s+)?password",

        r"crack\s+(someone'?s\s+)?password",

        r"obtain\s+(someone'?s\s+)?password",

        r"get\s+(someone'?s\s+)?password",

        r"find\s+(someone'?s\s+)?password",

        r"retrieve\s+(someone'?s\s+)?password",

        r"capture\s+(someone'?s\s+)?password",

        r"keylog\s+(someone'?s\s+)?password",

        r"phish\s+(for\s+)?(someone'?s\s+)?password",

        r"phishing\s+(for\s+)?(someone'?s\s+)?password",

        r"bypass\s+(a\s+)?password",

        r"bypass\s+(password\s+)?authentication",

        r"access\s+(someone'?s\s+)?account\s+without\s+permission",

        r"access\s+(someone'?s\s+)?account\s+without\s+authorization",

        # ====================================================
        # SECRET / API KEY / CREDENTIAL EXTRACTION
        # ====================================================

        r"steal\s+(an?\s+)?api\s+key",

        r"steal\s+(the\s+)?api\s+key",

        r"extract\s+(an?\s+)?api\s+key",

        r"reveal\s+(an?\s+)?api\s+key",

        r"get\s+(the\s+)?api\s+key",

        r"obtain\s+(an?\s+)?api\s+key",

        r"steal\s+(someone'?s\s+)?credentials",

        r"obtain\s+(someone'?s\s+)?credentials",

        r"steal\s+(someone'?s\s+)?login",

        r"steal\s+(someone'?s\s+)?login\s+credentials",
    ]

    def scan(self, text: str) -> AgentResult:

        started = time.perf_counter()

        text_lower = text.lower()

        matches = []

        for pattern in self.PATTERNS:

            if re.search(
                pattern,
                text_lower
            ):
                matches.append(pattern)

        if len(matches) >= 2:

            risk = 0.98
            status = "BLOCK"

        elif len(matches) == 1:

            risk = 0.85
            status = "BLOCK"

        else:

            risk = 0.02
            status = "PASS"

        latency = (
            time.perf_counter()
            - started
        ) * 1000

        return AgentResult(

            agent=self.name,

            risk=risk,

            status=status,

            reason=(
                "Security-risk indicators detected."
                if matches
                else
                "No obvious security-risk pattern detected."
            ),

            confidence=0.92,

            signals={
                "matches": len(matches),
                "patterns": matches
            },

            latency_ms=latency
        )