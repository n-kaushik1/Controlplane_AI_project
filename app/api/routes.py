from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import BaseModel, Field


from app.gateway.request_gateway import (
    RequestGateway,
)

from app.gateway.review_gateway import (
    ReviewAwareGateway,
)

from app.models.provider import (
    create_model_provider,
)

from app.audit import (
    AuditLogger,
)

from app.feedback import (
    FeedbackStore,
    ReviewQueue,
    ReviewService,
)

from app.monitoring import (
    MetricsCollector,
    MetricsAggregator,
)


# =========================================================
# RISK PROFILES
# =========================================================

from app.context.risk_profiles import (
    get_all_profile_summaries,
    get_profile_summary,
    get_risk_profile,
)


# =========================================================
# GOVERNANCE AGENTS
# =========================================================

from app.agents.security_agent import (
    SecurityAgent,
)

from app.agents.privacy_agent import (
    PrivacyAgent,
)

from app.agents.bias_agent import (
    BiasAgent,
)

from app.agents.cost_agent import (
    CostAgent,
)

from app.agents.factuality_agent import (
    FactualityAgent,
)

from app.agents.orchestrator import (
    AgentOrchestrator,
)


# =========================================================
# FACTUALITY ENGINE
# =========================================================

from app.core.factuality_engine import (
    FactualityEngine,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/api",
    tags=[
        "ControlPlane"
    ],
)


# =========================================================
# CORE SERVICES
# =========================================================

# IMPORTANT:
#
# The provider is selected through the existing provider
# factory and configuration.
#
# Supported providers:
#
#     mock
#     openrouter
#     openai
#
# This keeps the rest of ControlPlane provider-agnostic.
#
# With:
#
#     MODEL_PROVIDER=mock
#
# the existing mock behavior is preserved.
#
# With:
#
#     MODEL_PROVIDER=openrouter
#
# or:
#
#     MODEL_PROVIDER=openai
#
# the configured real LLM provider is used.
#
provider = create_model_provider()


audit_logger = AuditLogger()


review_queue = ReviewQueue()


feedback_store = FeedbackStore()


review_service = ReviewService(
    review_queue=review_queue,
    feedback_store=feedback_store,
    audit_logger=audit_logger,
)


# =========================================================
# MONITORING
# =========================================================

metrics_collector = MetricsCollector()


metrics_aggregator = MetricsAggregator(
    collector=metrics_collector,
)


# =========================================================
# GOVERNANCE AGENTS
# =========================================================

security_agent = SecurityAgent()


privacy_agent = PrivacyAgent()


bias_agent = BiasAgent()


cost_agent = CostAgent()


# =========================================================
# FACTUALITY ENGINE
# =========================================================

factuality_engine = FactualityEngine()


# =========================================================
# FACTUALITY AGENT
# =========================================================

factuality_agent = FactualityAgent(
    claim_extractor=(
        factuality_engine.extract_claims
    ),
    verifier=(
        factuality_engine.verify_claims
    ),
    evidence=(
        factuality_engine.evidence
    ),
)


# =========================================================
# GOVERNANCE ORCHESTRATOR
# =========================================================

orchestrator = AgentOrchestrator(
    security_agent=security_agent,
    privacy_agent=privacy_agent,
    bias_agent=bias_agent,
    factuality_agent=factuality_agent,
    cost_agent=cost_agent,
)


# =========================================================
# GATEWAY
# =========================================================

gateway = RequestGateway(
    model_provider=provider,
    orchestrator=orchestrator,
    audit_logger=audit_logger,
    metrics_collector=metrics_collector,
)


review_gateway = ReviewAwareGateway(
    gateway=gateway,
    review_service=review_service,
)


# =========================================================
# REQUEST MODELS
# =========================================================

class GenerateRequest(
    BaseModel
):

    prompt: str

    metadata: Optional[
        dict
    ] = None

    # -----------------------------------------------------
    # Round 2 enterprise AI use case
    # -----------------------------------------------------

    use_case: str = Field(
        default="customer_support",
        description=(
            "Enterprise AI use case / risk profile."
        ),
    )

    # -----------------------------------------------------
    # Multi-turn conversation tracking
    # -----------------------------------------------------

    conversation_id: Optional[
        str
    ] = Field(
        default=None,
        description=(
            "Conversation identifier used for "
            "multi-turn governance tracking."
        ),
    )

    # -----------------------------------------------------
    # Optional user identifier
    # -----------------------------------------------------

    user_id: Optional[
        str
    ] = Field(
        default=None,
        description=(
            "Optional user identifier for "
            "governance and audit correlation."
        ),
    )

    # -----------------------------------------------------
    # Current conversation turn
    # -----------------------------------------------------

    turn_number: int = Field(
        default=1,
        ge=1,
        description=(
            "Conversation turn number."
        ),
    )


