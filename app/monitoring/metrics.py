from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional
import time


# ============================================================
# CONSTANTS
# ============================================================

VALID_DECISIONS = {
    "ALLOW",
    "REVIEW",
    "BLOCK",
    "EDIT",
    "UNKNOWN",
}


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_number(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def _safe_integer(
    value: Any,
    default: int = 0,
) -> int:

    try:

        if value is None:
            return default

        return int(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def _safe_dict(
    value: Any,
) -> Dict[str, Any]:

    if isinstance(
        value,
        dict,
    ):

        return dict(value)

    return {}


def _safe_list(
    value: Any,
) -> List[Any]:

    if isinstance(
        value,
        list,
    ):

        return list(value)

    if isinstance(
        value,
        tuple,
    ):

        return list(value)

    if isinstance(
        value,
        set,
    ):

        return list(value)

    return []


def _clamp01(
    value: Any,
) -> float:

    number = _safe_number(
        value,
        0.0,
    )

    return min(
        max(
            number,
            0.0,
        ),
        1.0,
    )


# ============================================================
# METRIC EVENT
# ============================================================

@dataclass
class MetricEvent:

    request_id: Optional[str] = None

    decision: str = "UNKNOWN"

    risk_score: float = 0.0

    latency_ms: float = 0.0

    model_latency_ms: float = 0.0

    prompt_chars: int = 0

    input_tokens: int = 0

    output_tokens: int = 0

    token_count: int = 0

    estimated_cost: float = 0.0

    cost: float = 0.0

    model: str = "unknown"

    provider: str = "unknown"

    cost_source: Optional[str] = None

    cost_details: Dict[str, Any] = field(
        default_factory=dict
    )

    review_id: Optional[str] = None

    review_status: Optional[str] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    request_governance: Dict[str, Any] = field(
        default_factory=dict
    )

    response_governance: Dict[str, Any] = field(
        default_factory=dict
    )

    factuality: Dict[str, Any] = field(
        default_factory=dict
    )

    timestamp: float = field(
        default_factory=time.time
    )

    # ========================================================
    # FACTUALITY FROM CLAIM RESULTS
    # ========================================================

    @staticmethod
    def _factuality_from_claim_results(
        claim_results: Any,
    ) -> Dict[str, Any]:

        results = _safe_list(
            claim_results
        )

        if not results:

            return {}

        claims = len(
            results
        )

        verified = 0

        failed = 0

        unknown = 0

        status_counts: Dict[
            str,
            int
        ] = {}

        for item in results:

            if isinstance(
                item,
                dict,
            ):

                status = item.get(
                    "status",
                    item.get(
                        "verification_status",
                        item.get(
                            "result",
                            "",
                        ),
                    ),
                )

            else:

                status = ""

            key = str(
                status
            ).strip().upper()

            if key in {
                "VERIFIED",
                "SUPPORTED",
                "PASS",
                "TRUE",
            }:

                verified += 1

            elif key in {
                "FAILED",
                "FAIL",
                "CONTRADICTED",
                "FALSE",
            }:

                failed += 1

            else:

                unknown += 1

            if key:

                status_counts[
                    key
                ] = (
                    status_counts.get(
                        key,
                        0,
                    )
                    + 1
                )

        return {

            "claims":
                claims,

            "verified":
                verified,

            "failed":
                failed,

            "unknown":
                unknown,

            "status_counts":
                status_counts,
        }

    # ========================================================
    # FACTUALITY EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_factuality(
        request_governance: Dict[str, Any],
        response_governance: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Extract factuality telemetry without modifying the
        governance pipeline.

        Supported locations include:

            result["factuality"]

            result["verification"]

            response_governance["factuality"]

            response_governance["verification"]

            response_governance["agents"]

            request_governance["agents"]

        Response governance is searched before request
        governance so that response factuality is not
        accidentally replaced by request factuality.
        """

        result = _safe_dict(
            result
        )

        request_governance = _safe_dict(
            request_governance
        )

        response_governance = _safe_dict(
            response_governance
        )

        # ----------------------------------------------------
        # 1. Explicit top-level factuality
        # ----------------------------------------------------

        explicit = _safe_dict(
            result.get(
                "factuality",
                {},
            )
        )

        if explicit:

            return MetricEvent._normalize_factuality(
                explicit
            )

        # ----------------------------------------------------
        # 2. Explicit top-level verification
        # ----------------------------------------------------

        verification = _safe_dict(
            result.get(
                "verification",
                {},
            )
        )

        if verification:

            nested = _safe_dict(
                verification.get(
                    "factuality",
                    {},
                )
            )

            if nested:

                return MetricEvent._normalize_factuality(
                    nested
                )

            normalized = (
                MetricEvent._normalize_factuality(
                    verification
                )
            )

            if normalized:

                return normalized

        # ----------------------------------------------------
        # 3. Direct response factuality
        # ----------------------------------------------------

        nested = _safe_dict(
            response_governance.get(
                "factuality",
                {},
            )
        )

        if nested:

            return MetricEvent._normalize_factuality(
                nested
            )

        # ----------------------------------------------------
        # 4. Direct response verification
        # ----------------------------------------------------

        response_verification = _safe_dict(
            response_governance.get(
                "verification",
                {},
            )
        )

        if response_verification:

            nested = _safe_dict(
                response_verification.get(
                    "factuality",
                    {},
                )
            )

            if nested:

                return MetricEvent._normalize_factuality(
                    nested
                )

            normalized = (
                MetricEvent._normalize_factuality(
                    response_verification
                )
            )

            if normalized:

                return normalized

        # ----------------------------------------------------
        # 5. Search governance agents
        # ----------------------------------------------------

        for governance in (
            response_governance,
            request_governance,
        ):

            agents = _safe_list(
                governance.get(
                    "agents",
                    [],
                )
            )

            for agent in agents:

                if not isinstance(
                    agent,
                    dict,
                ):

                    continue

                agent_name = str(
                    agent.get(
                        "agent",
                        agent.get(
                            "agent_name",
                            agent.get(
                                "name",
                                "",
                            ),
                        ),
                    )
                ).strip().lower()

                if (
                    "factual" not in agent_name
                    and
                    "verification" not in agent_name
                    and
                    "verif" not in agent_name
                ):

                    continue

                # --------------------------------------------
                # Current expected structure:
                #
                # factuality
                #     -> signals
                # --------------------------------------------

                signals = _safe_dict(
                    agent.get(
                        "signals",
                        {},
                    )
                )

                if signals:

                    return MetricEvent._normalize_factuality(
                        signals
                    )

                # --------------------------------------------
                # Compatibility:
                #
                # factuality
                #     -> result
                # --------------------------------------------

                nested_result = _safe_dict(
                    agent.get(
                        "result",
                        {},
                    )
                )

                if nested_result:

                    normalized = (
                        MetricEvent._normalize_factuality(
                            nested_result
                        )
                    )

                    if normalized:

                        return normalized

                # --------------------------------------------
                # Compatibility:
                #
                # factuality
                #     -> details
                # --------------------------------------------

                details = _safe_dict(
                    agent.get(
                        "details",
                        {},
                    )
                )

                if details:

                    normalized = (
                        MetricEvent._normalize_factuality(
                            details
                        )
                    )

                    if normalized:

                        return normalized

                # --------------------------------------------
                # Compatibility:
                #
                # factuality fields directly on agent
                # --------------------------------------------

                direct_fields = {}

                for key in (
                    "claims",
                    "claims_count",
                    "total_claims",
                    "verified",
                    "verified_count",
                    "failed",
                    "failed_count",
                    "unknown",
                    "unknown_count",
                    "status",
                    "factuality_status",
                    "verification_status",
                    "status_counts",
                ):

                    if key in agent:

                        direct_fields[
                            key
                        ] = agent.get(
                            key
                        )

                if direct_fields:

                    return MetricEvent._normalize_factuality(
                        direct_fields
                    )

                # --------------------------------------------
                # Compatibility:
                #
                # claim results directly on agent
                # --------------------------------------------

                claim_results = agent.get(
                    "claim_results",
                    agent.get(
                        "results",
                        None,
                    ),
                )

                if isinstance(
                    claim_results,
                    list,
                ):

                    normalized = (
                        MetricEvent._factuality_from_claim_results(
                            claim_results
                        )
                    )

                    if normalized:

                        return normalized

        # ----------------------------------------------------
        # Nothing available
        # ----------------------------------------------------

        return {}

    # ========================================================
    # FACTUALITY NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_factuality(
        factuality: Dict[str, Any],
    ) -> Dict[str, Any]:

        factuality = _safe_dict(
            factuality
        )

        if not factuality:

            return {}

        normalized = dict(
            factuality
        )

        # ----------------------------------------------------
        # Nested factuality result
        # ----------------------------------------------------

        for key in (
            "factuality",
            "verification",
            "result",
            "details",
            "signals",
            "summary",
        ):

            nested = _safe_dict(
                normalized.get(
                    key,
                    {},
                )
            )

            if nested:

                merged = dict(
                    nested
                )

                for parent_key, value in (
                    normalized.items()
                ):

                    if parent_key not in merged:

                        merged[
                            parent_key
                        ] = value

                normalized = merged

                break

        # ----------------------------------------------------
        # CLAIMS
        # ----------------------------------------------------

        if (
            "claims" not in normalized
            and
            "claims_count" in normalized
        ):

            normalized[
                "claims"
            ] = normalized.get(
                "claims_count",
                0,
            )

        elif (
            "claims" not in normalized
            and
            "total_claims" in normalized
        ):

            normalized[
                "claims"
            ] = normalized.get(
                "total_claims",
                0,
            )

        # ----------------------------------------------------
        # VERIFIED
        # ----------------------------------------------------

        if (
            "verified" not in normalized
            and
            "verified_count" in normalized
        ):

            normalized[
                "verified"
            ] = normalized.get(
                "verified_count",
                0,
            )

        # ----------------------------------------------------
        # FAILED
        # ----------------------------------------------------

        if (
            "failed" not in normalized
            and
            "failed_count" in normalized
        ):

            normalized[
                "failed"
            ] = normalized.get(
                "failed_count",
                0,
            )

        # ----------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------

        if (
            "unknown" not in normalized
            and
            "unknown_count" in normalized
        ):

            normalized[
                "unknown"
            ] = normalized.get(
                "unknown_count",
                0,
            )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        if (
            "status" not in normalized
            and
            "factuality_status" in normalized
        ):

            normalized[
                "status"
            ] = normalized.get(
                "factuality_status"
            )

        if (
            "status" not in normalized
            and
            "verification_status" in normalized
        ):

            normalized[
                "status"
            ] = normalized.get(
                "verification_status"
            )

        # ----------------------------------------------------
        # NUMERIC NORMALIZATION
        # ----------------------------------------------------

        for key in (
            "claims",
            "verified",
            "failed",
            "unknown",
        ):

            if key in normalized:

                normalized[
                    key
                ] = max(
                    _safe_integer(
                        normalized.get(
                            key,
                            0,
                        )
                    ),
                    0,
                )

        # ----------------------------------------------------
        # REQUESTS CHECKED
        # ----------------------------------------------------

        if "requests_checked" in normalized:

            normalized[
                "requests_checked"
            ] = max(
                _safe_integer(
                    normalized.get(
                        "requests_checked",
                        0,
                    )
                ),
                0,
            )

        # ----------------------------------------------------
        # STATUS COUNTS
        # ----------------------------------------------------

        statuses = _safe_dict(
            normalized.get(
                "status_counts",
                {},
            )
        )

        if statuses:

            normalized[
                "status_counts"
            ] = {

                str(
                    status
                ).strip().upper():

                max(
                    _safe_integer(
                        count
                    ),
                    0,
                )

                for status, count
                in statuses.items()

                if str(
                    status
                ).strip()
            }

        return normalized

    # ========================================================
    # FROM RESULT
    # ========================================================

    @classmethod
    def from_result(
        cls,
        result: Any,
    ) -> "MetricEvent":

        """
        Convert a governed result into a normalized
        monitoring event.

        This method is intentionally defensive.

        Metrics must never modify or break the actual
        governance request.
        """

        if not isinstance(
            result,
            dict,
        ):

            result = {}

        # ----------------------------------------------------
        # DECISION
        # ----------------------------------------------------

        decision = str(
            result.get(
                "decision",
                result.get(
                    "action",
                    result.get(
                        "policy_decision",
                        "UNKNOWN",
                    ),
                ),
            )
        ).upper()

        if decision not in VALID_DECISIONS:

            decision = "UNKNOWN"

        # ----------------------------------------------------
        # METADATA / REQUEST ID
        # ----------------------------------------------------

        metadata = _safe_dict(
            result.get(
                "metadata",
                {},
            )
        )

        request_id = (
            result.get(
                "request_id"
            )
            or
            metadata.get(
                "request_id"
            )
        )

        if request_id is not None:

            request_id = str(
                request_id
            )

        # ----------------------------------------------------
        # RISK
        # ----------------------------------------------------

        risk_score = _clamp01(
            result.get(
                "risk_score",
                result.get(
                    "risk",
                    result.get(
                        "responsibility",
                        0.0,
                    ),
                ),
            )
        )

        # ----------------------------------------------------
        # TOTAL LATENCY
        # ----------------------------------------------------

        latency_ms = max(
            _safe_number(
                result.get(
                    "latency_ms",
                    result.get(
                        "latency",
                        0.0,
                    ),
                )
            ),
            0.0,
        )

        # ----------------------------------------------------
        # MODEL LATENCY
        # ----------------------------------------------------
        #
        # IMPORTANT:
        #
        # The model gateway already measures model latency.
        # Metrics must preserve that value.
        #
        # Compatibility aliases are accepted so older gateway
        # responses continue to work.
        # ----------------------------------------------------

        model_latency_ms = max(
            _safe_number(
                result.get(
                    "model_latency_ms",
                    result.get(
                        "model_latency",
                        result.get(
                            "model_time_ms",
                            result.get(
                                "model_ms",
                                0.0,
                            ),
                        ),
                    ),
                )
            ),
            0.0,
        )

        # ----------------------------------------------------
        # PROMPT
        # ----------------------------------------------------

        prompt = result.get(
            "prompt",
            "",
        )

        if prompt is None:

            prompt = ""

        prompt = str(
            prompt
        )

        # ----------------------------------------------------
        # INPUT TOKENS
        # ----------------------------------------------------

        input_tokens = max(
            _safe_integer(
                result.get(
                    "input_tokens",
                    0,
                )
            ),
            0,
        )

        # ----------------------------------------------------
        # OUTPUT TOKENS
        # ----------------------------------------------------

        output_tokens = max(
            _safe_integer(
                result.get(
                    "output_tokens",
                    0,
                )
            ),
            0,
        )

        # ----------------------------------------------------
        # TOKEN COUNT
        # ----------------------------------------------------

        token_count = max(
            _safe_integer(
                result.get(
                    "token_count",
                    result.get(
                        "tokens",
                        input_tokens
                        + output_tokens,
                    ),
                )
            ),
            0,
        )

        # If the gateway supplied input/output tokens but
        # token_count was absent, derive the total.
        if (
            token_count == 0
            and
            (
                input_tokens > 0
                or
                output_tokens > 0
            )
        ):

            token_count = (
                input_tokens
                + output_tokens
            )

        # ----------------------------------------------------
        # COST
        # ----------------------------------------------------
        #
        # IMPORTANT COMPATIBILITY RULE:
        #
        # Existing callers/tests may provide:
        #
        #     {"cost": 0.01}
        #
        # while newer gateway responses may provide:
        #
        #     {"estimated_cost": 0.01}
        #
        # Metrics must accept both.
        #
        # Metrics does NOT calculate provider pricing.
        # It only normalizes and aggregates values supplied
        # by the gateway/provider.
        # ----------------------------------------------------

        raw_estimated_cost = result.get(
            "estimated_cost",
            None,
        )

        raw_cost = result.get(
            "cost",
            None,
        )

        # Prefer explicit estimated_cost.
        if raw_estimated_cost is not None:

            estimated_cost = max(
                _safe_number(
                    raw_estimated_cost
                ),
                0.0,
            )

        # Backward compatibility:
        # cost becomes estimated_cost when the newer field
        # was not supplied.
        elif raw_cost is not None:

            estimated_cost = max(
                _safe_number(
                    raw_cost
                ),
                0.0,
            )

        else:

            estimated_cost = 0.0

        # Preserve the explicit provider cost when present.
        if raw_cost is not None:

            cost = max(
                _safe_number(
                    raw_cost
                ),
                0.0,
            )

        else:

            # For older result structures, estimated_cost
            # remains the compatible cost value.
            cost = estimated_cost

        # ----------------------------------------------------
        # MODEL / PROVIDER
        # ----------------------------------------------------

        model = result.get(
            "model",
            "unknown",
        )

        provider = result.get(
            "provider",
            "unknown",
        )

        if model is None:

            model = "unknown"

        if provider is None:

            provider = "unknown"

        model = str(
            model
        )

        provider = str(
            provider
        )

        # ----------------------------------------------------
        # COST METADATA
        # ----------------------------------------------------

        cost_source = result.get(
            "cost_source",
            None,
        )

        if cost_source is not None:

            cost_source = str(
                cost_source
            )

        cost_details = _safe_dict(
            result.get(
                "cost_details",
                {},
            )
        )

        # ----------------------------------------------------
        # REVIEW
        # ----------------------------------------------------

        review_id = result.get(
            "review_id",
            None,
        )

        review_status = result.get(
            "review_status",
            None,
        )

        if review_id is not None:

            review_id = str(
                review_id
            )

        if review_status is not None:

            review_status = str(
                review_status
            )

        # ----------------------------------------------------
        # GOVERNANCE
        # ----------------------------------------------------

        request_governance = _safe_dict(
            result.get(
                "request_governance",
                {},
            )
        )

        response_governance = _safe_dict(
            result.get(
                "response_governance",
                {},
            )
        )

        # ----------------------------------------------------
        # FACTUALITY
        # ----------------------------------------------------

        factuality = (
            cls._extract_factuality(
                request_governance=(
                    request_governance
                ),
                response_governance=(
                    response_governance
                ),
                result=result,
            )
        )

        # ----------------------------------------------------
        # CREATE EVENT
        # ----------------------------------------------------

        return cls(

            request_id=request_id,

            decision=decision,

            risk_score=risk_score,

            latency_ms=latency_ms,

            model_latency_ms=model_latency_ms,

            prompt_chars=len(
                prompt
            ),

            input_tokens=input_tokens,

            output_tokens=output_tokens,

            token_count=token_count,

            estimated_cost=estimated_cost,

            cost=cost,

            model=model,

            provider=provider,

            cost_source=cost_source,

            cost_details=cost_details,

            review_id=review_id,

            review_status=review_status,

            metadata=metadata,

            request_governance=(
                request_governance
            ),

            response_governance=(
                response_governance
            ),

            factuality=factuality,
        )


# ============================================================
# METRICS COLLECTOR
# ============================================================

class MetricsCollector:

    """
    Thread-safe monitoring collector.

    The collector is intentionally passive.

        Model/Gateway
              ↓
        MetricEvent
              ↓
        MetricsCollector
              ↓
        MetricsAggregator
              ↓
        API / Dashboard

    The collector does NOT calculate provider pricing.

    It aggregates cost and latency supplied by the
    model gateway/provider.
    """

    def __init__(self):

        self._lock = Lock()

        self._events: List[
            MetricEvent
        ] = []

    # ========================================================
    # RECORD
    # ========================================================

    def record(
        self,
        result: Dict[str, Any],
    ) -> MetricEvent:

        # Metrics must never break the request.

        try:

            event = MetricEvent.from_result(
                result
            )

        except Exception:

            event = MetricEvent(
                request_id=None,
                decision="UNKNOWN",
            )

        with self._lock:

            self._events.append(
                event
            )

        return event

    # ========================================================
    # COUNT
    # ========================================================

    @property
    def total_requests(
        self,
    ) -> int:

        with self._lock:

            return len(
                self._events
            )

    # ========================================================
    # DECISION COUNTS
    # ========================================================

    def decision_counts(
        self,
    ) -> Dict[str, int]:

        counts = {
            "ALLOW": 0,
            "REVIEW": 0,
            "BLOCK": 0,
            "EDIT": 0,
            "UNKNOWN": 0,
        }

        with self._lock:

            events = list(
                self._events
            )

        for event in events:

            decision = (
                event.decision
                if event.decision
                in VALID_DECISIONS
                else "UNKNOWN"
            )

            counts[
                decision
            ] += 1

        return counts

    # ========================================================
    # DECISION RATES
    # ========================================================

    def decision_rates(
        self,
    ) -> Dict[str, float]:

        total = self.total_requests

        if total == 0:

            return {
                "ALLOW": 0.0,
                "REVIEW": 0.0,
                "BLOCK": 0.0,
                "EDIT": 0.0,
            }

        counts = (
            self.decision_counts()
        )

        return {

            key: round(
                (
                    counts.get(
                        key,
                        0,
                    )
                    /
                    total
                )
                * 100.0,
                2,
            )

            for key in (
                "ALLOW",
                "REVIEW",
                "BLOCK",
                "EDIT",
            )
        }

    # ========================================================
    # RISK
    # ========================================================

    def risk_statistics(
        self,
    ) -> Dict[str, float]:

        with self._lock:

            values = [
                event.risk_score
                for event in self._events
            ]

        if not values:

            return {
                "average": 0.0,
                "minimum": 0.0,
                "maximum": 0.0,
                "high_risk_rate": 0.0,
            }

        average = (
            sum(values)
            /
            len(values)
        )

        high_risk = sum(
            value >= 0.70
            for value in values
        )

        return {

            "average":
                round(
                    average,
                    4,
                ),

            "minimum":
                round(
                    min(values),
                    4,
                ),

            "maximum":
                round(
                    max(values),
                    4,
                ),

            "high_risk_rate":
                round(
                    (
                        high_risk
                        /
                        len(values)
                    )
                    * 100.0,
                    2,
                ),
        }

    # ========================================================
    # LATENCY
    # ========================================================

    def latency_statistics(
        self,
    ) -> Dict[str, float]:

        with self._lock:

            total_values = [
                event.latency_ms
                for event in self._events
                if event.latency_ms >= 0
            ]

            model_values = [
                event.model_latency_ms
                for event in self._events
                if event.model_latency_ms > 0
            ]

        # ----------------------------------------------------
        # TOTAL LATENCY
        # ----------------------------------------------------

        if total_values:

            average_ms = (
                sum(total_values)
                /
                len(total_values)
            )

            minimum_ms = min(
                total_values
            )

            maximum_ms = max(
                total_values
            )

        else:

            average_ms = 0.0

            minimum_ms = 0.0

            maximum_ms = 0.0

        # ----------------------------------------------------
        # MODEL LATENCY
        # ----------------------------------------------------
        #
        # Only requests for which the model gateway actually
        # supplied model latency are included.
        #
        # This prevents zero-valued compatibility events
        # from artificially lowering the model latency.
        # ----------------------------------------------------

        if model_values:

            model_average_ms = (
                sum(model_values)
                /
                len(model_values)
            )

            model_minimum_ms = min(
                model_values
            )

            model_maximum_ms = max(
                model_values
            )

        else:

            model_average_ms = 0.0

            model_minimum_ms = 0.0

            model_maximum_ms = 0.0

        return {

            "average_ms":
                round(
                    average_ms,
                    3,
                ),

            "minimum_ms":
                round(
                    minimum_ms,
                    3,
                ),

            "maximum_ms":
                round(
                    maximum_ms,
                    3,
                ),

            "model_average_ms":
                round(
                    model_average_ms,
                    3,
                ),

            "model_minimum_ms":
                round(
                    model_minimum_ms,
                    3,
                ),

            "model_maximum_ms":
                round(
                    model_maximum_ms,
                    3,
                ),
        }

    # ========================================================
    # COST
    # ========================================================

    def cost_statistics(
        self,
    ) -> Dict[str, float]:

        with self._lock:

            values = [
                event.estimated_cost
                for event in self._events
            ]

        if not values:

            return {
                "total": 0.0,
                "average": 0.0,
                "maximum": 0.0,
            }

        total = sum(
            values
        )

        return {

            "total":
                round(
                    total,
                    6,
                ),

            "average":
                round(
                    total
                    /
                    len(values),
                    6,
                ),

            "maximum":
                round(
                    max(values),
                    6,
                ),
        }

    # ========================================================
    # REVIEW
    # ========================================================

    def review_statistics(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            events = list(
                self._events
            )

        reviewed = [

            event
            for event in events

            if (
                event.decision
                == "REVIEW"
                or
                event.review_id
                is not None
                or
                event.review_status
                is not None
            )
        ]

        pending = sum(

            str(
                event.review_status
            ).upper()
            == "PENDING"

            for event in reviewed
        )

        resolved = sum(

            str(
                event.review_status
            ).upper()
            == "RESOLVED"

            for event in reviewed
        )

        return {

            "total_review_events":
                len(reviewed),

            "pending":
                pending,

            "resolved":
                resolved,

            "review_rate":
                round(
                    (
                        len(reviewed)
                        /
                        self.total_requests
                        *
                        100.0
                    )
                    if self.total_requests
                    else 0.0,
                    2,
                ),
        }

    # ========================================================
    # GOVERNANCE STATISTICS
    # ========================================================

    def governance_statistics(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            events = list(
                self._events
            )

        if not events:

            return {

                "request_decision":
                    None,

                "response_decision":
                    None,

                "confidence":
                    None,
            }

        latest = events[
            -1
        ]

        request = (
            latest.request_governance
            or {}
        )

        response = (
            latest.response_governance
            or {}
        )

        confidence_values = []

        for event in events:

            for governance in (
                event.request_governance,
                event.response_governance,
            ):

                if not isinstance(
                    governance,
                    dict,
                ):

                    continue

                value = governance.get(
                    "confidence"
                )

                try:

                    value = float(
                        value
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    continue

                if (
                    0.0
                    <= value
                    <= 1.0
                ):

                    confidence_values.append(
                        value
                    )

        average_confidence = (

            round(
                sum(
                    confidence_values
                )
                /
                len(
                    confidence_values
                ),
                4,
            )

            if confidence_values

            else None
        )

        return {

            "request_decision":
                request.get(
                    "decision"
                ),

            "response_decision":
                response.get(
                    "decision"
                ),

            "confidence":
                average_confidence,
        }

    # ========================================================
    # RISK DIMENSIONS
    # ========================================================

    def risk_dimension_statistics(
        self,
    ) -> Dict[str, float]:

        dimensions = {

            "security": [],

            "privacy": [],

            "bias": [],

            "factuality": [],

            "cost": [],
        }

        with self._lock:

            events = list(
                self._events
            )

        for event in events:

            for governance in (

                event.request_governance,

                event.response_governance,

            ):

                if not isinstance(
                    governance,
                    dict,
                ):

                    continue

                agents = _safe_list(
                    governance.get(
                        "agents",
                        [],
                    )
                )

                for agent in agents:

                    if not isinstance(
                        agent,
                        dict,
                    ):

                        continue

                    name = str(
                        agent.get(
                            "agent",
                            agent.get(
                                "agent_name",
                                agent.get(
                                    "name",
                                    "",
                                ),
                            ),
                        )
                    ).lower().strip()

                    if "security" in name:

                        key = "security"

                    elif "privacy" in name:

                        key = "privacy"

                    elif "bias" in name:

                        key = "bias"

                    elif "factual" in name:

                        key = "factuality"

                    elif "cost" in name:

                        key = "cost"

                    else:

                        continue

                    value = _safe_number(
                        agent.get(
                            "risk",
                            agent.get(
                                "risk_score",
                                0.0,
                            ),
                        )
                    )

                    dimensions[
                        key
                    ].append(
                        _clamp01(
                            value
                        )
                    )

        return {

            name:

                round(
                    sum(values)
                    /
                    len(values),
                    4,
                )

                if values

                else 0.0

            for name, values
            in dimensions.items()
        }

    # ========================================================
    # FACTUALITY
    # ========================================================

    def factuality_statistics(
        self,
    ) -> Dict[str, Any]:

        """
        Aggregate factuality telemetry.

        Each request is counted at most once.

        Preferred source:

            event.factuality

        Compatibility fallback:

            response_governance
                -> factuality agent

            request_governance
                -> factuality agent
        """

        requests_checked = 0

        claims = 0

        verified = 0

        failed = 0

        unknown = 0

        status_counts: Dict[
            str,
            int
        ] = {}

        with self._lock:

            events = list(
                self._events
            )

        for event in events:

            # ------------------------------------------------
            # FIRST: normalized factuality stored on event
            # ------------------------------------------------

            factuality = _safe_dict(
                event.factuality
            )

            # ------------------------------------------------
            # FALLBACK: extract directly from governance
            # ------------------------------------------------

            if not factuality:

                factuality = (
                    MetricEvent._extract_factuality(
                        request_governance=(
                            event.request_governance
                        ),
                        response_governance=(
                            event.response_governance
                        ),
                        result={},
                    )
                )

            # ------------------------------------------------
            # No factuality layer for this event.
            # ------------------------------------------------

            if not factuality:

                continue

            factuality = (
                MetricEvent._normalize_factuality(
                    factuality
                )
            )

            if not factuality:

                continue

            # ------------------------------------------------
            # REQUESTS CHECKED
            # ------------------------------------------------

            explicit_checked = (
                factuality.get(
                    "requests_checked",
                    None,
                )
            )

            if explicit_checked is not None:

                requests_checked += max(
                    _safe_integer(
                        explicit_checked
                    ),
                    0,
                )

            else:

                requests_checked += 1

            # ------------------------------------------------
            # CLAIMS
            # ------------------------------------------------

            claims += max(
                _safe_integer(
                    factuality.get(
                        "claims",
                        factuality.get(
                            "claims_count",
                            factuality.get(
                                "total_claims",
                                0,
                            ),
                        ),
                    )
                ),
                0,
            )

            # ------------------------------------------------
            # VERIFIED
            # ------------------------------------------------

            verified += max(
                _safe_integer(
                    factuality.get(
                        "verified",
                        factuality.get(
                            "verified_count",
                            0,
                        ),
                    )
                ),
                0,
            )

            # ------------------------------------------------
            # FAILED
            # ------------------------------------------------

            failed += max(
                _safe_integer(
                    factuality.get(
                        "failed",
                        factuality.get(
                            "failed_count",
                            0,
                        ),
                    )
                ),
                0,
            )

            # ------------------------------------------------
            # UNKNOWN
            # ------------------------------------------------

            unknown += max(
                _safe_integer(
                    factuality.get(
                        "unknown",
                        factuality.get(
                            "unknown_count",
                            0,
                        ),
                    )
                ),
                0,
            )

            # ------------------------------------------------
            # STATUS COUNTS
            # ------------------------------------------------

            statuses = _safe_dict(
                factuality.get(
                    "status_counts",
                    {},
                )
            )

            if statuses:

                for status, count in (
                    statuses.items()
                ):

                    key = str(
                        status
                    ).strip().upper()

                    if not key:

                        continue

                    status_counts[
                        key
                    ] = (

                        status_counts.get(
                            key,
                            0,
                        )

                        +
                        max(
                            _safe_integer(
                                count
                            ),
                            0,
                        )
                    )

            else:

                status = factuality.get(
                    "status",
                    factuality.get(
                        "factuality_status",
                        factuality.get(
                            "verification_status",
                            None,
                        ),
                    ),
                )

                if status:

                    key = str(
                        status
                    ).strip().upper()

                    if key:

                        status_counts[
                            key
                        ] = (
                            status_counts.get(
                                key,
                                0,
                            )
                            + 1
                        )

        return {

            "requests_checked":
                requests_checked,

            "claims":
                claims,

            "verified":
                verified,

            "failed":
                failed,

            "unknown":
                unknown,

            "status_counts":
                status_counts,
        }

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def snapshot(
        self,
    ) -> Dict[str, Any]:

        return {

            "total_requests":
                self.total_requests,

            "decisions":
                self.decision_counts(),

            "decision_rates":
                self.decision_rates(),

            "risk":
                self.risk_statistics(),

            "latency":
                self.latency_statistics(),

            "cost":
                self.cost_statistics(),

            "reviews":
                self.review_statistics(),

            "factuality":
                self.factuality_statistics(),

            "governance":
                self.governance_statistics(),

            "risk_dimensions":
                self.risk_dimension_statistics(),
        }

    # ========================================================
    # EVENTS
    # ========================================================

    def events(
        self,
    ) -> List[MetricEvent]:

        with self._lock:

            return list(
                self._events
            )

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
    ) -> None:

        with self._lock:

            self._events.clear()


# ============================================================
# METRICS AGGREGATOR
# ============================================================

class MetricsAggregator:

    """
    Converts the raw MetricsCollector snapshot into the
    structure expected by /api/metrics/dashboard.

    Existing dashboard structure:

        system
        governance
        risk
        performance
        cost
        human_review
        factuality
        decisions
    """

    def __init__(
        self,
        collector: MetricsCollector,
    ):

        self.collector = collector

    # ========================================================
    # DASHBOARD
    # ========================================================

    def dashboard(
        self,
    ) -> Dict[str, Any]:

        snapshot = (
            self.collector.snapshot()
        )

        decisions = (
            snapshot.get(
                "decisions",
                {},
            )
            or {}
        )

        decision_rates = (
            snapshot.get(
                "decision_rates",
                {},
            )
            or {}
        )

        risk = (
            snapshot.get(
                "risk",
                {},
            )
            or {}
        )

        risk_dimensions = (
            snapshot.get(
                "risk_dimensions",
                {},
            )
            or {}
        )

        latency = (
            snapshot.get(
                "latency",
                {},
            )
            or {}
        )

        cost = (
            snapshot.get(
                "cost",
                {},
            )
            or {}
        )

        reviews = (
            snapshot.get(
                "reviews",
                {},
            )
            or {}
        )

        governance = (
            snapshot.get(
                "governance",
                {},
            )
            or {}
        )

        factuality = (
            snapshot.get(
                "factuality",
                {},
            )
            or {}
        )

        # ----------------------------------------------------
        # SYSTEM
        # ----------------------------------------------------

        system = {

            "requests":
                snapshot.get(
                    "total_requests",
                    0,
                ),

            "status":
                (
                    "ACTIVE"
                    if snapshot.get(
                        "total_requests",
                        0,
                    )
                    > 0

                    else
                    "READY"
                ),
        }

        # ----------------------------------------------------
        # GOVERNANCE
        # ----------------------------------------------------

        governance_data = {

            "allow_rate":
                decision_rates.get(
                    "ALLOW",
                    0.0,
                ),

            "review_rate":
                decision_rates.get(
                    "REVIEW",
                    0.0,
                ),

            "block_rate":
                decision_rates.get(
                    "BLOCK",
                    0.0,
                ),

            "edit_rate":
                decision_rates.get(
                    "EDIT",
                    0.0,
                ),

            "request_decision":
                governance.get(
                    "request_decision"
                ),

            "response_decision":
                governance.get(
                    "response_decision"
                ),

            "confidence":
                governance.get(
                    "confidence"
                ),
        }

        # ----------------------------------------------------
        # RISK
        # ----------------------------------------------------

        risk_data = {

            "average":
                risk.get(
                    "average",
                    0.0,
                ),

            "minimum":
                risk.get(
                    "minimum",
                    0.0,
                ),

            "maximum":
                risk.get(
                    "maximum",
                    0.0,
                ),

            "high_risk_rate":
                risk.get(
                    "high_risk_rate",
                    0.0,
                ),

            "security":
                risk_dimensions.get(
                    "security",
                    0.0,
                ),

            "privacy":
                risk_dimensions.get(
                    "privacy",
                    0.0,
                ),

            "bias":
                risk_dimensions.get(
                    "bias",
                    0.0,
                ),

            "factuality":
                risk_dimensions.get(
                    "factuality",
                    0.0,
                ),

            "cost":
                risk_dimensions.get(
                    "cost",
                    0.0,
                ),
        }

        # ----------------------------------------------------
        # PERFORMANCE
        # ----------------------------------------------------

        performance = {

            "average_ms":
                latency.get(
                    "average_ms",
                    0.0,
                ),

            "minimum_ms":
                latency.get(
                    "minimum_ms",
                    0.0,
                ),

            "maximum_ms":
                latency.get(
                    "maximum_ms",
                    0.0,
                ),

            "model_average_ms":
                latency.get(
                    "model_average_ms",
                    0.0,
                ),

            "model_minimum_ms":
                latency.get(
                    "model_minimum_ms",
                    0.0,
                ),

            "model_maximum_ms":
                latency.get(
                    "model_maximum_ms",
                    0.0,
                ),
        }

        # ----------------------------------------------------
        # COST
        # ----------------------------------------------------

        cost_data = {

            "total":
                cost.get(
                    "total",
                    0.0,
                ),

            "average":
                cost.get(
                    "average",
                    0.0,
                ),

            "maximum":
                cost.get(
                    "maximum",
                    0.0,
                ),
        }

        # ----------------------------------------------------
        # HUMAN REVIEW
        # ----------------------------------------------------

        human_review = {

            "total_review_events":
                reviews.get(
                    "total_review_events",
                    0,
                ),

            "pending":
                reviews.get(
                    "pending",
                    0,
                ),

            "resolved":
                reviews.get(
                    "resolved",
                    0,
                ),

            "review_rate":
                reviews.get(
                    "review_rate",
                    0.0,
                ),
        }

        # ----------------------------------------------------
        # FACTUALITY
        # ----------------------------------------------------

        factuality_data = {

            "requests_checked":
                factuality.get(
                    "requests_checked",
                    0,
                ),

            "claims":
                factuality.get(
                    "claims",
                    0,
                ),

            "verified":
                factuality.get(
                    "verified",
                    0,
                ),

            "failed":
                factuality.get(
                    "failed",
                    0,
                ),

            "unknown":
                factuality.get(
                    "unknown",
                    0,
                ),

            "status_counts":
                factuality.get(
                    "status_counts",
                    {},
                ),
        }

        # ----------------------------------------------------
        # FINAL DASHBOARD STRUCTURE
        # ----------------------------------------------------

        return {

            "system":
                system,

            "governance":
                governance_data,

            "risk":
                risk_data,

            "performance":
                performance,

            "cost":
                cost_data,

            "human_review":
                human_review,

            "factuality":
                factuality_data,

            "decisions":
                decisions,
        }