import re
import time

from app.agents.base import AgentResult


class BiasAgent:

    name = "bias"

    # ------------------------------------------------------------------
    # Vocabulary
    # ------------------------------------------------------------------

    _GROUPS = (
        r"women|men|girls|boys|females|males|"
        r"muslims|christians|hindus|jews|sikhs|buddhists|atheists|"
        r"immigrants|foreigners|refugees|"
        r"(?:black|white|asian|indian|latino|hispanic|arab|african|"
        r"gay|lesbian|trans|transgender|disabled|elderly|old|young|"
        r"poor|rich)\s+(?:people|folks|men|women)"
    )

    # Traits that make a group comparison a stereotype.
    _NEGATIVE_TRAITS = (
        r"worse|inferior|dumber|weaker|lazier|"
        r"less\s+(?:intelligent|capable|competent|suited|qualified|"
        r"rational|trustworthy|productive)|"
        r"better\s+(?:at|than)|"
        r"lazy|stupid|dumb|incompetent|criminals?|violent|dangerous|"
        r"untrustworthy|unfit|emotional|irrational"
    )

    # ------------------------------------------------------------------
    # Group stereotyping
    # ------------------------------------------------------------------

    GROUP_PATTERNS = [

        r"\b(women|men)\s+are\s+(naturally|inherently|always|usually)",

        r"\b(all|most)\s+(women|men)\s+are",

        r"\b(all|most)\s+(muslims|christians|hindus|jews)\s+are",

        r"\b(all|most)\s+(immigrants|foreigners)\s+are",

        r"\b(people\s+from|people\s+of)\s+\w+\s+are",

        r"\b(black|white|asian|indian)\s+people\s+are\s+(naturally|inherently)",

        r"\b(old|young)\s+people\s+are\s+(bad|lazy|stupid|incompetent)",

        # "<group> are/is worse at ..." / "<group> are lazy"
        rf"\b(?:{_GROUPS})\s+(?:are|is)\s+(?:(?!not\b|never\b)\w+\s+)?"
        rf"(?:{_NEGATIVE_TRAITS})\b",

        # "why are <group> worse ...", "explain why <group> are ..."
        rf"\bwhy\s+(?:are|do|is|does|can't|cannot)\s+(?:{_GROUPS})\b"
        rf".{{0,40}}\b(?:{_NEGATIVE_TRAITS})\b",

        rf"\bexplain\s+why\s+(?:{_GROUPS})\s+(?:are|is)\b"
        rf".{{0,40}}\b(?:{_NEGATIVE_TRAITS})\b",
    ]

    # A sentence that debunks or discusses a stereotype is not itself
    # a stereotype, so it should not be escalated.
    _DEBUNKING = re.compile(
        r"\b(myth|stereotype|stereotypes|misconception|untrue|false|"
        r"not\s+true|no\s+evidence|incorrect|prejudice|biased|bias|"
        r"offensive|harmful|inaccurate|baseless|unfounded|"
        r"can(?:'|no)t\s+help|won't\s+(?:say|claim))\b",
        re.IGNORECASE,
    )

    # ------------------------------------------------------------------
    # Protected attributes used in consequential decisions
    # ------------------------------------------------------------------

    # Text that explains why such decisions are wrong or unlawful
    # (typically a model response) is informational, not a decision.
    _DECISION_SAFE = re.compile(
        r"\b(illegal|unlawful|prohibited|not\s+allowed|discriminat\w*|"
        r"fair\s+lending|equal\s+credit|equal\s+opportunity|"
        r"protected\s+class|can(?:'|no)t\s+help|"
        r"myth|stereotype|bias|biased|harmful)\b",
        re.IGNORECASE,
    )

    _DECISION_VERBS = (
        r"deny|reject|decline|approve|hire|fire|dismiss|terminate|"
        r"promote|demote|shortlist|screen\s+out|rank|"
        r"evict|insure|underwrite|sentence"
    )

    _DECISION_CONTEXT = (
        r"loan|mortgage|credit|insurance|application|applicant|"
        r"candidate|employee|tenant|patient|claim|visa|benefits|"
        r"scholarship|admission|"
        r"him|her|them|this\s+(?:person|man|woman|guy|individual)"
    )

    _PROTECTED_ATTRIBUTES = (
        r"\b\d{1,3}[\s-]*years?[\s-]*old\b|"
        r"\bage\b|\bgender\b|\brace\b|\bracial\b|\bethnicity\b|"
        r"\breligion\b|\breligious\b|\bnationality\b|\bdisabilit(?:y|ies)\b|"
        r"\bpregnan(?:t|cy)\b|\bmarital\s+status\b|\bsexual\s+orientation\b|"
        r"\b(?:poor|rich|low-income)\s+(?:neighbou?rhood|area|zip\s*code)\b|"
        r"\bneighbou?rhood\b|\bzip\s*code\b|\bpostcode\b|"
        rf"\b(?:{_GROUPS})\b"
    )

    PROTECTED_DECISION_PATTERN = (
        rf"\b(?:{_DECISION_VERBS})\b.{{0,80}}\b(?:{_DECISION_CONTEXT})\b|"
        rf"\b(?:{_DECISION_CONTEXT})\b.{{0,80}}\b(?:{_DECISION_VERBS})\b"
    )

    # Findings are escalated to human review rather than blocked
    # outright, so their risk stays below the strictest block
    # thresholds of the lenient profiles.
    STEREOTYPE_BASE_RISK = 0.70

    STEREOTYPE_MAX_RISK = 0.78

    PROTECTED_DECISION_RISK = 0.45

    # ------------------------------------------------------------------

    @classmethod
    def _sentences(cls, text: str):

        return [
            part
            for part in re.split(r"(?<=[.!?\n])\s+", text)
            if part.strip()
        ]

    def _stereotype_matches(self, text: str):

        matches = []

        for sentence in self._sentences(text):

            lowered = sentence.lower()

            if self._DEBUNKING.search(lowered):
                continue

            for pattern in self.GROUP_PATTERNS:

                if re.search(pattern, lowered) and pattern not in matches:
                    matches.append(pattern)

        return matches

    def _protected_decision(self, text: str) -> bool:

        # Evaluated over the whole text: the decision ("should we
        # deny this application?") and the attribute ("they are 62")
        # are often in different sentences.
        lowered = text.lower()

        if self._DECISION_SAFE.search(lowered):
            return False

        return bool(
            re.search(self.PROTECTED_DECISION_PATTERN, lowered)
            and re.search(self._PROTECTED_ATTRIBUTES, lowered)
        )

    def scan(self, text: str) -> AgentResult:

        started = time.perf_counter()

        matches = self._stereotype_matches(text)

        protected_decision = self._protected_decision(text)

        if matches:

            risk = min(
                self.STEREOTYPE_MAX_RISK,
                self.STEREOTYPE_BASE_RISK + 0.08 * len(matches)
            )

            status = "REVIEW"

            reason = (
                "Potential group-based generalization or "
                "stereotyping detected."
            )

        elif protected_decision:

            risk = self.PROTECTED_DECISION_RISK

            status = "REVIEW"

            reason = (
                "A decision about a person references a "
                "protected or proxy attribute (e.g. age, "
                "gender, neighbourhood); human review is "
                "required to avoid discriminatory outcomes."
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
                "matches": len(matches),
                "protected_attribute_decision": protected_decision,
            },

            latency_ms=latency
        )
