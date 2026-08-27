from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class AuditLogger:
    """
    ControlPlane.ai Audit Logger

    Lightweight enterprise-style governance audit logger.

    Responsibilities:
    - Generate a unique request ID
    - Record governance decisions
    - Record request/response governance inspections
    - Record factuality verification results
    - Record evidence provenance and verification source
    - Record web fallback / ranking / consensus telemetry
    - Persist audit events as JSON Lines
    - Provide read access to recent audit events
    - Never crash the request pipeline if logging fails

    IMPORTANT:

    This logger does NOT make governance or factuality decisions.

    It only records decisions already produced by the
    governance pipeline.

    Existing public APIs are preserved:
        - generate_request_id()
        - log()
        - read_events()
    """

    # =========================================================
    # INITIALIZATION
    # =========================================================

    def __init__(
        self,
        log_dir: str = "logs",
        filename: str = "audit.jsonl",
        log_path: Optional[str] = None,
    ):
        self.log_dir = log_dir
        self.filename = filename

        if log_path is not None:
             self.log_path = os.fspath(log_path)
        else:
          self.log_path = os.path.join(
            self.log_dir,
            self.filename,
    )

        self._lock = threading.Lock()

        os.makedirs(
            self.log_dir,
            exist_ok=True,
        )

        self.log_path = os.path.join(
            self.log_dir,
            self.filename,
        )

    # =========================================================
    # REQUEST ID
    # =========================================================

    @staticmethod
    def generate_request_id() -> str:
        """
        Generate a unique audit/request identifier.
        """

        return str(
            uuid.uuid4()
        )

    # =========================================================
    # PUBLIC LOGGING API
    # =========================================================

    def log(
        self,
        result: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build and persist a structured audit event.

        Existing callers can continue using:

            audit_logger.log(result)

        or:

            audit_logger.log(
                result,
                request_id="..."
            )

        The method returns the exact event that was persisted.
        """

        if not isinstance(
            result,
            dict,
        ):
            result = {
                "output": str(result)
            }

        request_id = (
            request_id
            or result.get(
                "request_id"
            )
            or self._request_id_from_metadata(
                result
            )
            or self.generate_request_id()
        )

        event = self._build_event(
            result=result,
            request_id=request_id,
        )

        self._write(
            event
        )

        return event

    # =========================================================
    # EVENT BUILDER
    # =========================================================

    @classmethod
    def _build_event(
        cls,
        result: Dict[str, Any],
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Build the complete governance audit event.

        Existing audit fields are preserved.

        Additional structured fields are added for:

            Factuality
            Evidence
            Web fallback
            Web ranking
            Web consensus
            Governance inspection
        """

        request_inspection = result.get(
            "request_inspection",
            {},
        )

        response_inspection = result.get(
            "response_inspection",
            {},
        )

        if not isinstance(
            request_inspection,
            dict,
        ):
            request_inspection = {}

        if not isinstance(
            response_inspection,
            dict,
        ):
            response_inspection = {}

        factuality = cls._extract_factuality(
            result
        )

        governance = cls._extract_governance(
            result
        )

        return {
            # =================================================
            # CORE AUDIT IDENTITY
            # =================================================

            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "request_id": request_id,

            # =================================================
            # REQUEST
            # =================================================

            "prompt": result.get(
                "prompt",
                "",
            ),

            # =================================================
            # FINAL GOVERNANCE DECISION
            # =================================================

            "decision": result.get(
                "decision",
                result.get(
                    "action",
                    "UNKNOWN",
                ),
            ),

            "action": result.get(
                "action",
                result.get(
                    "decision",
                    "UNKNOWN",
                ),
            ),

            "policy_decision": result.get(
                "policy_decision",
                "ALLOW",
            ),

            # =================================================
            # GOVERNANCE INSPECTION
            # =================================================

            "request_inspection":
                request_inspection,

            "response_inspection":
                response_inspection,

            "governance":
                governance,

            # =================================================
            # FACTUALITY
            # =================================================

            "factuality":
                factuality,

            # =================================================
            # ORIGINAL EVENT STREAM
            # =================================================

            "events": result.get(
                "events",
                [],
            ),

            # =================================================
            # METADATA
            # =================================================

            "metadata": result.get(
                "metadata",
                {},
            ),

            # =================================================
            # TIMING
            # =================================================

            "latency_ms": result.get(
                "latency_ms",
                0.0,
            ),

            "model_latency_ms": result.get(
                "model_latency_ms",
                0.0,
            ),

            # =================================================
            # COMPATIBILITY / TELEMETRY
            # =================================================

            "risk_score": result.get(
                "risk_score",
                0.0,
            ),

            "confidence": result.get(
                "confidence",
                0.0,
            ),

            "token_count": result.get(
                "token_count",
                result.get(
                    "tokens",
                    0,
                ),
            ),

            "estimated_cost": result.get(
                "estimated_cost",
                result.get(
                    "cost",
                    0.0,
                ),
            ),

            "review_id": result.get(
                "review_id",
            ),

            "review_status": result.get(
                "review_status",
            ),
        }

    # =========================================================
    # FACTUALITY EXTRACTION
    # =========================================================

    @classmethod
    def _extract_factuality(
        cls,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract factuality information without changing the
        original result structure.

        Supports:

        1. Direct gateway result:

            {
                "verification": {...}
            }

        2. Nested response governance:

            {
                "response_governance": {
                    "agents": [
                        {
                            "agent": "factuality",
                            "signals": {
                                "verification": {...}
                            }
                        }
                    ]
                }
            }

        3. request_inspection / response_inspection
           agent structures.

        4. Legacy factuality fields.
        """

        verification = result.get(
            "verification"
        )

        # -----------------------------------------------------
        # Find nested factuality if direct verification
        # is not available.
        # -----------------------------------------------------

        if not isinstance(
            verification,
            dict,
        ):

            verification = cls._find_verification(
                result
            )

        if not isinstance(
            verification,
            dict,
        ):
            verification = {}

        # -----------------------------------------------------
        # IMPORTANT FIX
        #
        # A factuality result can exist inside an agent's
        # "signals" dictionary rather than directly under
        # "verification".
        #
        # _find_verification() now searches those structures.
        # -----------------------------------------------------

        status = cls._safe_string(
            verification.get(
                "status",
                result.get(
                    "verification_status",
                    "NOT_RUN",
                ),
            )
        ).upper()

        claims = verification.get(
            "claims",
            [],
        )

        if not isinstance(
            claims,
            list,
        ):
            claims = cls._normalize_list(
                claims
            )

        details = verification.get(
            "details",
            [],
        )

        if not isinstance(
            details,
            list,
        ):
            details = []

        # -----------------------------------------------------
        # Claims count
        #
        # Prefer the verification result, then the gateway
        # result, then the actual claim list.
        # -----------------------------------------------------

        claims_count = verification.get(
            "claims_count"
        )

        if claims_count is None:
            claims_count = result.get(
                "claims_count",
                len(claims),
            )

        # -----------------------------------------------------
        # Factuality enabled
        #
        # bool(verification) alone is insufficient because
        # some nested factuality structures may be present
        # without the exact direct verification shape.
        # -----------------------------------------------------

        factuality_enabled = cls._factuality_is_enabled(
            result=result,
            verification=verification,
            status=status,
            claims=claims,
        )

        factuality = {
            "enabled":
                factuality_enabled,

            "status":
                status,

            "claims":
                claims,

            "claims_count":
                cls._integer(
                    claims_count
                ),

            "verified_count":
                cls._integer(
                    verification.get(
                        "verified_count",
                        0,
                    )
                ),

            "failed_count":
                cls._integer(
                    verification.get(
                        "failed_count",
                        0,
                    )
                ),

            "unknown_count":
                cls._integer(
                    verification.get(
                        "unknown_count",
                        0,
                    )
                ),

            "evidence_count":
                cls._integer(
                    verification.get(
                        "evidence_count",
                        0,
                    )
                ),

            "verification_source":
                cls._verification_source(
                    verification
                ),

            "retrieval":
                cls._safe_dict(
                    verification.get(
                        "retrieval",
                        {},
                    )
                ),

            "web_fallback":
                cls._safe_dict(
                    verification.get(
                        "web_fallback",
                        {},
                    )
                ),

            "web_ranking":
                cls._safe_dict(
                    verification.get(
                        "web_ranking",
                        {},
                    )
                ),

            "web_consensus":
                cls._safe_dict(
                    verification.get(
                        "web_consensus",
                        {},
                    )
                ),

            "claim_support":
                cls._safe_dict(
                    verification.get(
                        "claim_support",
                        {},
                    )
                ),

            "verification_counts":
                cls._safe_dict(
                    verification.get(
                        "verification_counts",
                        {},
                    )
                ),

            "details":
                cls._sanitize_factuality_details(
                    details
                ),

            "latency_ms":
                cls._number(
                    verification.get(
                        "latency_ms",
                        0.0,
                    )
                ),

            # -------------------------------------------------
            # Existing governance-level factuality fields.
            # -------------------------------------------------

            "verification_status":
                cls._safe_string(
                    result.get(
                        "verification_status",
                        status,
                    )
                ).upper(),

            "factuality_gate":
                cls._safe_string(
                    result.get(
                        "factuality_gate",
                        "NOT_RUN",
                    )
                ).upper(),
        }

        return factuality

    # =========================================================
    # FACTUALITY ENABLEMENT
    # =========================================================

    @classmethod
    def _factuality_is_enabled(
        cls,
        result: Dict[str, Any],
        verification: Dict[str, Any],
        status: str,
        claims: list,
    ) -> bool:
        """
        Determine whether factuality actually ran.

        This is metadata extraction only.

        IMPORTANT:
        Do not confuse:

            status == UNKNOWN

        with:

            factuality was not executed.

        A factuality agent may execute and return UNKNOWN because
        evidence was insufficient.

        Therefore nested factuality agent execution is also
        considered enabled.
        """

        # Direct verification result exists.
        if isinstance(
            result.get("verification"),
            dict,
        ):
            return True

        # Explicit verification status.
        explicit_status = cls._safe_string(
            result.get(
                "verification_status"
            )
        ).upper()

        if explicit_status not in {
            "",
            "NOT_RUN",
            "NONE",
        }:
            return True

        # Explicit factuality gate.
        factuality_gate = cls._safe_string(
            result.get(
                "factuality_gate"
            )
        ).upper()

        if factuality_gate not in {
            "",
            "NOT_RUN",
        }:
            return True

        # Nested factuality agent was found.
        if cls._has_nested_factuality_agent(
            result
        ):
            return True

        # A populated verification dictionary is sufficient.
        if isinstance(
            verification,
            dict,
        ) and verification:
            return True

        # A non-empty claim collection with factuality
        # governance structures indicates execution.
        if claims:
            return True

        return False

    # =========================================================
    # NESTED FACTUALITY AGENT DETECTION
    # =========================================================

    @classmethod
    def _has_nested_factuality_agent(
        cls,
        result: Dict[str, Any],
    ) -> bool:
        """
        Detect factuality execution in the current governance
        response format.

        Supported structures include:

            response_governance.agents[*]
            request_governance.agents[*]
            response_inspection.agents[*]
            request_inspection.agents[*]

        and:

            agent == "factuality"

        This method only detects presence. It never makes
        a factuality decision.
        """

        inspection_keys = (
            "response_governance",
            "request_governance",
            "response_inspection",
            "request_inspection",
            "governance",
        )

        for parent_key in inspection_keys:

            parent = result.get(
                parent_key
            )

            if not isinstance(
                parent,
                dict,
            ):
                continue

            if cls._contains_factuality_agent(
                parent
            ):
                return True

        return False

    @classmethod
    def _contains_factuality_agent(
        cls,
        parent: Dict[str, Any],
    ) -> bool:
        """
        Check one governance container for a factuality agent.
        """

        agents = parent.get(
            "agents",
            parent.get(
                "results",
                [],
            ),
        )

        if not isinstance(
            agents,
            list,
        ):
            return False

        for agent in agents:

            if not isinstance(
                agent,
                dict,
            ):
                continue

            name = cls._safe_string(
                agent.get(
                    "agent",
                    agent.get(
                        "name",
                        "",
                    ),
                )
            ).lower()

            if name == "factuality":
                return True

        return False

    # =========================================================
    # GOVERNANCE EXTRACTION
    # =========================================================

    @classmethod
    def _extract_governance(
        cls,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract a compact governance summary while preserving
        the complete request/response inspections separately.
        """

        request_inspection = result.get(
            "request_inspection",
            {},
        )

        response_inspection = result.get(
            "response_inspection",
            {},
        )

        if not isinstance(
            request_inspection,
            dict,
        ):
            request_inspection = {}

        if not isinstance(
            response_inspection,
            dict,
        ):
            response_inspection = {}

        # -----------------------------------------------------
        # Current gateway uses request_governance /
        # response_governance.
        #
        # Preserve compatibility with the older inspection names.
        # -----------------------------------------------------

        request_governance = result.get(
            "request_governance",
            request_inspection,
        )

        response_governance = result.get(
            "response_governance",
            response_inspection,
        )

        if not isinstance(
            request_governance,
            dict,
        ):
            request_governance = request_inspection

        if not isinstance(
            response_governance,
            dict,
        ):
            response_governance = response_inspection

        return {
            "request_decision":
                cls._inspection_decision(
                    request_governance
                ),

            "response_decision":
                cls._inspection_decision(
                    response_governance
                ),

            "final_decision":
                cls._safe_string(
                    result.get(
                        "decision",
                        result.get(
                            "action",
                            "UNKNOWN",
                        ),
                    )
                ).upper(),

            "policy_decision":
                cls._safe_string(
                    result.get(
                        "policy_decision",
                        "ALLOW",
                    )
                ).upper(),

            "risk_score":
                cls._number(
                    result.get(
                        "risk_score",
                        result.get(
                            "response_governance",
                            {}
                        ).get(
                            "risk_score",
                            0.0
                        )
                        if isinstance(
                            result.get(
                                "response_governance",
                                {}
                            ),
                            dict
                        )
                        else 0.0,
                    )
                ),

            "confidence":
                cls._number(
                    result.get(
                        "confidence",
                        result.get(
                            "response_governance",
                            {}
                        ).get(
                            "confidence",
                            0.0
                        )
                        if isinstance(
                            result.get(
                                "response_governance",
                                {}
                            ),
                            dict
                        )
                        else 0.0,
                    )
                ),
        }

    # =========================================================
    # FACTUALITY DETAIL SANITIZATION
    # =========================================================

    @classmethod
    def _sanitize_factuality_details(
        cls,
        details: Any,
    ) -> list:
        """
        Preserve factuality evidence details in a predictable
        JSON-safe structure.

        No factuality decision is made here.
        """

        if not isinstance(
            details,
            list,
        ):
            return []

        sanitized = []

        for item in details:

            if not isinstance(
                item,
                dict,
            ):
                continue

            row = {
                "claim": item.get(
                    "claim",
                    "",
                ),

                "status": cls._safe_string(
                    item.get(
                        "status",
                        "UNKNOWN",
                    )
                ).upper(),

                "reason": item.get(
                    "reason",
                    "",
                ),

                "source": item.get(
                    "source",
                ),

                "evidence": item.get(
                    "evidence",
                    "",
                ),

                "similarity": cls._number(
                    item.get(
                        "similarity",
                        0.0,
                    )
                ),

                "verification_source":
                    cls._safe_string(
                        item.get(
                            "verification_source",
                            "UNKNOWN",
                        )
                    ).upper(),

                "retrieved_evidence":
                    cls._safe_list(
                        item.get(
                            "retrieved_evidence",
                            [],
                        )
                    ),

                "web_evidence":
                    cls._safe_list(
                        item.get(
                            "web_evidence",
                            [],
                        )
                    ),

                "web_consensus":
                    cls._safe_dict(
                        item.get(
                            "web_consensus",
                            {},
                        )
                    ),

                "best_web_ranking_score":
                    cls._nullable_number(
                        item.get(
                            "best_web_ranking_score"
                        )
                    ),

                "web_error":
                    item.get(
                        "web_error"
                    ),
            }

            sanitized.append(
                row
            )

        return sanitized

    # =========================================================
    # VERIFICATION SOURCE
    # =========================================================

    @staticmethod
    def _verification_source(
        verification: Dict[str, Any],
    ) -> str:
        """
        Determine the already-computed verification source.

        Priority:
            verification_source
            detail-level source
            UNKNOWN
        """

        direct = verification.get(
            "verification_source"
        )

        if direct:

            return str(
                direct
            ).strip().upper()

        details = verification.get(
            "details",
            []
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

                source = detail.get(
                    "verification_source"
                )

                if source:

                    sources.append(
                        str(
                            source
                        ).strip().upper()
                    )

            if sources:

                unique = list(
                    dict.fromkeys(
                        sources
                    )
                )

                if len(unique) == 1:
                    return unique[0]

                return "MIXED"

        return "UNKNOWN"

    # =========================================================
    # VERIFICATION SEARCH
    # =========================================================

    @classmethod
    def _find_verification(
        cls,
        result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Find verification data in nested governance structures.

        Supports both the old inspection structure and the
        current response_governance structure.

        IMPORTANT FIX:

        The factuality agent's verification is commonly stored as:

            response_governance
                -> agents
                    -> factuality
                        -> signals
                            -> verification

        The previous logger did not reliably inspect this path.
        """

        candidates = []

        # -----------------------------------------------------
        # Direct top-level candidates.
        # -----------------------------------------------------

        for key in (
            "verification",
            "factuality",
        ):

            value = result.get(
                key
            )

            if isinstance(
                value,
                dict,
            ):
                candidates.append(
                    value
                )

        # -----------------------------------------------------
        # Governance containers.
        # -----------------------------------------------------

        parent_keys = (
            "request_governance",
            "response_governance",
            "request_inspection",
            "response_inspection",
            "governance",
        )

        for parent_key in parent_keys:

            parent = result.get(
                parent_key
            )

            if not isinstance(
                parent,
                dict,
            ):
                continue

            # ---------------------------------------------
            # Direct nested verification/factuality.
            # ---------------------------------------------

            for key in (
                "verification",
                "factuality",
            ):

                value = parent.get(
                    key
                )

                if isinstance(
                    value,
                    dict,
                ):
                    candidates.append(
                        value
                    )

            # ---------------------------------------------
            # Agent list.
            # ---------------------------------------------

            agents = parent.get(
                "agents",
                parent.get(
                    "results",
                    [],
                ),
            )

            if not isinstance(
                agents,
                list,
            ):
                continue

            for agent in agents:

                if not isinstance(
                    agent,
                    dict,
                ):
                    continue

                agent_name = cls._safe_string(
                    agent.get(
                        "agent",
                        agent.get(
                            "name",
                            "",
                        ),
                    )
                ).lower()

                # -----------------------------------------
                # Prefer the factuality agent explicitly.
                # -----------------------------------------

                is_factuality_agent = (
                    agent_name == "factuality"
                )

                # -----------------------------------------
                # Direct verification.
                # -----------------------------------------

                for key in (
                    "verification",
                    "factuality",
                ):

                    value = agent.get(
                        key
                    )

                    if isinstance(
                        value,
                        dict,
                    ):

                        if is_factuality_agent:
                            candidates.insert(
                                0,
                                value
                            )
                        else:
                            candidates.append(
                                value
                            )

                # -----------------------------------------
                # Factuality agent telemetry normally stores
                # the verification result under "signals".
                # -----------------------------------------

                signals = agent.get(
                    "signals"
                )

                if isinstance(
                    signals,
                    dict,
                ):

                    for key in (
                        "verification",
                        "factuality",
                    ):

                        value = signals.get(
                            key
                        )

                        if isinstance(
                            value,
                            dict,
                        ):

                            if is_factuality_agent:
                                candidates.insert(
                                    0,
                                    value
                                )
                            else:
                                candidates.append(
                                    value
                                )

        # -----------------------------------------------------
        # Recursive fallback for future compatible structures.
        # -----------------------------------------------------

        recursive = cls._recursive_find_verification(
            result
        )

        if isinstance(
            recursive,
            dict,
        ):
            candidates.append(
                recursive
            )

        # -----------------------------------------------------
        # Select the best candidate.
        #
        # Prefer actual verification structures over empty
        # factuality metadata.
        # -----------------------------------------------------

        best = None
        best_score = -1

        for candidate in candidates:

            if not isinstance(
                candidate,
                dict,
            ):
                continue

            score = 0

            for key in (
                "status",
                "claims",
                "verified_count",
                "failed_count",
                "unknown_count",
                "evidence_count",
                "details",
            ):

                if key in candidate:
                    score += 1

            if candidate.get(
                "details"
            ):
                score += 2

            if candidate.get(
                "claims"
            ):
                score += 2

            if score > best_score:

                best = candidate
                best_score = score

        return best

    # =========================================================
    # RECURSIVE VERIFICATION SEARCH
    # =========================================================

    @classmethod
    def _recursive_find_verification(
        cls,
        value: Any,
        depth: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Conservative recursive fallback.

        It searches nested dictionaries/lists for an object
        that has a recognizable verification signature.

        Maximum depth prevents pathological traversal.
        """

        if depth > 8:
            return None

        if isinstance(
            value,
            dict,
        ):

            # Prefer explicit verification keys.
            for key in (
                "verification",
                "factuality",
            ):

                candidate = value.get(
                    key
                )

                if isinstance(
                    candidate,
                    dict,
                ) and cls._looks_like_verification(
                    candidate
                ):
                    return candidate

            # Search children.
            for child in value.values():

                found = cls._recursive_find_verification(
                    child,
                    depth + 1,
                )

                if found is not None:
                    return found

            return None

        if isinstance(
            value,
            (list, tuple),
        ):

            for child in value:

                found = cls._recursive_find_verification(
                    child,
                    depth + 1,
                )

                if found is not None:
                    return found

        return None

    # =========================================================
    # VERIFICATION SIGNATURE
    # =========================================================

    @staticmethod
    def _looks_like_verification(
        value: Any,
    ) -> bool:
        """
        Determine whether a dictionary looks like a factuality
        verification result.
        """

        if not isinstance(
            value,
            dict,
        ):
            return False

        signature_keys = {
            "status",
            "claims",
            "verified_count",
            "failed_count",
            "unknown_count",
            "evidence_count",
            "details",
        }

        return bool(
            signature_keys.intersection(
                value.keys()
            )
        )

    # =========================================================
    # INSPECTION DECISION
    # =========================================================

    @staticmethod
    def _inspection_decision(
        inspection: Dict[str, Any],
    ) -> str:
        """
        Extract a normalized governance decision.
        """

        if not isinstance(
            inspection,
            dict,
        ):
            return "UNKNOWN"

        return str(
            inspection.get(
                "decision",
                inspection.get(
                    "action",
                    "UNKNOWN",
                ),
            )
        ).strip().upper()

    # =========================================================
    # REQUEST ID FROM METADATA
    # =========================================================

    @staticmethod
    def _request_id_from_metadata(
        result: Dict[str, Any],
    ) -> Optional[str]:

        metadata = result.get(
            "metadata"
        )

        if not isinstance(
            metadata,
            dict,
        ):
            return None

        value = metadata.get(
            "request_id"
        )

        if value is None:
            return None

        return str(
            value
        )

    # =========================================================
    # SAFE HELPERS
    # =========================================================

    @staticmethod
    def _safe_string(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        return str(
            value
        ).strip()

    @staticmethod
    def _number(
        value: Any,
    ) -> float:

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

    @staticmethod
    def _nullable_number(
        value: Any,
    ):

        if value is None:
            return None

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @staticmethod
    def _integer(
        value: Any,
    ) -> int:

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0

    @staticmethod
    def _safe_dict(
        value: Any,
    ) -> Dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}

    @staticmethod
    def _safe_list(
        value: Any,
    ) -> list:

        if isinstance(
            value,
            list,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            tuple,
        ):
            return list(
                value
            )

        return []

    @staticmethod
    def _normalize_list(
        value: Any,
    ) -> list:

        if value is None:
            return []

        if isinstance(
            value,
            list,
        ):
            return value

        if isinstance(
            value,
            tuple,
        ):
            return list(
                value
            )

        return [
            value
        ]

    # =========================================================
    # FILE PERSISTENCE
    # =========================================================

    def _write(
        self,
        event: Dict[str, Any],
    ) -> None:
        """
        Persist one event as JSON Lines.

        Audit failure must NEVER break the governance pipeline.
        """

        try:

            serialized = json.dumps(
                event,
                ensure_ascii=False,
                default=str,
            )

            with self._lock:

                with open(
                    self.log_path,
                    "a",
                    encoding="utf-8",
                ) as file:

                    file.write(
                        serialized
                        + "\n"
                    )

        except Exception:
            # Audit failure must never affect model execution
            # or governance decisions.
            pass

    # =========================================================
    # READ AUDIT LOG
    # =========================================================

    def read_events(
        self,
        limit: int = 100,
    ):
        """
        Return the most recent audit events.

        Existing behavior is preserved.
        """

        try:

            limit = max(
                1,
                int(limit),
            )

        except (
            TypeError,
            ValueError,
        ):

            limit = 100

        if not os.path.exists(
            self.log_path
        ):
            return []

        events = []

        try:

            with open(
                self.log_path,
                "r",
                encoding="utf-8",
            ) as file:

                for line in file:

                    line = line.strip()

                    if not line:
                        continue

                    try:

                        events.append(
                            json.loads(
                                line
                            )
                        )

                    except json.JSONDecodeError:
                        continue

            return events[-limit:]

        except Exception:
            return []