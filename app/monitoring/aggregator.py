import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .metrics import MetricsCollector


class MetricsAggregator:
    """
    Builds dashboard metrics from the shared MetricsCollector.
    """

    def __init__(
        self,
        collector: Optional[
            MetricsCollector
        ] = None,
    ):

        self.collector = (
            collector
            if collector is not None
            else MetricsCollector()
        )

    # =========================================================
    # INGEST
    # =========================================================

    def ingest(
        self,
        result: Dict[str, Any],
    ):

        return self.collector.record(
            result
        )

    def ingest_many(
        self,
        results: Iterable[
            Dict[str, Any]
        ],
    ) -> int:

        count = 0

        for result in results:

            if not isinstance(
                result,
                dict,
            ):
                continue

            self.ingest(
                result
            )

            count += 1

        return count

    # =========================================================
    # AUDIT JSONL
    # =========================================================

    def load_jsonl(
        self,
        path: str,
    ) -> int:

        file_path = Path(path)

        if not file_path.exists():
            return 0

        count = 0

        with file_path.open(
            "r",
            encoding="utf-8",
        ) as handle:

            for line in handle:

                line = line.strip()

                if not line:
                    continue

                try:

                    result = json.loads(
                        line
                    )

                except json.JSONDecodeError:

                    continue

                if not isinstance(
                    result,
                    dict,
                ):
                    continue

                self.ingest(
                    result
                )

                count += 1

        return count

    # =========================================================
    # SNAPSHOT
    # =========================================================

    def snapshot(
        self,
    ) -> Dict[str, Any]:

        return (
            self.collector
            .snapshot()
        )

    # =========================================================
    # DASHBOARD
    # =========================================================

    def dashboard(
        self,
    ) -> Dict[str, Any]:

        snapshot = (
            self.snapshot()
        )

        decisions = (
            snapshot[
                "decisions"
            ]
        )

        governance = (
            snapshot.get(
                "governance",
                {},
            )
        )

        risk = dict(
            snapshot.get(
                "risk",
                {},
            )
        )

        risk.update(
            snapshot.get(
                "risk_dimensions",
                {},
            )
        )

        latency = (
            snapshot.get(
                "latency",
                {},
            )
        )

        model_latency = (
            snapshot.get(
                "model_latency",
                {},
            )
        )

        return {

            # -------------------------------------------------
            # SYSTEM
            # -------------------------------------------------

            "system": {

                "requests":
                    snapshot[
                        "total_requests"
                    ],

                "status": (
                    "ACTIVE"
                    if snapshot[
                        "total_requests"
                    ] > 0
                    else "READY"
                ),
            },

            # -------------------------------------------------
            # GOVERNANCE
            # -------------------------------------------------

            "governance": {

                "allow_rate":
                    snapshot[
                        "decision_rates"
                    ][
                        "ALLOW"
                    ],

                "review_rate":
                    snapshot[
                        "decision_rates"
                    ][
                        "REVIEW"
                    ],

                "block_rate":
                    snapshot[
                        "decision_rates"
                    ][
                        "BLOCK"
                    ],

                "edit_rate":
                    snapshot[
                        "decision_rates"
                    ][
                        "EDIT"
                    ],

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
            },

            # -------------------------------------------------
            # RISK
            # -------------------------------------------------

            "risk": risk,

            # -------------------------------------------------
            # PERFORMANCE
            # -------------------------------------------------

            "performance": {

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
                    model_latency.get(
                        "average_ms",
                        0.0,
                    ),

                "model_minimum_ms":
                    model_latency.get(
                        "minimum_ms",
                        0.0,
                    ),

                "model_maximum_ms":
                    model_latency.get(
                        "maximum_ms",
                        0.0,
                    ),
            },

            # -------------------------------------------------
            # COST
            # -------------------------------------------------

            "cost":
                snapshot[
                    "cost"
                ],

            # -------------------------------------------------
            # HUMAN REVIEW
            # -------------------------------------------------

            "human_review":
                snapshot[
                    "reviews"
                ],

            # -------------------------------------------------
            # FACTUALITY
            # -------------------------------------------------

            "factuality":
                snapshot.get(
                    "factuality",
                    {
                        "requests_checked": 0,
                        "claims": 0,
                        "verified": 0,
                        "failed": 0,
                        "unknown": 0,
                        "status_counts": {},
                    },
                ),

            # -------------------------------------------------
            # DECISIONS
            # -------------------------------------------------

            "decisions":
                decisions,
        }