class ReviewDecisionRequest(
    BaseModel
):

    final_decision: str

    reviewer: str

    comment: str = ""


# =========================================================
# HEALTH
# =========================================================

@router.get(
    "/health"
)
def health():

    return {

        "status":
            "healthy",

        "service":
            "ControlPlane.ai",

        "human_review":
            "enabled",

        "governance": {

            "security":
                security_agent is not None,

            "privacy":
                privacy_agent is not None,

            "bias":
                bias_agent is not None,

            "cost":
                cost_agent is not None,

            "factuality":
                factuality_agent is not None,
        },

        "risk_profiles": {

            "enabled":
                True,

            "profiles":
                list(
                    get_all_profile_summaries()
                ),
        },
    }


# =========================================================
# RISK PROFILES
# =========================================================

@router.get(
    "/risk-profiles"
)
def risk_profiles():

    """
    Return all configured enterprise AI
    risk profiles.

    These profiles allow ControlPlane.ai
    to apply different governance policies
    to different AI use cases.
    """

    return {

        "profiles":
            get_all_profile_summaries()
    }


# =========================================================
# SINGLE RISK PROFILE
# =========================================================

@router.get(
    "/risk-profiles/{profile_id}"
)
def risk_profile(
    profile_id: str,
):

    """
    Return configuration for one
    enterprise AI risk profile.
    """

    try:

        return get_profile_summary(
            profile_id
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


# =========================================================
# GENERATE
# =========================================================

@router.post(
    "/generate"
)
def generate(
    request: GenerateRequest,
):

    # -----------------------------------------------------
    # Resolve and validate the selected risk profile.
    # -----------------------------------------------------

    try:

        profile = get_risk_profile(
            request.use_case
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # -----------------------------------------------------
    # Preserve all existing metadata.
    #
    # A copy is created so that the caller's original
    # dictionary is never modified directly.
    # -----------------------------------------------------

    metadata = dict(
        request.metadata or {}
    )

    # -----------------------------------------------------
    # Add Round 2 governance context.
    #
    # Existing metadata remains intact.
    # These fields give the governance and monitoring
    # layers explicit use-case and conversation context.
    # -----------------------------------------------------

    metadata.update({

        "use_case":
            profile.name,

        "risk_profile":
            profile.name,

        "risk_level":
            profile.risk_level,

        "conversation_id":
            request.conversation_id,

        "user_id":
            request.user_id,

        "turn_number":
            request.turn_number,

    })

    # -----------------------------------------------------
    # Preserve the existing review-aware processing path.
    # -----------------------------------------------------

    result = review_gateway.process(
        prompt=request.prompt,
        metadata=metadata,
    )

    # -----------------------------------------------------
    # Make the governance context explicit in the response.
    #
    # This allows the dashboard to show which enterprise
    # risk profile governed the request.
    # -----------------------------------------------------

    if isinstance(
        result,
        dict,
    ):

        result["use_case"] = (
            profile.name
        )

        result["risk_profile"] = (
            profile.name
        )

        result["risk_level"] = (
            profile.risk_level
        )

        result["conversation_id"] = (
            request.conversation_id
        )

        result["turn_number"] = (
            request.turn_number
        )

    return result


# =========================================================
# REVIEW QUEUE
# =========================================================

@router.get(
    "/reviews"
)
def pending_reviews():

    return {

        "reviews": (
            review_gateway
            .pending_reviews()
        )
    }


@router.get(
    "/reviews/history"
)
def review_history():

    return {

        "reviews": (
            review_gateway
            .review_history()
        )
    }


# =========================================================
# GET SINGLE REVIEW
# =========================================================

@router.get(
    "/reviews/{review_id}"
)
def get_review(
    review_id: str,
):

    review = (
        review_gateway
        .get_review(
            review_id
        )
    )

    if review is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Review not found."
            ),
        )

    return review


# =========================================================
# RESOLVE REVIEW
# =========================================================

