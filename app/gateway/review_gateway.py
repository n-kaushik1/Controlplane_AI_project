from typing import Any, Dict, Optional

from app.feedback import ReviewService


class ReviewAwareGateway:

    """
    Integration layer between the existing
    RequestGateway and the Human Review system.

    Existing RequestGateway remains unchanged.

    Flow:

        RequestGateway
              ↓
        Governance Decision
              ↓
          REVIEW?
           /   \
         NO     YES
         ↓       ↓
      Return   ReviewService
                   ↓
              Review Queue
                   ↓
              Feedback Store
    """

    def __init__(
        self,
        gateway,
        review_service: Optional[
            ReviewService
        ] = None,
    ):

        self.gateway = gateway

        self.review_service = (
            review_service
            if review_service is not None
            else ReviewService()
        )

    # =========================================================
    # PROCESS
    # =========================================================

    def process(
        self,
        prompt: str,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ):

        result = self.gateway.process(
            prompt,
            metadata=metadata,
        )

        review = (
            self.review_service
            .create_from_result(
                result
            )
        )

        if review:

            result["review"] = review

            result["review_id"] = (
                review["review_id"]
            )

            result["review_status"] = (
                review["status"]
            )

        return result

    # =========================================================
    # REVIEW API
    # =========================================================

    def pending_reviews(self):

        return (
            self.review_service
            .pending_reviews()
        )

    def get_review(
        self,
        review_id: str,
    ):

        return (
            self.review_service
            .get_review(review_id)
        )

    def resolve_review(
        self,
        review_id: str,
        final_decision: str,
        reviewer: str,
        comment: str = "",
    ):

        return (
            self.review_service
            .resolve_review(
                review_id=review_id,
                final_decision=final_decision,
                reviewer=reviewer,
                comment=comment,
            )
        )

    def feedback_summary(self):

        return (
            self.review_service
            .feedback_summary()
        )
    
    def review_history(self):

        return (
           self.review_service
           .review_history()
        )