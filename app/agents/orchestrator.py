import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from typing import (
    Any,
    Dict,
    List,
    Tuple,
)


class AgentOrchestrator:
    """
    Multi-agent governance orchestrator.

    Responsibilities:

        - Parallel execution of independent agents
        - Unified risk aggregation
        - Confidence aggregation
        - Fail-safe agent execution
        - Per-agent latency
        - Critical-agent blocking
        - Request inspection
        - Response inspection
        - Stable governance response schema
        - Round 2 observability support

    IMPORTANT:

    The orchestrator always returns a stable response structure.

    Every successful inspection contains:

        decision
        phase
        risk_score
        confidence
        minimum_agent_confidence
        status_counts
        risk_contributors
        critical_block
        agents
        agent_count
        latency_ms
        sequential_agent_latency_ms
        slowest_agent_latency_ms
        parallel_efficiency
    """

    # ========================================================
    # CRITICAL BLOCK AGENTS
    # ========================================================

    CRITICAL_BLOCK_AGENTS = {
        "security",
        "privacy",
        "cost",
    }

    # ========================================================
    # REVIEW STATUSES
    # ========================================================

    REVIEW_STATUSES = {
        "REVIEW",
        "UNKNOWN",
    }

    # ========================================================
    # CONSTRUCTOR
    # ========================================================

    def __init__(
        self,
        security_agent,
        privacy_agent,
        bias_agent,
        factuality_agent=None,
        cost_agent=None,
        max_workers=5,
    ):

        self.security_agent = (
            security_agent
        )

        self.privacy_agent = (
            privacy_agent
        )

        self.bias_agent = (
            bias_agent
        )

        self.factuality_agent = (
            factuality_agent
        )

        self.cost_agent = (
            cost_agent
        )

        self.max_workers = max(
            1,
            int(max_workers),
        )

    # ========================================================
    # PUBLIC REQUEST INSPECTION
    # ========================================================

    def inspect_request(
        self,
        prompt: str,
    ) -> Dict[str, Any]:

        started = (
            time.perf_counter()
        )

        jobs = [
            (
                "security",
                self.security_agent.scan,
                (prompt,),
            ),
            (
                "privacy",
                self.privacy_agent.scan,
                (prompt,),
            ),
            (
                "bias",
                self.bias_agent.scan,
                (prompt,),
            ),
        ]

        # ----------------------------------------------------
        # Cost is optional.
        # ----------------------------------------------------

        if self.cost_agent:

            jobs.append(
                (
                    "cost",
                    self.cost_agent.scan,
                    (prompt,),
                )
            )

        results = (
            self._run_parallel(
                jobs
            )
        )

        return self._aggregate(
            results,
            started,
            phase="REQUEST",
        )

    # ========================================================
    # PUBLIC RESPONSE INSPECTION
    # ========================================================

    def inspect_response(
        self,
        response: str,
    ) -> Dict[str, Any]:

        started = (
            time.perf_counter()
        )

        jobs = [
            (
                "privacy",
                self.privacy_agent.scan,
                (response,),
            ),
            (
                "bias",
                self.bias_agent.scan,
                (response,),
            ),
        ]

        # ----------------------------------------------------
        # Factuality is deliberately kept separate because
        # it may involve retrieval / evidence verification.
        # ----------------------------------------------------

        if self.factuality_agent:

            jobs.append(
                (
                    "factuality",
                    self.factuality_agent.scan,
                    (response,),
                )
            )

        results = (
            self._run_parallel(
                jobs
            )
        )

        return self._aggregate(
            results,
            started,
            phase="RESPONSE",
        )

    # ========================================================
    # PARALLEL EXECUTION
    # ========================================================

    def _run_parallel(
        self,
        jobs: List[
            Tuple[
                str,
                Any,
                Tuple[Any, ...],
            ]
        ],
    ):

        results = []

        # ----------------------------------------------------
        # Defensive handling for empty job lists.
        # ----------------------------------------------------

        if not jobs:

            return results

        worker_count = min(
            self.max_workers,
            len(jobs),
        )

        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="cp-agent",
        ) as executor:

            futures = {
                executor.submit(
                    function,
                    *args,
                ): name

                for name, function, args
                in jobs
            }

            for future in as_completed(
                futures
            ):

                agent_name = (
                    futures[future]
                )

                try:

                    result = (
                        future.result()
                    )

                    # ------------------------------------------------
                    # Defensive result validation.
                    #
                    # A governance agent must return an AgentResult-like
                    # object. If it returns None or another unexpected
                    # value, convert that failure into a safe REVIEW.
                    # ------------------------------------------------

                    if result is None:

                        from app.agents.base import (
                            AgentResult,
                        )

                        result = AgentResult(

                            agent=agent_name,

                            risk=0.90,

                            status="REVIEW",

                            reason=(
                                f"{agent_name} "
                                "agent returned "
                                "no result."
                            ),

                            confidence=0.10,

                            signals={
                                "execution_failure": True,
                                "empty_result": True,
                            },

                            latency_ms=0.0,
                        )

                    results.append(
                        result
                    )

                except Exception as exc:

                    # ------------------------------------------------
                    # Fail closed.
                    #
                    # If a governance agent itself crashes, we don't
                    # silently allow the request.
                    # ------------------------------------------------

                    from app.agents.base import (
                        AgentResult,
                    )

                    results.append(
                        AgentResult(

                            agent=agent_name,

                            risk=0.90,

                            status="REVIEW",

                            reason=(
                                f"{agent_name} "
                                "agent failed safely: "
                                f"{type(exc).__name__}"
                            ),

                            confidence=0.10,

                            signals={
                                "error": str(exc),
                                "execution_failure": True,
                            },

                            latency_ms=0.0,
                        )
                    )

        # ----------------------------------------------------
        # Keep deterministic ordering for logs/UI/tests.
        # ----------------------------------------------------

        results.sort(
            key=lambda result: (
                str(
                    getattr(
                        result,
                        "agent",
                        "",
                    )
                )
            )
        )

        return results

    # ========================================================
    # AGENT SERIALIZATION
    # ========================================================

    @staticmethod
    def _serialize_agent(
        result,
    ) -> Dict[str, Any]:

        """
        Convert an AgentResult-like object into a dictionary.

        This is deliberately defensive so one malformed agent result
        cannot remove the complete `agents` list from the governance
        response.
        """

        # ----------------------------------------------------
        # Normal AgentResult path.
        # ----------------------------------------------------

        try:

            if hasattr(
                result,
                "to_dict",
            ):

                serialized = (
                    result.to_dict()
                )

                if isinstance(
                    serialized,
                    dict,
                ):

                    return serialized

        except Exception as exc:

            return {

                "agent":
                    str(
                        getattr(
                            result,
                            "agent",
                            "unknown",
                        )
                    ),

                "risk": 0.90,

                "status": "REVIEW",

                "reason": (
                    "Agent result "
                    "serialization failed."
                ),

                "confidence": 0.10,

                "signals": {
                    "serialization_error":
                        str(exc),
                },

                "latency_ms": 0.0,
            }

        # ----------------------------------------------------
        # Generic object fallback.
        # ----------------------------------------------------

        return {

            "agent":
                str(
                    getattr(
                        result,
                        "agent",
                        "unknown",
                    )
                ),

            "risk":
                float(
                    getattr(
                        result,
                        "risk",
                        0.0,
                    )
                    or 0.0
                ),

            "status":
                str(
                    getattr(
                        result,
                        "status",
                        "UNKNOWN",
                    )
                    or "UNKNOWN"
                ).upper(),

            "reason":
                str(
                    getattr(
                        result,
                        "reason",
                        "",
                    )
                    or ""
                ),

            "confidence":
                float(
                    getattr(
                        result,
                        "confidence",
                        0.0,
                    )
                    or 0.0
                ),

            "signals":
                getattr(
                    result,
                    "signals",
                    {},
                )
                or {},

            "latency_ms":
                float(
                    getattr(
                        result,
                        "latency_ms",
                        0.0,
                    )
                    or 0.0
                ),
        }

    # ========================================================
    # AGGREGATION
    # ========================================================

    def _aggregate(
        self,
        results,
        started,
        phase="REQUEST",
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # Defensive normalization.
        # ----------------------------------------------------

        if results is None:

            results = []

        # ----------------------------------------------------
        # Serialize every agent.
        #
        # IMPORTANT:
        # `agents` is ALWAYS present.
        # ----------------------------------------------------

        serialized = []

        for result in results:

            try:

                serialized.append(
                    self._serialize_agent(
                        result
                    )
                )

            except Exception as exc:

                serialized.append({

                    "agent":
                        "unknown",

                    "risk": 0.90,

                    "status":
                        "REVIEW",

                    "reason": (
                        "Unknown governance "
                        "agent serialization "
                        "failure."
                    ),

                    "confidence": 0.10,

                    "signals": {
                        "error":
                            str(exc),
                    },

                    "latency_ms": 0.0,
                })

        # ----------------------------------------------------
        # Risk
        # ----------------------------------------------------

        risks = []

        for result in results:

            try:

                risks.append(
                    float(
                        getattr(
                            result,
                            "risk",
                            0.0,
                        )
                        or 0.0
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                risks.append(
                    0.0
                )

        max_risk = (
            max(risks)
            if risks
            else 0.0
        )

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        confidences = []

        for result in results:

            try:

                confidences.append(
                    float(
                        getattr(
                            result,
                            "confidence",
                            0.0,
                        )
                        or 0.0
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                confidences.append(
                    0.0
                )

        avg_confidence = (

            sum(confidences)
            /
            len(confidences)

            if confidences

            else 0.0
        )

        min_confidence = (

            min(confidences)

            if confidences

            else 0.0
        )

        # ----------------------------------------------------
        # Status counts
        # ----------------------------------------------------

        status_counts = {}

        for result in results:

            status = str(
                getattr(
                    result,
                    "status",
                    "UNKNOWN",
                )
                or "UNKNOWN"
            ).upper()

            status_counts[status] = (
                status_counts.get(
                    status,
                    0,
                )
                + 1
            )

        # ----------------------------------------------------
        # Critical BLOCK
        #
        # Security / privacy / cost are hard controls.
        # Bias and factuality normally lead to REVIEW unless
        # a future policy explicitly changes that behaviour.
        # ----------------------------------------------------

        critical_block = any(

            str(
                getattr(
                    result,
                    "status",
                    "",
                )
                or ""
            ).upper()
            == "BLOCK"

            and

            str(
                getattr(
                    result,
                    "agent",
                    "",
                )
                or ""
            ).lower()
            in self.CRITICAL_BLOCK_AGENTS

            for result in results
        )

        any_block = any(

            str(
                getattr(
                    result,
                    "status",
                    "",
                )
                or ""
            ).upper()
            == "BLOCK"

            for result in results
        )

        any_review = any(

            str(
                getattr(
                    result,
                    "status",
                    "",
                )
                or ""
            ).upper()
            in self.REVIEW_STATUSES

            for result in results
        )

        any_modify = any(

            str(
                getattr(
                    result,
                    "status",
                    "",
                )
                or ""
            ).upper()
            == "MODIFY"

            for result in results
        )

        # ----------------------------------------------------
        # Decision
        # ----------------------------------------------------

        if critical_block:

            decision = "BLOCK"

        elif any_block:

            decision = "BLOCK"

        elif any_review:

            decision = "REVIEW"

        elif any_modify:

            decision = "MODIFY"

        else:

            decision = "ALLOW"

        # ----------------------------------------------------
        # Latency
        #
        # With parallel execution, total agent latency is
        # approximately bounded by the slowest agent rather
        # than the sum of all agent latencies.
        # ----------------------------------------------------

        agent_latencies = []

        for result in results:

            try:

                agent_latencies.append(
                    float(
                        getattr(
                            result,
                            "latency_ms",
                            0.0,
                        )
                        or 0.0
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                agent_latencies.append(
                    0.0
                )

        sequential_latency = (
            sum(
                agent_latencies
            )
        )

        slowest_agent_latency = (

            max(
                agent_latencies
            )

            if agent_latencies

            else 0.0
        )

        total_latency = (
            time.perf_counter()
            - started
        ) * 1000

        # ----------------------------------------------------
        # Risk contributors
        # ----------------------------------------------------

        risk_contributors = []

        for result in results:

            try:

                risk = float(
                    getattr(
                        result,
                        "risk",
                        0.0,
                    )
                    or 0.0
                )

            except (
                TypeError,
                ValueError,
            ):

                risk = 0.0

            if risk > 0.10:

                risk_contributors.append({

                    "agent":
                        str(
                            getattr(
                                result,
                                "agent",
                                "unknown",
                            )
                        ),

                    "risk":
                        round(
                            risk,
                            4,
                        ),

                    "status":
                        str(
                            getattr(
                                result,
                                "status",
                                "UNKNOWN",
                            )
                            or "UNKNOWN"
                        ).upper(),
                })

        risk_contributors.sort(
            key=lambda item:
                item["risk"],
            reverse=True,
        )

        # ----------------------------------------------------
        # Governance efficiency
        # ----------------------------------------------------

        if total_latency > 0:

            parallel_efficiency = min(

                1.0,

                sequential_latency
                /
                total_latency,
            )

        else:

            parallel_efficiency = 1.0

        # ----------------------------------------------------
        # STABLE RESPONSE CONTRACT
        # ----------------------------------------------------
        #
        # Do NOT remove fields from this structure.
        #
        # Existing tests and downstream monitoring rely on
        # the `agents` list.
        # ----------------------------------------------------

        return {

            "decision":
                decision,

            "phase":
                phase,

            "risk_score":
                round(
                    float(
                        max_risk
                    ),
                    4,
                ),

            "confidence":
                round(
                    float(
                        avg_confidence
                    ),
                    4,
                ),

            "minimum_agent_confidence":
                round(
                    float(
                        min_confidence
                    ),
                    4,
                ),

            "status_counts":
                status_counts,

            "risk_contributors":
                risk_contributors,

            "critical_block":
                critical_block,

            # IMPORTANT:
            # Existing contract preserved.
            "agents":
                serialized,

            "agent_count":
                len(
                    serialized
                ),

            "latency_ms":
                round(
                    total_latency,
                    3,
                ),

            "sequential_agent_latency_ms":
                round(
                    sequential_latency,
                    3,
                ),

            "slowest_agent_latency_ms":
                round(
                    slowest_agent_latency,
                    3,
                ),

            "parallel_efficiency":
                round(
                    float(
                        parallel_efficiency
                    ),
                    4,
                ),
        }