@router.post(
    "/reviews/{review_id}/resolve"
)
def resolve_review(
    review_id: str,
    request: ReviewDecisionRequest,
):

    try:

        return (
            review_gateway
            .resolve_review(
                review_id=review_id,
                final_decision=(
                    request.final_decision
                ),
                reviewer=(
                    request.reviewer
                ),
                comment=(
                    request.comment
                ),
            )
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# FEEDBACK ANALYTICS
# =========================================================

@router.get(
    "/feedback/summary"
)
def feedback_summary():

    return (
        review_gateway
        .feedback_summary()
    )


# =========================================================
# MONITORING
# =========================================================

@router.get(
    "/metrics"
)
def metrics():

    """
    Complete monitoring snapshot.

    Includes:

    - request volume
    - decision distribution
    - decision rates
    - risk statistics
    - latency statistics
    - cost statistics
    - human-review statistics
    """

    return (
        metrics_collector
        .snapshot()
    )


# =========================================================
# MONITORING DASHBOARD
# =========================================================

@router.get(
    "/metrics/dashboard"
)
def metrics_dashboard():

    """
    Dashboard-oriented monitoring summary.
    """

    return (
        metrics_aggregator
        .dashboard()
    )


# =========================================================
# MONITORING EVENTS
# =========================================================

@router.get(
    "/metrics/events"
)
def metrics_events():

    """
    Recent governed request events.

    This endpoint exposes the existing in-memory
    MetricsCollector events to the dashboard.

    It does not modify gateway behavior.
    """

    events = (
        metrics_collector
        .events()
    )

    return {

        "events": [

            {

                "request_id":
                    event.request_id,

                "decision":
                    event.decision,

                "risk_score":
                    event.risk_score,

                "latency_ms":
                    event.latency_ms,

                "model_latency_ms":
                    event.model_latency_ms,

                "estimated_cost":
                    event.estimated_cost,

                "review_id":
                    event.review_id,

                "review_status":
                    event.review_status,

                "metadata":
                    event.metadata,

            }

            for event in events
        ]
    }


# =========================================================
# DECISION METRICS
# =========================================================

@router.get(
    "/metrics/decisions"
)
def metrics_decisions():

    return {

        "total_requests":
            metrics_collector
            .total_requests,

        "decisions":
            metrics_collector
            .decision_counts(),

        "rates":
            metrics_collector
            .decision_rates(),
    }


# =========================================================
# RISK METRICS
# =========================================================

@router.get(
    "/metrics/risk"
)
def metrics_risk():

    return {

        "total_requests":
            metrics_collector
            .total_requests,

        "risk":
            metrics_collector
            .risk_statistics(),
    }


# =========================================================
# PERFORMANCE METRICS
# =========================================================

@router.get(
    "/metrics/performance"
)
def metrics_performance():

    return {

        "total_requests":
            metrics_collector
            .total_requests,

        "latency":
            metrics_collector
            .latency_statistics(),
    }


# =========================================================
# COST METRICS
# =========================================================

@router.get(
    "/metrics/cost"
)
def metrics_cost():

    return {

        "total_requests":
            metrics_collector
            .total_requests,

        "cost":
            metrics_collector
            .cost_statistics(),
    }


# =========================================================
# HUMAN REVIEW METRICS
# =========================================================

@router.get(
    "/metrics/reviews"
)
def metrics_reviews():

    return {

        "total_requests":
            metrics_collector
            .total_requests,

        "reviews":
            metrics_collector
            .review_statistics(),
    }


# =========================================================
# OBSERVABILITY
# =========================================================

@router.get(
    "/observability"
)
def observability():

    return (
        metrics_aggregator
        .dashboard()
    )


@router.get(
    "/observability/metrics"
)
def observability_metrics():

    return (
        metrics_collector
        .snapshot()
    )


# =========================================================
# OBSERVABILITY EVENTS
# =========================================================

@router.get(
    "/observability/events"
)
def observability_events(
    limit: int = 100,
):

    events = (
        metrics_collector
        .events()
    )

    # Enforce the requested limit
    events = events[:limit]

    return {

        "events": [

            {

                "request_id":
                    event.request_id,

                "decision":
                    event.decision,

                "risk_score":
                    event.risk_score,

                "latency_ms":
                    event.latency_ms,

                "model_latency_ms":
                    event.model_latency_ms,

                "estimated_cost":
                    event.estimated_cost,

                "review_id":
                    event.review_id,

                "review_status":
                    event.review_status,

                "metadata":
                    event.metadata,

            }

            for event in events
        ]
    }


# =========================================================
# OBSERVABILITY HEALTH
# =========================================================

@router.get(
    "/observability/health"
)
def observability_health():

    data = health()

    data["observability"] = "enabled"

    return data