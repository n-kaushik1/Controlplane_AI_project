import time

from typing import Any, Dict, Optional

from app.gateway.model_gateway import ModelGateway
from app.policies import PolicyEngine


class RequestGateway:
    """
    Main ControlPlane runtime gateway.

    High-level architecture:

        User Request
             |
             v
       Input Validation
             |
             v
      PRE-REQUEST GOVERNANCE
             |
       +-----+-----+
       |           |
    Security    Privacy
       |           |
       +-----+-----+
             |
          Bias/Cost
             |
             v
        Policy Engine
             |
       ALLOW / MODIFY /
       REVIEW / BLOCK
             |
             v
        Model Gateway
             |
             v
        Model Response
             |
             v
     POST-RESPONSE GOVERNANCE
             |
       +-----+------+------+-----+
       |     |      |      |     |
     Fact  Bias  Privacy Security ...
       |     |      |      |
       +-----+------+------+-----+
             |
             v
       Final Policy
             |
             v
    ALLOW / MODIFY / REVIEW / BLOCK
             |
             v
      Audit + Metrics

    The gateway deliberately does not know
    how individual agents work.

    It only consumes standardized orchestrator
    results.
    """

    def __init__(
        self,
        model_provider,
        orchestrator=None,
        policy_engine=None,
        audit_logger=None,
        metrics_collector=None,
    ):

        if model_provider is None:

            raise ValueError(
                "model_provider is required."
            )

        # ========================================================
        # MODEL GATEWAY
        # ========================================================

        if isinstance(
            model_provider,
            ModelGateway
        ):

            self.model_gateway = (
                model_provider
            )

        else:

            self.model_gateway = (
                ModelGateway(
                    model_provider
                )
            )

        # Preserve original public attribute.
        self.model_provider = (
            model_provider
        )

        self.orchestrator = (
            orchestrator
        )

        self.policy_engine = (
            policy_engine
        )

        self.audit_logger = (
            audit_logger
        )

        self.metrics_collector = (
            metrics_collector
        )

    # ============================================================
    # PUBLIC API
    # ============================================================

    def process(
        self,
        prompt: str,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
        risk_profile: Optional[str] = None,
    ) -> Dict[str, Any]:

        started = time.perf_counter()

        metadata = dict(
            metadata or {}
        )

        # ========================================================
        # GOVERNANCE PROFILE
        # ========================================================

        if risk_profile is not None:

            metadata[
                "risk_profile"
            ] = str(
                risk_profile
            ).strip()

        events = [
            "REQUEST RECEIVED"
        ]

        # ========================================================
        # REQUEST ID
        # ========================================================

        request_id = metadata.get(
            "request_id"
        )

        if request_id is None:

            request_id = (
                f"req-"
                f"{int(time.time() * 1000000)}"
            )

        metadata[
            "request_id"
        ] = request_id

        # ========================================================
        # INPUT VALIDATION
        # ========================================================

        if not isinstance(
            prompt,
            str
        ):

            return self._blocked_result(
                prompt=str(prompt),
                reason=(
                    "Prompt must be a string."
                ),
                events=events,
                started=started,
                metadata=metadata,
            )

        prompt = prompt.strip()

        if not prompt:

            return self._blocked_result(
                prompt=prompt,
                reason="Empty prompt.",
                events=events,
                started=started,
                metadata=metadata,
            )

        events.append(
            "INPUT VALIDATED | "
            f"chars={len(prompt)}"
        )

        # ========================================================
        # PRE-REQUEST GOVERNANCE
        # ========================================================

        request_inspection = {}

        if self.orchestrator:

            try:

                request_inspection = (
                    self.orchestrator
                    .inspect_request(
                        prompt
                    )
                )

                events.append(
                    "PRE-GOVERNANCE: "
                    "request agents completed"
                )

            except Exception as exc:

                events.append(
                    "PRE-GOVERNANCE: "
                    "orchestrator failure"
                )

                return self._blocked_result(
                    prompt=prompt,
                    reason=(
                        "Request governance "
                        "failed safely: "
                        f"{type(exc).__name__}"
                    ),
                    events=events,
                    started=started,
                    metadata=metadata,
                    request_inspection={
                        "decision": "BLOCK",
                        "error": str(exc),
                    },
                )

        else:

            events.append(
                "PRE-GOVERNANCE: "
                "no orchestrator configured"
            )

        # ========================================================
        # PRE DECISION
        # ========================================================

        pre_decision = (
            self._extract_decision(
                request_inspection
            )
        )

        events.append(
            f"PRE-DECISION: {pre_decision}"
        )

        # ========================================================
        # HARD BLOCK
        # ========================================================

        if pre_decision == "BLOCK":

            events.append(
                "MODEL INVOCATION: SKIPPED"
            )

            result = self._build_result(

                prompt=prompt,

                output=(
                    "🚫 ControlPlane blocked "
                    "this request before "
                    "model execution."
                ),

                action="BLOCK",

                request_inspection=(
                    request_inspection
                ),

                response_inspection={},

                events=events,

                started=started,

                metadata=metadata,

                policy_decision="BLOCK",
            )

            self._audit(result)

            return result

        # ========================================================
        # MODEL EXECUTION
        # ========================================================

        model_started = (
            time.perf_counter()
        )

        events.append(
            "MODEL INVOCATION: started"
        )

        try:

            try:

                model_response = (
                    self.model_gateway
                    .generate(
                        prompt
                    )
                )

            except AttributeError as exc:

                error_text = str(
                    exc
                )

                if (
                    "'str' object has no attribute "
                    "'get'"
                    not in error_text
                ):

                    raise

                events.append(
                    "MODEL GATEWAY: "
                    "legacy string provider fallback"
                )

                model_response = (
                    self._invoke_legacy_provider(
                        prompt
                    )
                )

        except Exception as exc:

            events.append(
                "MODEL INVOCATION: FAILED"
            )

            result = self._build_result(

                prompt=prompt,

                output=(
                    "⚠️ ControlPlane could "
                    "not safely complete "
                    "the model request."
                ),

                action="BLOCK",

                request_inspection=(
                    request_inspection
                ),

                response_inspection={},

                events=events,

                started=started,

                metadata=metadata,

                model_error=str(exc),

                policy_decision="BLOCK",
            )

            self._audit(result)

            return result

        model_latency = (
            time.perf_counter()
            - model_started
        ) * 1000

        events.append(
            "MODEL INVOCATION: completed | "
            f"{model_latency:.2f} ms"
        )

        # ========================================================
        # MODEL RESPONSE NORMALIZATION
        # ========================================================

        response_text = (
            self._extract_response(
                model_response
            )
        )

        # ========================================================
        # MODEL USAGE / COST
        # ========================================================

        model_usage = (
            self._extract_model_usage(
                model_response
            )
        )

        if not response_text:

            events.append(
                "MODEL RESPONSE: empty"
            )

            result = self._build_result(

                prompt=prompt,

                output=(
                    "⚠️ The model returned "
                    "an empty response."
                ),

                action="BLOCK",

                request_inspection=(
                    request_inspection
                ),

                response_inspection={},

                events=events,

                started=started,

                metadata=metadata,

                model_latency_ms=(
                    model_latency
                ),

                model_usage=model_usage,

                policy_decision="BLOCK",
            )

            self._audit(result)

            return result

        # ========================================================
        # POST-RESPONSE GOVERNANCE
        # ========================================================

        response_inspection = {}

        if self.orchestrator:

            try:

                response_inspection = (
                    self.orchestrator
                    .inspect_response(
                        response_text
                    )
                )

                events.append(
                    "POST-GOVERNANCE: "
                    "response agents completed"
                )

            except Exception as exc:

                events.append(
                    "POST-GOVERNANCE: "
                    "orchestrator failure"
                )

                result = self._build_result(

                    prompt=prompt,

                    output=(
                        "⚠️ ControlPlane could "
                        "not safely validate "
                        "the model response."
                    ),

                    action="BLOCK",

                    request_inspection=(
                        request_inspection
                    ),

                    response_inspection={
                        "decision": "BLOCK",
                        "error": str(exc),
                    },

                    events=events,

                    started=started,

                    metadata=metadata,

                    model_latency_ms=(
                        model_latency
                    ),

                    model_usage=model_usage,

                    policy_decision="BLOCK",
                )

                self._audit(result)

                return result

        else:

            events.append(
                "POST-GOVERNANCE: "
                "no orchestrator configured"
            )

        # ========================================================
        # POST DECISION
        # ========================================================

        post_decision = (
            self._extract_decision(
                response_inspection
            )
        )

        events.append(
            f"POST-DECISION: {post_decision}"
        )

        # ========================================================
        # POLICY ENGINE
        # ========================================================

        policy_decision = "ALLOW"

        if self.policy_engine:

            try:

                policy_decision = (
                    self._evaluate_policy(
                        prompt=prompt,
                        response=response_text,
                        request_inspection=(
                            request_inspection
                        ),
                        response_inspection=(
                            response_inspection
                        ),
                        metadata=metadata,
                    )
                )

                events.append(
                    "POLICY ENGINE: "
                    f"{policy_decision}"
                )

            except Exception as exc:

                events.append(
                    "POLICY ENGINE: failure"
                )

                result = self._build_result(

                    prompt=prompt,

                    output=(
                        "⚠️ ControlPlane "
                        "could not safely "
                        "evaluate policy."
                    ),

                    action="BLOCK",

                    request_inspection=(
                        request_inspection
                    ),

                    response_inspection=(
                        response_inspection
                    ),

                    events=events,

                    started=started,

                    metadata=metadata,

                    model_latency_ms=(
                        model_latency
                    ),

                    model_usage=model_usage,

                    policy_error=str(exc),

                    policy_decision="BLOCK",
                )

                self._audit(result)

                return result

        # ========================================================
        # FINAL DECISION
        # ========================================================

        final_action = (
            self._final_decision(
                pre_decision,
                post_decision,
                policy_decision,
            )
        )

        events.append(
            f"FINAL DECISION: {final_action}"
        )

        # ========================================================
        # FINAL OUTPUT
        # ========================================================

        if final_action == "ALLOW":

            final_output = (
                response_text
            )

        elif final_action == "MODIFY":

            final_output = (
                response_text
                + "\n\n"
                "🛡️ ControlPlane: "
                "Response modified by "
                "governance controls."
            )

        elif final_action == "REVIEW":

            final_output = (
                "🔎 ControlPlane: "
                "The model response "
                "requires review "
                "before it can be trusted."
            )

        else:

            final_output = (
                "🚫 ControlPlane blocked "
                "the model response "
                "because it failed a "
                "governance check."
            )

        # ========================================================
        # BUILD RESULT
        # ========================================================

        result = self._build_result(

            prompt=prompt,

            output=final_output,

            raw_output=response_text,

            action=final_action,

            request_inspection=(
                request_inspection
            ),

            response_inspection=(
                response_inspection
            ),

            events=events,

            started=started,

            metadata=metadata,

            model_latency_ms=(
                model_latency
            ),

            model_usage=model_usage,

            policy_decision=(
                policy_decision
            ),
        )

        self._audit(result)

        return result

    # ============================================================
    # MODEL USAGE EXTRACTION
    # ============================================================

    @staticmethod
    def _extract_model_usage(
        response
    ) -> Dict[str, Any]:
        """
        Extract normalized model usage.

        ModelGateway calculates cost.
        RequestGateway only transports it.
        """

        def value(
            source,
            key,
            default=None
        ):

            if isinstance(
                source,
                dict
            ):

                return source.get(
                    key,
                    default
                )

            return getattr(
                source,
                key,
                default
            )

        metadata = value(
            response,
            "metadata",
            {}
        )

        if not isinstance(
            metadata,
            dict
        ):

            metadata = {}

        usage = value(
            response,
            "usage",
            {}
        )

        if not isinstance(
            usage,
            dict
        ):

            usage = metadata.get(
                "usage",
                {}
            )

        if not isinstance(
            usage,
            dict
        ):

            usage = {}

        input_tokens = value(
            response,
            "input_tokens",
            None
        )

        if input_tokens is None:

            input_tokens = usage.get(
                "prompt_tokens",
                usage.get(
                    "input_tokens",
                    0
                )
            )

        output_tokens = value(
            response,
            "output_tokens",
            None
        )

        if output_tokens is None:

            output_tokens = usage.get(
                "completion_tokens",
                usage.get(
                    "output_tokens",
                    0
                )
            )

        cost = value(
            response,
            "cost",
            None
        )

        if cost is None:

            cost = metadata.get(
                "cost",
                0.0
            )

        try:

            input_tokens = max(
                int(
                    input_tokens
                    or 0
                ),
                0
            )

        except (
            TypeError,
            ValueError
        ):

            input_tokens = 0

        try:

            output_tokens = max(
                int(
                    output_tokens
                    or 0
                ),
                0
            )

        except (
            TypeError,
            ValueError
        ):

            output_tokens = 0

        try:

            cost = max(
                float(
                    cost
                    or 0.0
                ),
                0.0
            )

        except (
            TypeError,
            ValueError
        ):

            cost = 0.0

        return {

            "input_tokens":
                input_tokens,

            "output_tokens":
                output_tokens,

            "token_count":
                (
                    input_tokens
                    + output_tokens
                ),

            "cost":
                cost,

            "estimated_cost":
                cost,

            "model":
                str(
                    value(
                        response,
                        "model",
                        "unknown"
                    )
                ),

            "provider":
                str(
                    value(
                        response,
                        "provider",
                        "unknown"
                    )
                ),

            "cost_source":
                metadata.get(
                    "cost_source",
                    "unknown"
                ),

            "cost_details":
                metadata.get(
                    "cost_details",
                    {}
                ),
        }

    # ============================================================
    # POLICY ENGINE
    # ============================================================

    def _evaluate_policy(
        self,
        prompt,
        response,
        request_inspection,
        response_inspection,
        metadata,
    ):

        engine = self._select_policy_engine(
            metadata
        )

        if engine is None:

            return "ALLOW"

        # --------------------------------------------------------
        # Native ControlPlane PolicyEngine
        # --------------------------------------------------------

        if isinstance(
            engine,
            PolicyEngine
        ):

            agent_results = (
                self._policy_agent_results(
                    request_inspection,
                    response_inspection,
                )
            )

            uncertainty = (
                self._policy_uncertainty(
                    request_inspection,
                    response_inspection,
                )
            )

            cost = (
                self._policy_cost(
                    request_inspection,
                    response_inspection,
                    metadata,
                )
            )

            verification_status = (
                self._verification_status(
                    response_inspection
                )
            )

            result = engine.evaluate(
                agent_results=agent_results,
                uncertainty=uncertainty,
                cost=cost,
                verification_status=verification_status,
            )

        elif hasattr(
            engine,
            "evaluate"
        ):

            result = engine.evaluate(
                prompt=prompt,
                response=response,
                request_inspection=(
                    request_inspection
                ),
                response_inspection=(
                    response_inspection
                ),
                metadata=metadata,
            )

        elif hasattr(
            engine,
            "decide"
        ):

            result = engine.decide(
                prompt=prompt,
                response=response,
                request_inspection=(
                    request_inspection
                ),
                response_inspection=(
                    response_inspection
                ),
                metadata=metadata,
            )

        else:

            return "ALLOW"

        if isinstance(
            result,
            dict
        ):

            return str(
                result.get(
                    "decision",
                    result.get(
                        "action",
                        "ALLOW"
                    )
                )
            ).upper()

        return str(
            result
        ).upper()

    # ============================================================
    # POLICY ENGINE HELPERS
    # ============================================================

    def _select_policy_engine(
        self,
        metadata: Optional[Dict[str, Any]] = None,
    ):

        metadata = (
            metadata
            if isinstance(metadata, dict)
            else {}
        )

        profile = metadata.get(
            "risk_profile"
        )

        if profile:

            profile_name = str(
                profile
            ).strip()

            if profile_name:

                normalized = (
                    profile_name.lower()
                    .replace("-", "_")
                    .replace(" ", "_")
                )

                if normalized == "regulated_decision":

                    normalized = "regulated"

                configured = self.policy_engine

                configured_policy = getattr(
                    configured,
                    "policy",
                    None
                )

                configured_name = getattr(
                    configured_policy,
                    "name",
                    None
                )

                if (
                    configured is not None
                    and
                    str(configured_name).lower()
                    == normalized
                ):

                    return configured

                return PolicyEngine(
                    normalized
                )

        return self.policy_engine

    @staticmethod
    def _policy_agent_results(
        request_inspection,
        response_inspection,
    ):

        results = []

        for inspection in (
            request_inspection,
            response_inspection,
        ):

            if not isinstance(inspection, dict):

                continue

            agents = inspection.get(
                "agents",
                inspection.get("results", [])
            )

            if not isinstance(agents, list):

                continue

            for agent in agents:

                if isinstance(agent, dict):

                    results.append(agent)

        return results

    @staticmethod
    def _policy_uncertainty(
        request_inspection,
        response_inspection,
    ) -> float:

        values = []

        for inspection in (
            request_inspection,
            response_inspection,
        ):

            if not isinstance(inspection, dict):

                continue

            for key in (
                "uncertainty",
                "uncertainty_score",
            ):

                value = inspection.get(key)

                if value is not None:

                    try:
                        values.append(float(value))
                    except (TypeError, ValueError):
                        pass

            agents = inspection.get(
                "agents",
                inspection.get("results", [])
            )

            if isinstance(agents, list):

                for agent in agents:

                    if not isinstance(agent, dict):
                        continue

                    signals = agent.get("signals", {})

                    if not isinstance(signals, dict):
                        continue

                    for key in (
                        "uncertainty",
                        "uncertainty_score",
                    ):

                        value = signals.get(key)

                        if value is not None:

                            try:
                                values.append(float(value))
                            except (TypeError, ValueError):
                                pass

        if not values:
            return 0.0

        return max(
            0.0,
            min(1.0, max(values))
        )

    @staticmethod
    def _policy_cost(
        request_inspection,
        response_inspection,
        metadata,
    ) -> float:

        values = []

        sources = [
            metadata,
            request_inspection,
            response_inspection,
        ]

        for source in sources:

            if not isinstance(source, dict):
                continue

            for key in (
                "cost",
                "estimated_cost",
            ):

                value = source.get(key)

                if value is not None:

                    try:
                        values.append(float(value))
                    except (TypeError, ValueError):
                        pass

            agents = source.get(
                "agents",
                source.get("results", [])
            )

            if isinstance(agents, list):

                for agent in agents:

                    if not isinstance(agent, dict):
                        continue

                    signals = agent.get("signals", {})

                    if not isinstance(signals, dict):
                        continue

                    for key in (
                        "cost",
                        "estimated_cost",
                    ):

                        value = signals.get(key)

                        if value is not None:

                            try:
                                values.append(float(value))
                            except (TypeError, ValueError):
                                pass

        if not values:
            return 0.0

        return max(
            0.0,
            max(values)
        )

    @staticmethod
    def _verification_status(
        response_inspection,
    ) -> str:

        if not isinstance(
            response_inspection,
            dict
        ):
            return "UNKNOWN"

        agents = response_inspection.get(
            "agents",
            response_inspection.get("results", [])
        )

        if not isinstance(agents, list):
            return "UNKNOWN"

        for agent in agents:

            if not isinstance(agent, dict):
                continue

            if str(
                agent.get("agent", "")
            ).lower() != "factuality":
                continue

            signals = agent.get("signals", {})

            if isinstance(signals, dict):

                status = signals.get(
                    "factuality_status"
                )

                if status is not None:
                    return str(status).upper()

                verification = signals.get(
                    "verification"
                )

                if isinstance(verification, dict):

                    status = verification.get("status")

                    if status is not None:
                        return str(status).upper()

            status = agent.get(
                "verification_status"
            )

            if status is not None:
                return str(status).upper()

        return "UNKNOWN"

    # ============================================================
    # DECISION HELPERS
    # ============================================================

    @staticmethod
    def _extract_decision(
        inspection
    ) -> str:

        if not isinstance(
            inspection,
            dict
        ):

            return "ALLOW"

        decision = inspection.get(
            "decision",
            inspection.get(
                "action",
                "ALLOW"
            )
        )

        return str(
            decision
        ).upper()

    @staticmethod
    def _final_decision(
        pre_decision,
        post_decision,
        policy_decision="ALLOW",
    ) -> str:

        decisions = [

            str(
                pre_decision
            ).upper(),

            str(
                post_decision
            ).upper(),

            str(
                policy_decision
            ).upper(),
        ]

        if "BLOCK" in decisions:

            return "BLOCK"

        if any(
            decision in {
                "REVIEW",
                "UNKNOWN",
            }
            for decision in decisions
        ):

            return "REVIEW"

        if "MODIFY" in decisions:

            return "MODIFY"

        return "ALLOW"

    # ============================================================
    # LEGACY PROVIDER
    # ============================================================

    def _invoke_legacy_provider(
        self,
        prompt: str,
    ):

        provider = (
            self.model_provider
        )

        if hasattr(
            provider,
            "generate"
        ):

            try:

                return provider.generate(
                    prompt
                )

            except AttributeError as exc:

                error_text = str(
                    exc
                )

                if (
                    "'str' object has no attribute "
                    "'get'"
                    not in error_text
                ):

                    raise

                return provider.generate(
                    {
                        "prompt": prompt
                    }
                )

        if callable(
            provider
        ):

            return provider(
                prompt
            )

        raise TypeError(
            "Model provider must expose "
            "generate(...) or be callable."
        )

    # ============================================================
    # RESPONSE NORMALIZATION
    # ============================================================

    @staticmethod
    def _extract_response(
        response
    ) -> str:

        if response is None:

            return ""

        if isinstance(
            response,
            str
        ):

            return response.strip()

        if hasattr(
            response,
            "text"
        ):

            text = getattr(
                response,
                "text"
            )

            if isinstance(
                text,
                str
            ):

                return text.strip()

        if isinstance(
            response,
            dict
        ):

            for key in (
                "text",
                "content",
                "response",
                "output",
                "model_response",
            ):

                value = response.get(
                    key
                )

                if isinstance(
                    value,
                    str
                ):

                    return value.strip()

            choices = response.get(
                "choices"
            )

            if (
                isinstance(
                    choices,
                    list
                )
                and choices
            ):

                first = choices[0]

                if isinstance(
                    first,
                    dict
                ):

                    message = (
                        first.get(
                            "message"
                        )
                    )

                    if isinstance(
                        message,
                        dict
                    ):

                        content = (
                            message.get(
                                "content"
                            )
                        )

                        if isinstance(
                            content,
                            str
                        ):

                            return (
                                content.strip()
                            )

                    text = first.get(
                        "text"
                    )

                    if isinstance(
                        text,
                        str
                    ):

                        return (
                            text.strip()
                        )

        return str(
            response
        ).strip()

    # ============================================================
    # RESULT BUILDER
    # ============================================================

    def _build_result(
        self,
        prompt,
        output,
        action,
        request_inspection,
        response_inspection,
        events,
        started,
        metadata,
        raw_output=None,
        model_latency_ms=0.0,
        model_error=None,
        policy_error=None,
        policy_decision="ALLOW",
        model_usage=None,
    ):

        total_latency = (
            time.perf_counter()
            - started
        ) * 1000

        usage = (
            model_usage
            or {}
        )

        result = {

            "decision":
                action,

            "action":
                action,

            "prompt":
                prompt,

            "output":
                output,

            "raw_output":
                (
                    raw_output
                    if raw_output is not None
                    else output
                ),

            "request_governance":
                request_inspection,

            "response_governance":
                response_inspection,

            "policy_decision":
                policy_decision,

            "risk_score":
                self._risk_score(
                    request_inspection,
                    response_inspection
                ),

            "confidence":
                self._confidence(
                    request_inspection,
                    response_inspection
                ),

            "model_latency_ms":
                round(
                    float(
                        model_latency_ms
                    ),
                    3
                ),

            "latency_ms":
                round(
                    float(
                        total_latency
                    ),
                    3
                ),

            # ==================================================
            # MODEL USAGE
            # ==================================================

            "input_tokens":
                int(
                    usage.get(
                        "input_tokens",
                        0
                    )
                    or 0
                ),

            "output_tokens":
                int(
                    usage.get(
                        "output_tokens",
                        0
                    )
                    or 0
                ),

            "token_count":
                int(
                    usage.get(
                        "token_count",
                        0
                    )
                    or 0
                ),

            "cost":
                float(
                    usage.get(
                        "cost",
                        0.0
                    )
                    or 0.0
                ),

            "estimated_cost":
                float(
                    usage.get(
                        "estimated_cost",
                        0.0
                    )
                    or 0.0
                ),

            "model":
                usage.get(
                    "model",
                    "unknown"
                ),

            "provider":
                usage.get(
                    "provider",
                    "unknown"
                ),

            "cost_source":
                usage.get(
                    "cost_source",
                    "unknown"
                ),

            "cost_details":
                usage.get(
                    "cost_details",
                    {}
                ),

            "events":
                events,

            "metadata":
                metadata,
        }

        if model_error:

            result[
                "model_error"
            ] = model_error

        if policy_error:

            result[
                "policy_error"
            ] = policy_error

        return result

    # ============================================================
    # RISK
    # ============================================================

    @staticmethod
    def _risk_score(
        request_inspection,
        response_inspection
    ) -> float:

        values = []

        for inspection in (
            request_inspection,
            response_inspection,
        ):

            if not isinstance(
                inspection,
                dict
            ):

                continue

            for key in (
                "risk_score",
                "risk",
            ):

                value = (
                    inspection.get(
                        key
                    )
                )

                if value is not None:

                    try:

                        values.append(
                            float(value)
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        pass

            agents = (
                inspection.get(
                    "agents",
                    inspection.get(
                        "results",
                        []
                    )
                )
            )

            if isinstance(
                agents,
                list
            ):

                for agent in agents:

                    if not isinstance(
                        agent,
                        dict
                    ):

                        continue

                    value = agent.get(
                        "risk"
                    )

                    if value is None:

                        continue

                    try:

                        values.append(
                            float(value)
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        pass

        if not values:

            return 0.0

        return round(

            max(
                0.0,
                min(
                    1.0,
                    max(values)
                )
            ),

            4
        )

    # ============================================================
    # CONFIDENCE
    # ============================================================

    @staticmethod
    def _confidence(
        request_inspection,
        response_inspection
    ) -> float:

        values = []

        for inspection in (
            request_inspection,
            response_inspection,
        ):

            if not isinstance(
                inspection,
                dict
            ):

                continue

            try:

                value = (
                    inspection.get(
                        "confidence"
                    )
                )

                if value is not None:

                    values.append(
                        float(value)
                    )

            except (
                TypeError,
                ValueError,
            ):

                pass

            agents = (
                inspection.get(
                    "agents",
                    inspection.get(
                        "results",
                        []
                    )
                )
            )

            if isinstance(
                agents,
                list
            ):

                for agent in agents:

                    if not isinstance(
                        agent,
                        dict
                    ):

                        continue

                    value = agent.get(
                        "confidence"
                    )

                    if value is None:

                        continue

                    try:

                        values.append(
                            float(value)
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        pass

        if not values:

            return 0.0

        return round(
            sum(values)
            / len(values),
            4
        )

    # ============================================================
    # BLOCKED RESULT
    # ============================================================

    def _blocked_result(
        self,
        prompt,
        reason,
        events,
        started,
        metadata=None,
        request_inspection=None,
    ):

        events.append(
            f"BLOCK: {reason}"
        )

        result = self._build_result(

            prompt=prompt,

            output=(
                "🚫 ControlPlane blocked "
                "the request.\n\n"
                f"Reason: {reason}"
            ),

            action="BLOCK",

            request_inspection=(
                request_inspection
                if request_inspection is not None
                else {}
            ),

            response_inspection={},

            events=events,

            started=started,

            metadata=(
                metadata
                if metadata is not None
                else {}
            ),

            policy_decision="BLOCK",
        )

        self._audit(result)

        return result

    # ============================================================
    # AUDIT + METRICS
    # ============================================================

    def _audit(
        self,
        result: Dict[str, Any]
    ):

        if self.audit_logger is not None:

            try:

                if callable(
                    self.audit_logger
                ):

                    self.audit_logger(
                        result
                    )

                elif hasattr(
                    self.audit_logger,
                    "write"
                ):

                    self.audit_logger.write(
                        result
                    )

                elif hasattr(
                    self.audit_logger,
                    "log"
                ):

                    self.audit_logger.log(
                        result
                    )

            except Exception:

                pass

        if self.metrics_collector is not None:

            try:

                self.metrics_collector.record(
                    result
                )

            except Exception:

                pass