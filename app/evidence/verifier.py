from typing import Any, Dict, List
import re

from app.evidence.retriever import EvidenceRetriever


class EvidenceVerifier:
    """
    Evidence-based factuality verifier.

    Retrieval answers:
        "Is there relevant evidence?"

    Verification answers:
        "Does the evidence actually support the claim?"

    This distinction is critical.

    A document can be highly relevant to a claim while
    contradicting the claim.
    """

    VERIFIED_THRESHOLD = 0.65
    PARTIAL_THRESHOLD = 0.25

    def __init__(
        self,
        retriever: EvidenceRetriever
    ):
        self.retriever = retriever

    # ========================================================
    # TEXT NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize(text: str) -> str:

        return re.sub(
            r"[^a-z0-9\s]",
            " ",
            text.lower()
        )

    @classmethod
    def _tokens(cls, text: str):

        return {
            token
            for token in cls._normalize(text).split()
            if len(token) > 2
        }

    # ========================================================
    # CONTRADICTION CHECK
    # ========================================================

    @classmethod
    def _detect_contradiction(
        cls,
        claim: str,
        evidence: str
    ) -> bool:
        """
        Lightweight contradiction detector.

        The prototype uses an important heuristic:

        If a factual statement has the same subject/context
        but the key value differs, the evidence should not be
        considered supporting evidence.

        Example:

            Claim:
                "The capital of India is Mumbai."

            Evidence:
                "The capital of India is New Delhi."

        The evidence is relevant but contradicts the claim.
        """

        claim_tokens = cls._tokens(
            claim
        )

        evidence_tokens = cls._tokens(
            evidence
        )

        # Strong negation signals.
        contradiction_words = {
            "not",
            "never",
            "false",
            "incorrect",
            "wrong",
            "no",
            "cannot"
        }

        if (
            claim_tokens
            & contradiction_words
        ):

            return False

        # ----------------------------------------------------
        # Detect simple "X is Y" statements.
        # ----------------------------------------------------

        claim_match = re.search(
            r"\b(.+?)\s+is\s+(.+?)(?:[.!?]|$)",
            claim.lower()
        )

        evidence_match = re.search(
            r"\b(.+?)\s+is\s+(.+?)(?:[.!?]|$)",
            evidence.lower()
        )

        if not claim_match or not evidence_match:

            return False

        claim_subject = (
            claim_match.group(1).strip()
        )

        claim_value = (
            claim_match.group(2).strip()
        )

        evidence_subject = (
            evidence_match.group(1).strip()
        )

        evidence_value = (
            evidence_match.group(2).strip()
        )

        subject_similarity = (
            cls._tokens(
                claim_subject
            )
            &
            cls._tokens(
                evidence_subject
            )
        )

        if not subject_similarity:

            return False

        claim_value_tokens = cls._tokens(
            claim_value
        )

        evidence_value_tokens = cls._tokens(
            evidence_value
        )

        if not claim_value_tokens:

            return False

        # If the values differ substantially,
        # the evidence is likely contradicting the claim.
        value_overlap = (
            len(
                claim_value_tokens
                &
                evidence_value_tokens
            )
            /
            max(
                len(claim_value_tokens),
                1
            )
        )

        return value_overlap < 0.5

    # ========================================================
    # CLAIM VERIFICATION
    # ========================================================

    def verify_claim(
        self,
        claim: str,
        top_k: int = 3
    ) -> Dict[str, Any]:

        evidence = self.retriever.retrieve(
            claim,
            top_k=top_k
        )

        if not evidence:

            return {
                "claim": claim,
                "status": "NO_EVIDENCE",
                "confidence": 0.0,
                "evidence": []
            }

        evidence_payload = []

        best_support_score = 0.0
        best_contradiction_score = 0.0

        # ----------------------------------------------------
        # Evaluate every retrieved document
        # ----------------------------------------------------

        for item in evidence:

            document = item["document"]

            retrieval_score = float(
                item["score"]
            )

            contradiction = (
                self._detect_contradiction(
                    claim,
                    document.content
                )
            )

            if contradiction:

                best_contradiction_score = max(
                    best_contradiction_score,
                    retrieval_score
                )

                relation = "CONTRADICTS"

            else:

                best_support_score = max(
                    best_support_score,
                    retrieval_score
                )

                relation = "SUPPORTS"

            evidence_payload.append(
                {
                    "document_id":
                        document.document_id,

                    "title":
                        document.title,

                    "source":
                        document.source,

                    "score":
                        round(
                            retrieval_score,
                            4
                        ),

                    "method":
                        item["method"],

                    "relation":
                        relation
                }
            )

        # ====================================================
        # FINAL DECISION
        # ====================================================

        # Contradictory evidence wins over generic relevance.
        if (
            best_contradiction_score
            >=
            self.VERIFIED_THRESHOLD
        ):

            return {
                "claim": claim,
                "status": "UNSUPPORTED",
                "confidence": round(
                    best_contradiction_score,
                    4
                ),
                "evidence":
                    evidence_payload
            }

        # Strong supporting evidence.
        if (
            best_support_score
            >=
            self.VERIFIED_THRESHOLD
        ):

            return {
                "claim": claim,
                "status": "VERIFIED",
                "confidence": round(
                    best_support_score,
                    4
                ),
                "evidence":
                    evidence_payload
            }

        # Some evidence exists, but it is not strong enough.
        if (
            best_support_score
            >=
            self.PARTIAL_THRESHOLD
        ):

            return {
                "claim": claim,
                "status": "PARTIAL",
                "confidence": round(
                    best_support_score,
                    4
                ),
                "evidence":
                    evidence_payload
            }

        return {
            "claim": claim,
            "status": "UNSUPPORTED",
            "confidence": round(
                best_support_score,
                4
            ),
            "evidence":
                evidence_payload
        }

    # ========================================================
    # MULTI-CLAIM VERIFICATION
    # ========================================================

    def verify_claims(
        self,
        claims: List[Any]
    ) -> Dict[str, Any]:

        if not claims:

            return {
                "status": "NO_CLAIMS",
                "confidence": 1.0,
                "claims": [],
                "summary": {
                    "verified": 0,
                    "partial": 0,
                    "unsupported": 0,
                    "no_evidence": 0
                }
            }

        results = []

        for claim in claims:

            if isinstance(
                claim,
                dict
            ):

                claim_text = str(
                    claim.get(
                        "text",
                        ""
                    )
                )

            else:

                claim_text = str(
                    claim
                )

            results.append(
                self.verify_claim(
                    claim_text
                )
            )

        verified = sum(
            r["status"] == "VERIFIED"
            for r in results
        )

        partial = sum(
            r["status"] == "PARTIAL"
            for r in results
        )

        unsupported = sum(
            r["status"] == "UNSUPPORTED"
            for r in results
        )

        no_evidence = sum(
            r["status"] == "NO_EVIDENCE"
            for r in results
        )

        total = len(results)

        verified_ratio = (
            verified / total
            if total
            else 0.0
        )

        if verified == total:

            overall_status = "VERIFIED"

        elif verified > 0 or partial > 0:

            overall_status = "PARTIAL"

        elif no_evidence == total:

            overall_status = "NO_EVIDENCE"

        else:

            overall_status = "UNSUPPORTED"

        return {
            "status":
                overall_status,

            "confidence":
                round(
                    verified_ratio,
                    4
                ),

            "claims":
                results,

            "summary": {
                "verified":
                    verified,

                "partial":
                    partial,

                "unsupported":
                    unsupported,

                "no_evidence":
                    no_evidence
            }
        }


