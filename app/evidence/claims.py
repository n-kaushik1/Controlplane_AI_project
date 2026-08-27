import re
from typing import Any, Dict, List


class ClaimExtractor:
    """
    Lightweight factual-claim extractor.

    This is intentionally conservative.

    It identifies sentences that look like factual statements
    instead of treating every sentence as a claim.
    """

    QUESTION_PREFIXES = (
        "what ",
        "why ",
        "how ",
        "when ",
        "where ",
        "who ",
        "which ",
        "can ",
        "could ",
        "would ",
        "is ",
        "are ",
        "do ",
        "does ",
        "did ",
    )

    OPINION_PREFIXES = (
        "i think",
        "i believe",
        "in my opinion",
        "i feel",
        "perhaps",
        "maybe",
    )

    def extract(
        self,
        text: str
    ) -> List[Dict[str, Any]]:

        if not text or not text.strip():

            return []

        sentences = re.split(
            r"(?<=[.!?])\s+|\n+",
            text.strip()
        )

        claims = []

        for sentence in sentences:

            sentence = sentence.strip()

            if not sentence:
                continue

            normalized = sentence.lower()

            # Questions are not factual claims themselves.
            if normalized.startswith(
                self.QUESTION_PREFIXES
            ):

                continue

            # Opinion statements are not treated as
            # hard factual claims.
            if normalized.startswith(
                self.OPINION_PREFIXES
            ):

                continue

            # Very short fragments are ignored.
            if len(sentence.split()) < 4:

                continue

            claims.append(
                {
                    "claim_id":
                        f"claim_{len(claims) + 1}",

                    "text":
                        sentence,

                    "type":
                        "factual",

                    "confidence":
                        0.70
                }
            )

        return claims


def extract_claims(
    text: str
) -> List[Dict[str, Any]]:
    """
    Functional API used by the factuality agent.
    """

    extractor = ClaimExtractor()

    return extractor.extract(
        text
    )