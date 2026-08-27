from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .review_queue import ReviewQueue
from .store import FeedbackStore


class ReviewService:

    def __init__(
        self,
        review_queue: Optional[ReviewQueue] = None,
        feedback_store: Optional[FeedbackStore] = None,
        audit_logger=None,
    ):
        self.review_queue = (
            review_queue
            if review_queue is not None
            else ReviewQueue()
        )

        self.feedback_store = (
            feedback_store
            if feedback_store is not None
            else FeedbackStore()
        )

        self.audit_logger = audit_logger
        
    def review_history(self):
        return self.feedback_store.read_all(
          limit=1000
    )
    # =========================================================
    # CREATE REVIEW FROM GATEWAY RESULT
    # =========================================================

    def create_from_result(
        self,
        result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        decision = str(
            result.get(
                "decision",
                result.get(
                    "action",
                    ""
                ),
            )
        ).upper()

        if decision != "REVIEW":
            return None

        # -----------------------------------------------------
        # Preserve the original gateway request_id.
        #
        # The RequestGateway stores the ID inside:
        #
        #     result["metadata"]["request_id"]
        #
        # Do NOT generate a second UUID when that ID exists.
        # -----------------------------------------------------

        request_id = result.get(
            "request_id"
        )

        if not request_id:

            metadata = result.get(
                "metadata",
                {},
            )

            if isinstance(
                metadata,
                dict,
            ):
                request_id = metadata.get(
                    "request_id"
                )

        if not request_id:

            request_id = (
                self._generate_request_id()
            )

        # Keep the resolved request_id on
        # the result as well.
        result["request_id"] = request_id

        request_inspection = result.get(
            "request_governance",
            result.get(
                "request_inspection",
                {},
            ),
        )

        response_inspection = result.get(
            "response_governance",
            result.get(
                "response_inspection",
                {},
            ),
        )

        risk_score = self._extract_risk(
            result,
            request_inspection,
            response_inspection,
        )

        reason = self._build_reason(
            result,
            request_inspection,
            response_inspection,
        )

        item = self.review_queue.create_review(
            request_id=request_id,
            prompt=result.get(
                "prompt",
                "",
            ),
            model_response=result.get(
                "raw_output",
                result.get(
                    "output",
                    "",
                ),
            ),
            risk_score=risk_score,
            reason=reason,
            metadata=result.get(
                "metadata",
                {},
            ),
        )

        result["review_id"] = item.review_id

        result["review_status"] = (
            item.status
        )

        result.setdefault(
            "events",
            []
        ).append(
            "HUMAN REVIEW: "
            f"created | review_id="
            f"{item.review_id}"
        )

        self._audit(
            result,
            event_type="REVIEW_CREATED",
        )

        return item.to_dict()

    # =========================================================
    # PENDING REVIEWS
    # =========================================================

    def pending_reviews(self):

        return [
            item.to_dict()
            for item in self.review_queue.pending()
        ]

    # =========================================================
    # GET REVIEW
    # =========================================================

    def get_review(
        self,
        review_id: str,
    ):

        item = self.review_queue.get(
            review_id
        )

        if item is None:
            return None

        return item.to_dict()

    # =========================================================
    # RESOLVE REVIEW
    # =========================================================

    def resolve_review(
        self,
        review_id: str,
        final_decision: str,
        reviewer: str,
        comment: str = "",
    ):

        item = self.review_queue.resolve(
            review_id=review_id,
            final_decision=final_decision,
            reviewer=reviewer,
            comment=comment,
        )

        feedback = {
            "review_id": item.review_id,
            "request_id": item.request_id,
            "final_decision": item.final_decision,
            "reviewer": item.reviewer,
            "reviewer_comment": (
                item.reviewer_comment
            ),
            "risk_score": item.risk_score,
            "reason": item.reason,
            "reviewed_at": item.reviewed_at,
            "created_at": item.created_at,
            "metadata": item.metadata,
            "prompt": item.prompt,
            "model_response": item.model_response,
        }

        self.feedback_store.save(
            feedback
        )

        audit_result = {
            "request_id": item.request_id,
            "decision": item.final_decision,
            "action": item.final_decision,
            "prompt": item.prompt,
            "review_id": item.review_id,
            "review_status": item.status,
            "reviewer": item.reviewer,
            "reviewer_comment": (
                item.reviewer_comment
            ),
            "final_decision": (
                item.final_decision
            ),
            "events": [
                "HUMAN REVIEW: resolved",
                (
                    "FEEDBACK: persisted"
                ),
            ],
            "metadata": item.metadata,
        }

        self._audit(
            audit_result,
            event_type="REVIEW_RESOLVED",
        )

        # -----------------------------------------------------
        # Preserve the existing response structure and add
        # a top-level status for the review API.
        #
        # REJECT is a valid human-review resolution and should
        # be surfaced as REJECTED.
        # -----------------------------------------------------

        decision = str(
            item.final_decision
        ).strip().upper()

        if decision == "REJECT":
            status = "REJECTED"
        elif decision in {
            "ALLOW",
            "BLOCK",
            "EDIT",
        }:
            status = "RESOLVED"
        else:
            status = (
                str(
                    item.status
                ).strip().upper()
                if item.status
                else "RESOLVED"
            )

        return {
            "status": status,
            "review": item.to_dict(),
            "feedback": feedback,
        }

    # =========================================================
    # FEEDBACK SUMMARY
    # =========================================================

    def feedback_summary(self):

        return self.feedback_store.summary()

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _generate_request_id():

        import uuid

        return str(
            uuid.uuid4()
        )

    @staticmethod
    def _extract_risk(
        result,
        request_inspection,
        response_inspection,
    ):

        try:

            if result.get(
                "risk_score"
            ) is not None:

                return float(
                    result["risk_score"]
                )

        except (
            TypeError,
            ValueError,
        ):
            pass

        values = []

        for inspection in (
            request_inspection,
            response_inspection,
        ):

            if not isinstance(
                inspection,
                dict,
            ):
                continue

            for key in (
                "risk_score",
                "risk",
            ):

                try:

                    value = inspection.get(
                        key
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

        return max(
            values
        ) if values else 0.0

    @staticmethod
    def _build_reason(
        result,
        request_inspection,
        response_inspection,
    ):

        reasons = []

        for inspection in (
            request_inspection,
            response_inspection,
        ):

            if not isinstance(
                inspection,
                dict,
            ):
                continue

            reason = inspection.get(
                "reason"
            )

            if reason:
                reasons.append(
                    str(reason)
                )

        if result.get(
            "policy_decision"
        ) == "REVIEW":

            reasons.append(
                "Policy engine requested review."
            )

        if not reasons:

            reasons.append(
                "Governance pipeline "
                "requires human review."
            )

        return " ".join(
            dict.fromkeys(
                reasons
            )
        )

    def _audit(
        self,
        result,
        event_type: str,
    ):

        result = dict(result)

        result.setdefault(
            "events",
            []
        ).append(
            f"AUDIT: {event_type}"
        )

        if self.audit_logger:

            try:

                self.audit_logger.log(
                    result,
                    request_id=result.get(
                        "request_id"
                    ),
                )

            except Exception:
                # Audit failures must never
                # break human-review flow.
                pass