# ============================================================
# COMPATIBILITY API
# ============================================================

def verify_claims(
    claims,
    evidence=None,
    embedder=None
):
    """
    Compatibility function for the existing
    FactualityAgent / previous prototype.
    """

    from app.evidence.store import (
        EvidenceDocument,
        EvidenceStore
    )

    if evidence is None:

        evidence = []

    documents = []

    for index, item in enumerate(
        evidence
    ):

        if isinstance(
            item,
            EvidenceDocument
        ):

            documents.append(item)

        elif isinstance(
            item,
            dict
        ):

            documents.append(
                EvidenceDocument(
                    document_id=str(
                        item.get(
                            "id",
                            f"evidence_{index}"
                        )
                    ),

                    title=str(
                        item.get(
                            "title",
                            f"Evidence {index + 1}"
                        )
                    ),

                    content=str(
                        item.get(
                            "content",
                            item.get(
                                "text",
                                ""
                            )
                        )
                    ),

                    source=str(
                        item.get(
                            "source",
                            "internal"
                        )
                    ),

                    metadata=item.get(
                        "metadata",
                        {}
                    )
                )
            )

        else:

            documents.append(
                EvidenceDocument(
                    document_id=
                        f"evidence_{index}",

                    title=
                        f"Evidence {index + 1}",

                    content=
                        str(item)
                )
            )

    store = EvidenceStore(
        documents
    )

    retriever = EvidenceRetriever(
        store,
        embedder=embedder
    )

    verifier = EvidenceVerifier(
        retriever
    )

    return verifier.verify_claims(
        claims
    )