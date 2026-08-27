import time
from typing import Any, Dict

from app.agents.base import AgentResult


class FactualityAgent:
    """
    ControlPlane.ai Factuality Governance Agent.

    Responsibilities:
        1. Extract claims from a model response.
        2. Ask FactualityEngine to verify those claims.
        3. Convert factuality results into a governance status.
        4. Preserve the complete factuality result for:
           - governance inspection
           - audit logging
           - monitoring
           - debugging

    IMPORTANT:

        The FactualityAgent does NOT perform web retrieval itself.

        FactualityEngine remains responsible for:

            LOCAL EVIDENCE
                  |
             UNKNOWN ONLY
                  |
             TAVILY FALLBACK
                  |
          ranking + claim support
                  |
              verification

        This keeps factuality retrieval and governance
        decisions properly separated.
    """

    name = "factuality"

    # ============================================================
    # GOVERNANCE THRESHOLDS
    # ============================================================

    VERIFIED_RISK = 0.05

    REVIEW_RISK = 0.60

    FAILED_RISK = 0.90

    UNKNOWN_CONFIDENCE = 0.20

    REVIEW_CONFIDENCE = 0.55

    VERIFIED_CONFIDENCE = 0.90

    # ============================================================
    # CONSTRUCTOR
    # ============================================================

    def __init__(
        self,
        claim_extractor=None,
        verifier=None,
        evidence=None,
    ):

        self.claim_extractor = claim_extractor

        self.verifier = verifier

        self.evidence = evidence

    # ============================================================
    # PUBLIC SCAN
    # ============================================================

    def scan(
        self,
        text: str,
    ) -> AgentResult:

        started = time.perf_counter()

        # --------------------------------------------------------
        # ENGINE NOT CONFIGURED
        # --------------------------------------------------------

        if (
            self.claim_extractor is None
            or self.verifier is None
        ):

            latency = (
                time.perf_counter()
                - started
            ) * 1000

            verification = {
                "status": "NOT_CONFIGURED",
                "claims": [],
                "verified_count": 0,
                "failed_count": 0,
                "unknown_count": 0,
                "details": [],
                "verification_counts": {
                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,
                },
            }

            return AgentResult(
                agent=self.name,
                risk=self.REVIEW_RISK,
                status="REVIEW",
                reason=(
                    "Factuality engine is not "
                    "configured."
                ),
                confidence=self.UNKNOWN_CONFIDENCE,
                signals={
                    "claims": 0,
                    "verification": verification,
                    "factuality_status": "NOT_CONFIGURED",
                    "verification_source": "UNKNOWN",
                    "verified_count": 0,
                    "failed_count": 0,
                    "unknown_count": 0,
                    "evidence_count": 0,
                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,
                    "web_fallback_used": False,
                    "details": [],
                    "verification_counts": verification[
                        "verification_counts"
                    ],
                    "web_fallback": {},
                    "latency_ms": latency,
                },
                latency_ms=latency,
            )

        # --------------------------------------------------------
        # INPUT NORMALIZATION
        # --------------------------------------------------------

        if text is None:
            text = ""

        if not isinstance(
            text,
            str,
        ):
            text = str(text)

        # --------------------------------------------------------
        # CLAIM EXTRACTION
        # --------------------------------------------------------

        try:

            claims = self._extract_claims(text)

        except Exception as exc:

            latency = (
                time.perf_counter()
                - started
            ) * 1000

            verification = {
                "status": "UNKNOWN",
                "claims": [],
                "verified_count": 0,
                "failed_count": 0,
                "unknown_count": 0,
                "details": [],
                "error": str(exc),
            }

            return AgentResult(
                agent=self.name,
                risk=self.REVIEW_RISK,
                status="REVIEW",
                reason=(
                    "Factuality claim extraction "
                    "failed safely."
                ),
                confidence=self.UNKNOWN_CONFIDENCE,
                signals={
                    "claims": 0,
                    "verification": verification,
                    "factuality_status": "UNKNOWN",
                    "verification_source": "UNKNOWN",
                    "verified_count": 0,
                    "failed_count": 0,
                    "unknown_count": 0,
                    "evidence_count": 0,
                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,
                    "web_fallback_used": False,
                    "details": [],
                    "error": str(exc),
                    "latency_ms": latency,
                },
                latency_ms=latency,
            )

        # --------------------------------------------------------
        # NORMALIZE CLAIM COUNT
        # --------------------------------------------------------

        claim_count = self._claim_count(claims)

        # --------------------------------------------------------
        # NO CLAIMS
        #
        # This is not a factuality failure.
        # It simply means there was nothing factual
        # to verify.
        # --------------------------------------------------------

        if claim_count == 0:

            latency = (
                time.perf_counter()
                - started
            ) * 1000

            verification = {
                "status": "NO_CLAIMS",
                "claims": self._normalize_claims(claims),
                "verified_count": 0,
                "failed_count": 0,
                "unknown_count": 0,
                "evidence_count": 0,
                "details": [],
                "verification_counts": {
                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,
                },
                "web_fallback": {
                    "enabled": True,
                    "used": False,
                },
                "latency_ms": 0.0,
            }

            return AgentResult(
                agent=self.name,
                risk=self.VERIFIED_RISK,
                status="PASS",
                reason=(
                    "No factual claims were "
                    "identified."
                ),
                confidence=self.VERIFIED_CONFIDENCE,
                signals={
                    "claims": 0,

                    # Complete verification object.
                    "verification": verification,

                    # Explicit flattened fields for
                    # monitoring / metrics / audit.
                    "factuality_status": "NO_CLAIMS",
                    "status": "NO_CLAIMS",
                    "verification_source": "NONE",

                    "verified_count": 0,
                    "failed_count": 0,
                    "unknown_count": 0,
                    "evidence_count": 0,

                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,

                    "web_fallback_used": False,

                    "verification_counts": verification[
                        "verification_counts"
                    ],

                    "web_fallback": verification[
                        "web_fallback"
                    ],

                    "details": [],

                    "verification_latency_ms": 0.0,
                    "latency_ms": latency,
                },
                latency_ms=latency,
            )

        # --------------------------------------------------------
        # CLAIM VERIFICATION
        # --------------------------------------------------------

        try:

            verification = self._verify_claims(
                claims
            )

        except Exception as exc:

            latency = (
                time.perf_counter()
                - started
            ) * 1000

            verification = {
                "status": "UNKNOWN",
                "claims": self._normalize_claims(claims),
                "verified_count": 0,
                "failed_count": 0,
                "unknown_count": claim_count,
                "evidence_count": 0,
                "details": [],
                "verification_counts": {
                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,
                },
                "web_fallback": {
                    "enabled": True,
                    "used": False,
                },
                "error": str(exc),
            }

            return AgentResult(
                agent=self.name,
                risk=self.REVIEW_RISK,
                status="REVIEW",
                reason=(
                    "Factuality verification "
                    "failed safely."
                ),
                confidence=self.UNKNOWN_CONFIDENCE,
                signals={
                    "claims": claim_count,
                    "verification": verification,

                    "factuality_status": "UNKNOWN",
                    "status": "UNKNOWN",
                    "verification_source": "UNKNOWN",

                    "verified_count": 0,
                    "failed_count": 0,
                    "unknown_count": claim_count,
                    "evidence_count": 0,

                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,

                    "web_fallback_used": False,

                    "verification_counts": verification[
                        "verification_counts"
                    ],

                    "web_fallback": verification[
                        "web_fallback"
                    ],

                    "details": [],

                    "error": str(exc),
                    "latency_ms": latency,
                },
                latency_ms=latency,
            )

        # --------------------------------------------------------
        # NORMALIZE VERIFICATION RESULT
        # --------------------------------------------------------

        verification = self._normalize_verification(
            verification,
            claims,
        )

        status = self._verification_status(
            verification
        )

        # --------------------------------------------------------
        # EXTRACT SUMMARY SIGNALS
        # --------------------------------------------------------

        summary = self._verification_summary(
            verification
        )

        verification_source = (
            self._verification_source(
                verification
            )
        )

        # --------------------------------------------------------
        # GOVERNANCE MAPPING
        #
        # VERIFIED / SUPPORTED
        #     -> PASS
        #
        # FAILED
        #     -> REVIEW
        #
        # PARTIAL / UNKNOWN
        #     -> REVIEW
        #
        # A factual contradiction is sent to human review.
        # The factuality engine still reports FAILED.
        # --------------------------------------------------------

        if status in {
            "VERIFIED",
            "SUPPORTED",
            "PASS",
            "CONFIRMED",
        }:

            agent_status = "PASS"

            risk = self.VERIFIED_RISK

            confidence = (
                self._verified_confidence(
                    verification
                )
            )

            reason = (
                "Factuality verification "
                "established the response claims."
            )

        elif status == "FAILED":

            # ----------------------------------------------------
            # FAILED factuality results go to REVIEW rather
            # than directly becoming BLOCK.
            #
            # Existing FAILED_RISK is preserved.
            # ----------------------------------------------------

            agent_status = "REVIEW"

            risk = self.FAILED_RISK

            confidence = (
                self._failed_confidence(
                    verification
                )
            )

            reason = (
                "Factuality verification "
                "found a contradicted or failed "
                "claim; human review is required."
            )

        elif status in {
            "PARTIAL",
            "UNCERTAIN",
            "LOW_CONFIDENCE",
        }:

            agent_status = "REVIEW"

            risk = self.REVIEW_RISK

            confidence = self.REVIEW_CONFIDENCE

            reason = (
                "Factuality verification was "
                "inconclusive or only partially "
                "established the claims."
            )

        elif status == "NO_CLAIMS":

            agent_status = "PASS"

            risk = self.VERIFIED_RISK

            confidence = self.VERIFIED_CONFIDENCE

            reason = (
                "No factual claims required "
                "verification."
            )

        else:

            # ----------------------------------------------------
            # UNKNOWN does not automatically mean HUMAN REVIEW.
            #
            # An evidence store is necessarily incomplete. A normal
            # low-risk answer that is simply absent from the local
            # corpus must not make the entire product unusable.
            #
            # Explicit contradictions remain REVIEW above. Unknown
            # claims in high-impact domains remain REVIEW below.
            # Other unknown claims are allowed with a low risk score
            # while the complete UNKNOWN factuality result is retained
            # in signals/audit for observability.
            # ----------------------------------------------------

            claims_for_risk = self._normalize_claims(
                verification.get("claims", claims)
                if isinstance(verification, dict)
                else claims
            )

            if self._contains_high_impact_claim(claims_for_risk):

                agent_status = "REVIEW"

                risk = self.REVIEW_RISK

                confidence = self.UNKNOWN_CONFIDENCE

                reason = (
                    "Factuality could not establish a "
                    "high-impact claim with sufficient "
                    "evidence; human review is required."
                )

            else:

                agent_status = "PASS"

                risk = 0.10

                confidence = 0.65

                reason = (
                    "Factuality evidence was inconclusive, "
                    "but no explicit contradiction or high-impact "
                    "claim was detected. The response is allowed "
                    "with factuality uncertainty retained for audit "
                    "and monitoring."
                )

        # --------------------------------------------------------
        # LATENCY
        # --------------------------------------------------------

        latency = (
            time.perf_counter()
            - started
        ) * 1000

        # --------------------------------------------------------
        # GOVERNANCE SIGNALS
        #
        # IMPORTANT:
        #
        # The COMPLETE engine verification result is preserved.
        #
        # Additionally, the important fields are flattened into
        # signals so metrics/audit/governance consumers do not
        # have to depend on one exact nested structure.
        # --------------------------------------------------------

        signals = {

            # Core claim information
            "claims": claim_count,

            # Complete engine result
            "verification": verification,

            # Primary status
            "factuality_status": status,
            "status": status,

            # Source
            "verification_source": (
                verification_source
            ),

            # Summary counters
            "verified_count": (
                summary["verified_count"]
            ),

            "failed_count": (
                summary["failed_count"]
            ),

            "unknown_count": (
                summary["unknown_count"]
            ),

            "evidence_count": (
                summary["evidence_count"]
            ),

            # Local / web counters
            "local_verified": (
                summary["local_verified"]
            ),

            "local_failed": (
                summary["local_failed"]
            ),

            "web_verified": (
                summary["web_verified"]
            ),

            "web_fallback_used": (
                summary["web_fallback_used"]
            ),

            # Preserve engine metadata
            "verification_counts": (
                summary["verification_counts"]
            ),

            "web_fallback": (
                summary["web_fallback"]
            ),

            "details": (
                summary["details"]
            ),

            "verification_latency_ms": (
                self._safe_float(
                    verification.get(
                        "latency_ms",
                        0.0,
                    )
                )
            ),

            "latency_ms": latency,
        }

        # --------------------------------------------------------
        # RETURN STANDARD AGENT RESULT
        # --------------------------------------------------------

        return AgentResult(
            agent=self.name,
            risk=risk,
            status=agent_status,
            reason=reason,
            confidence=confidence,
            signals=signals,
            latency_ms=latency,
        )

    # ============================================================
    # HIGH-IMPACT UNKNOWN CLAIM DETECTION
    # ============================================================

    @staticmethod
    def _contains_high_impact_claim(
        claims: list,
    ) -> bool:
        """
        Return True when an unverified claim concerns a domain where
        uncertainty should still trigger human review.

        This keeps ordinary conversation and everyday low-risk facts
        flowing while preserving a conservative control for medical,
        legal, financial, safety and similarly consequential topics.
        """

        if not claims:
            return False

        high_impact_terms = (
            # Medical / health
            "medical", "medicine", "medication", "drug", "dose",
            "dosage", "symptom", "diagnosis", "disease", "cancer",
            "pregnant", "pregnancy", "treatment", "therapy",
            "doctor", "health", "suicide",

            # Legal
            "legal", "law", "lawsuit", "court", "attorney",
            "lawyer", "contract", "liable", "liability",
            "criminal", "visa", "immigration",

            # Financial
            "financial", "finance", "investment", "invest",
            "stock", "stocks", "share price", "crypto", "tax",
            "loan", "mortgage", "interest rate", "bank",
            "insurance", "revenue", "profit", "loss",

            # Safety / security / sensitive decisions
            "danger", "dangerous", "safe", "safety", "security",
            "explosive", "weapon", "firearm", "password",
            "credential", "private key", "personal data",
            "confidential",
        )

        for claim in claims:

            normalized = str(claim).strip().lower()

            if any(
                term in normalized
                for term in high_impact_terms
            ):
                return True

        return False

    # ============================================================
    # CLAIM EXTRACTION
    # ============================================================

    def _extract_claims(
        self,
        text: str,
    ) -> Any:

        extractor = self.claim_extractor

        # Existing project uses a bound method:
        #
        # factuality_engine.extract_claims
        #
        # This also supports an engine-like object without
        # changing the existing constructor API.

        if callable(extractor):

            return extractor(text)

        method = getattr(
            extractor,
            "extract_claims",
            None,
        )

        if callable(method):

            return method(text)

        raise TypeError(
            "Invalid factuality claim extractor."
        )

    # ============================================================
    # CLAIM VERIFICATION
    # ============================================================

    def _verify_claims(
        self,
        claims: Any,
    ) -> Any:

        verifier = self.verifier

        # Existing project uses:
        #
        # factuality_engine.verify_claims
        #
        # which accepts:
        #
        # verify_claims(claims, evidence)

        if callable(verifier):

            try:

                return verifier(
                    claims,
                    self.evidence,
                )

            except TypeError:

                # Backward-compatible support for a verifier
                # accepting only claims.

                return verifier(
                    claims
                )

        method = getattr(
            verifier,
            "verify_claims",
            None,
        )

        if callable(method):

            try:

                return method(
                    claims,
                    self.evidence,
                )

            except TypeError:

                return method(
                    claims
                )

        raise TypeError(
            "Invalid factuality verifier."
        )

    # ============================================================
    # VERIFICATION NORMALIZATION
    # ============================================================

    @classmethod
    def _normalize_verification(
        cls,
        verification: Any,
        claims: Any,
    ) -> Dict[str, Any]:

        # --------------------------------------------------------
        # FactualityEngine returns a dictionary.
        # --------------------------------------------------------

        if isinstance(
            verification,
            dict,
        ):

            result = dict(
                verification
            )

        # --------------------------------------------------------
        # Support object-style verification results without
        # changing the existing project behavior.
        # --------------------------------------------------------

        else:

            result = {}

            for key in (
                "status",
                "claims",
                "verified_count",
                "failed_count",
                "unknown_count",
                "evidence_count",
                "details",
                "verification_counts",
                "web_fallback",
                "latency_ms",
            ):

                if hasattr(
                    verification,
                    key,
                ):

                    result[key] = getattr(
                        verification,
                        key,
                    )

        # --------------------------------------------------------
        # Always preserve normalized claims.
        # --------------------------------------------------------

        if "claims" not in result:

            result["claims"] = (
                cls._normalize_claims(
                    claims
                )
            )

        # --------------------------------------------------------
        # Always expose integer counters.
        # --------------------------------------------------------

        result["verified_count"] = (
            cls._safe_int(
                result.get(
                    "verified_count",
                    0,
                )
            )
        )

        result["failed_count"] = (
            cls._safe_int(
                result.get(
                    "failed_count",
                    0,
                )
            )
        )

        result["unknown_count"] = (
            cls._safe_int(
                result.get(
                    "unknown_count",
                    0,
                )
            )
        )

        result["evidence_count"] = (
            cls._safe_int(
                result.get(
                    "evidence_count",
                    0,
                )
            )
        )

        # --------------------------------------------------------
        # Normalize details.
        # --------------------------------------------------------

        details = result.get(
            "details",
            [],
        )

        if not isinstance(
            details,
            list,
        ):

            details = []

        result["details"] = details

        # --------------------------------------------------------
        # Normalize verification_counts.
        #
        # This is directly produced by the current
        # FactualityEngine.
        # --------------------------------------------------------

        verification_counts = (
            result.get(
                "verification_counts",
                {},
            )
        )

        if not isinstance(
            verification_counts,
            dict,
        ):

            verification_counts = {}

        result["verification_counts"] = {

            "local_verified": cls._safe_int(
                verification_counts.get(
                    "local_verified",
                    0,
                )
            ),

            "local_failed": cls._safe_int(
                verification_counts.get(
                    "local_failed",
                    0,
                )
            ),

            "web_verified": cls._safe_int(
                verification_counts.get(
                    "web_verified",
                    0,
                )
            ),
        }

        # --------------------------------------------------------
        # Normalize web fallback metadata.
        # --------------------------------------------------------

        web_fallback = result.get(
            "web_fallback",
            {},
        )

        if not isinstance(
            web_fallback,
            dict,
        ):

            web_fallback = {}

        result["web_fallback"] = web_fallback

        # --------------------------------------------------------
        # Normalize latency.
        # --------------------------------------------------------

        result["latency_ms"] = (
            cls._safe_float(
                result.get(
                    "latency_ms",
                    0.0,
                )
            )
        )

        # --------------------------------------------------------
        # Make sure status always exists.
        # --------------------------------------------------------

        result["status"] = (
            cls._verification_status(
                result
            )
        )

        return result

    # ============================================================
    # CLAIM NORMALIZATION
    # ============================================================

    @staticmethod
    def _normalize_claims(
        claims: Any,
    ) -> list:

        if isinstance(
            claims,
            (list, tuple, set),
        ):

            return list(
                claims
            )

        if isinstance(
            claims,
            dict,
        ):

            values = claims.get(
                "claims",
                [],
            )

            if isinstance(
                values,
                (list, tuple, set),
            ):

                return list(
                    values
                )

            if values:

                return [values]

            return []

        if claims:

            return [claims]

        return []

    # ============================================================
    # CLAIM COUNT
    # ============================================================

    @classmethod
    def _claim_count(
        cls,
        claims: Any,
    ) -> int:

        return len(
            cls._normalize_claims(
                claims
            )
        )

    # ============================================================
    # STATUS
    # ============================================================

    @staticmethod
    def _verification_status(
        verification: Any,
    ) -> str:

        if isinstance(
            verification,
            dict,
        ):

            status = verification.get(
                "status",
                "UNKNOWN",
            )

        else:

            status = getattr(
                verification,
                "status",
                "UNKNOWN",
            )

        if status is None:

            return "UNKNOWN"

        return str(
            status
        ).strip().upper()

    # ============================================================
    # SOURCE
    # ============================================================

    @classmethod
    def _verification_source(
        cls,
        verification: Any,
    ) -> str:

        if not isinstance(
            verification,
            dict,
        ):

            return "UNKNOWN"

        details = verification.get(
            "details",
            [],
        )

        if isinstance(
            details,
            list,
        ):

            sources = []

            for detail in details:

                if not isinstance(
                    detail,
                    dict,
                ):

                    continue

                source = str(
                    detail.get(
                        "verification_source",
                        "",
                    )
                ).strip().upper()

                if source:

                    sources.append(
                        source
                    )

            if sources:

                unique = list(
                    dict.fromkeys(
                        sources
                    )
                )

                if len(
                    unique
                ) == 1:

                    return unique[0]

                return "MIXED"

        source = str(
            verification.get(
                "verification_source",
                "",
            )
        ).strip().upper()

        if source:

            return source

        return "UNKNOWN"

    # ============================================================
    # SUMMARY
    # ============================================================

    @classmethod
    def _verification_summary(
        cls,
        verification: Any,
    ) -> Dict[str, Any]:

        if not isinstance(
            verification,
            dict,
        ):

            return {
                "verified_count": 0,
                "failed_count": 0,
                "unknown_count": 0,
                "evidence_count": 0,
                "local_verified": 0,
                "local_failed": 0,
                "web_verified": 0,
                "web_fallback_used": False,
                "verification_counts": {
                    "local_verified": 0,
                    "local_failed": 0,
                    "web_verified": 0,
                },
                "web_fallback": {},
                "details": [],
            }

        verification_counts = (
            verification.get(
                "verification_counts",
                {},
            )
        )

        if not isinstance(
            verification_counts,
            dict,
        ):

            verification_counts = {}

        details = verification.get(
            "details",
            [],
        )

        if not isinstance(
            details,
            list,
        ):

            details = []

        web_fallback = (
            verification.get(
                "web_fallback",
                {},
            )
        )

        if not isinstance(
            web_fallback,
            dict,
        ):

            web_fallback = {}

        normalized_counts = {

            "local_verified": (
                cls._safe_int(
                    verification_counts.get(
                        "local_verified",
                        0,
                    )
                )
            ),

            "local_failed": (
                cls._safe_int(
                    verification_counts.get(
                        "local_failed",
                        0,
                    )
                )
            ),

            "web_verified": (
                cls._safe_int(
                    verification_counts.get(
                        "web_verified",
                        0,
                    )
                )
            ),
        }

        return {

            "verified_count": (
                cls._safe_int(
                    verification.get(
                        "verified_count",
                        0,
                    )
                )
            ),

            "failed_count": (
                cls._safe_int(
                    verification.get(
                        "failed_count",
                        0,
                    )
                )
            ),

            "unknown_count": (
                cls._safe_int(
                    verification.get(
                        "unknown_count",
                        0,
                    )
                )
            ),

            "evidence_count": (
                cls._safe_int(
                    verification.get(
                        "evidence_count",
                        0,
                    )
                )
            ),

            "local_verified": (
                normalized_counts[
                    "local_verified"
                ]
            ),

            "local_failed": (
                normalized_counts[
                    "local_failed"
                ]
            ),

            "web_verified": (
                normalized_counts[
                    "web_verified"
                ]
            ),

            "web_fallback_used": bool(
                web_fallback.get(
                    "used",
                    False,
                )
            ),

            "verification_counts": (
                normalized_counts
            ),

            "web_fallback": (
                web_fallback
            ),

            "details": details,
        }

    # ============================================================
    # VERIFIED CONFIDENCE
    # ============================================================

    @classmethod
    def _verified_confidence(
        cls,
        verification: Any,
    ) -> float:

        if not isinstance(
            verification,
            dict,
        ):

            return cls.VERIFIED_CONFIDENCE

        details = verification.get(
            "details",
            [],
        )

        scores = []

        if isinstance(
            details,
            list,
        ):

            for detail in details:

                if not isinstance(
                    detail,
                    dict,
                ):

                    continue

                for key in (
                    "ranking_score",
                    "similarity",
                    "claim_support",
                ):

                    value = detail.get(
                        key
                    )

                    if value is None:

                        continue

                    try:

                        scores.append(
                            float(value)
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        pass

        if not scores:

            return cls.VERIFIED_CONFIDENCE

        score = (
            sum(scores)
            / len(scores)
        )

        return round(
            max(
                0.70,
                min(
                    1.0,
                    score,
                ),
            ),
            4,
        )

    # ============================================================
    # FAILED CONFIDENCE
    # ============================================================

    @classmethod
    def _failed_confidence(
        cls,
        verification: Any,
    ) -> float:

        if not isinstance(
            verification,
            dict,
        ):

            return 0.80

        failed_count = cls._safe_int(
            verification.get(
                "failed_count",
                0,
            )
        )

        if failed_count > 0:

            return 0.90

        return 0.80

    # ============================================================
    # SAFE INTEGER
    # ============================================================

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:

        try:

            return max(
                0,
                int(value),
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0

    # ============================================================
    # SAFE FLOAT
    # ============================================================

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:

        try:

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return 0.0