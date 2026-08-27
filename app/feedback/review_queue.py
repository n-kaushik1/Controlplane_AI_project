from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from .models import ReviewItem


class ReviewQueue:

    def __init__(self):

        self._items: Dict[
            str,
            ReviewItem
        ] = {}

    # =========================================================
    # CREATE REVIEW
    # =========================================================

    def create_review(
        self,
        request_id: str,
        prompt: str,
        model_response: str = "",
        risk_score: float = 0.0,
        reason: str = "",
        metadata: Optional[dict] = None,
    ) -> ReviewItem:

        review_id = str(
            uuid.uuid4()
        )

        item = ReviewItem(
            review_id=review_id,
            request_id=request_id,
            prompt=prompt,
            model_response=model_response,
            risk_score=risk_score,
            reason=reason,
            metadata=metadata or {},
        )

        self._items[review_id] = item

        return item

    # =========================================================
    # GET REVIEW
    # =========================================================

    def get(
        self,
        review_id: str
    ) -> Optional[ReviewItem]:

        return self._items.get(
            review_id
        )

    # =========================================================
    # PENDING REVIEWS
    # =========================================================

    def pending(
        self
    ) -> List[ReviewItem]:

        return [
            item
            for item in self._items.values()
            if item.status == "PENDING"
        ]

    # =========================================================
    # ALL REVIEWS
    # =========================================================

    def all(
        self
    ) -> List[ReviewItem]:

        return list(
            self._items.values()
        )

    # =========================================================
    # REVIEW DECISION
    # =========================================================

    def resolve(
        self,
        review_id: str,
        final_decision: str,
        reviewer: str,
        comment: str = "",
    ) -> ReviewItem:

        item = self.get(
            review_id
        )

        if item is None:

            raise ValueError(
                f"Review item not found: "
                f"{review_id}"
            )

        decision = (
            final_decision
            .strip()
            .upper()
        )

        if decision not in {
            "ALLOW",
            "BLOCK",
            "EDIT",
            "REJECT",
        }:

            raise ValueError(
                "final_decision must be "
                "ALLOW, BLOCK, or EDIT"
                "(REJECT is also supported)"
            )

        if not reviewer or not reviewer.strip():

            raise ValueError(
                "reviewer is required"
            )

        item.status = "RESOLVED"

        item.final_decision = decision

        item.reviewer = reviewer.strip()

        item.reviewer_comment = comment

        item.reviewed_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        return item

    # =========================================================
    # REMOVE
    # =========================================================

    def clear(
        self
    ) -> None:

        self._items.clear()