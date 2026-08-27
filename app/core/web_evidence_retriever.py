"""
ControlPlane.ai Web Evidence Retriever

Production-oriented web evidence retrieval layer.

Responsibilities:
    1. Search the web for a factual claim.
    2. Return candidate sources with provenance.
    3. Keep web retrieval separate from factuality decisions.
    4. Fail safely when web retrieval is unavailable.
    5. Provide a stable interface that can later use:
         - Tavily
         - Bing Web Search
         - Google Programmable Search
         - SerpAPI
         - another enterprise search provider

IMPORTANT:
    This module does NOT decide whether a claim is true.

It only answers:

    "What web evidence is relevant to this claim?"

ARCHITECTURE:

    Local Evidence / RAG
            |
            | UNKNOWN
            v
       Web Evidence
         Retriever
            |
            v
          Tavily

The factuality decision remains in the factuality
engine/agent. This module only retrieves evidence.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import httpx


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_TOP_K = 5

DEFAULT_TIMEOUT_SECONDS = 8.0

DEFAULT_MIN_SCORE = 0.55

DEFAULT_SEARCH_ENDPOINT = (
    "https://api.tavily.com/search"
)


# ============================================================
# WEB EVIDENCE RETRIEVER
# ============================================================

class WebEvidenceRetriever:
    """
    Web-based evidence retrieval layer.

    The retriever is intentionally independent from:

        - FactualityAgent
        - FactualityEngine
        - policy decisions
        - PASS / REVIEW / BLOCK decisions

    It only retrieves candidate evidence.

    A search provider can be changed later without changing
    the factuality-agent contract.

    IMPORTANT:
        This class does NOT determine whether a claim is
        true or false.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        min_score: float = DEFAULT_MIN_SCORE,
    ):

        # ----------------------------------------------------
        # API KEY
        # ----------------------------------------------------

        self.api_key = (
            api_key
            or os.getenv("TAVILY_API_KEY")
        )

        # ----------------------------------------------------
        # SEARCH ENDPOINT
        # ----------------------------------------------------

        self.endpoint = (
            endpoint
            or os.getenv(
                "WEB_SEARCH_ENDPOINT",
                DEFAULT_SEARCH_ENDPOINT,
            )
        )

        # ----------------------------------------------------
        # RETRIEVAL CONFIGURATION
        # ----------------------------------------------------

        self.top_k = max(
            1,
            int(top_k),
        )

        self.timeout = max(
            1.0,
            float(timeout),
        )

        self.min_score = float(
            min_score
        )

    # ========================================================
    # HEALTH
    # ========================================================

    def health(self) -> Dict[str, Any]:
        """
        Return retriever configuration health.

        This does not perform a live search.

        Returns:
            Dictionary describing whether the web retrieval
            provider is configured.
        """

        if not self.api_key:

            return {
                "status": "degraded",
                "provider": "tavily",
                "configured": False,
                "reason": (
                    "TAVILY_API_KEY is not configured."
                ),
            }

        return {
            "status": "healthy",
            "provider": "tavily",
            "configured": True,
            "endpoint": self.endpoint,
            "top_k": self.top_k,
            "timeout_seconds": self.timeout,
            "min_score": self.min_score,
        }

    # ========================================================
    # SEARCH / RETRIEVE
    # ========================================================

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve web evidence for a query.

        Returns a list of normalized evidence records.

        Example:

            [
                {
                    "id": "...",
                    "title": "...",
                    "url": "...",
                    "source": "...",
                    "text": "...",
                    "similarity": 0.91,
                    "query": "...",
                    "retrieval_latency_ms": 123.4,
                }
            ]

        IMPORTANT:
            This method only retrieves evidence.

            It does NOT decide whether the claim is:
                - TRUE
                - FALSE
                - VERIFIED
                - FAILED
                - UNKNOWN

            Those decisions belong to the factuality layer.
        """

        started = time.perf_counter()

        # ----------------------------------------------------
        # Validate query
        # ----------------------------------------------------

        if not isinstance(
            query,
            str,
        ):
            return []

        query = query.strip()

        if not query:
            return []

        # ----------------------------------------------------
        # No API key -> safe empty result
        # ----------------------------------------------------

        if not self.api_key:
            return []

        # ----------------------------------------------------
        # Determine result limit
        # ----------------------------------------------------

        limit = (
            self.top_k
            if top_k is None
            else max(
                1,
                int(top_k),
            )
        )

        try:

            # ------------------------------------------------
            # Query provider
            # ------------------------------------------------

            response = self._search(
                query=query,
                top_k=limit,
            )

            # ------------------------------------------------
            # Normalize provider response
            # ------------------------------------------------

            results = self._normalize_results(
                response,
                query=query,
            )

            # ------------------------------------------------
            # Record retrieval latency
            # ------------------------------------------------

            elapsed = (
                time.perf_counter()
                - started
            ) * 1000

            for result in results:

                result[
                    "retrieval_latency_ms"
                ] = float(elapsed)

            return results

        except Exception:

            # ------------------------------------------------
            # Fail safely.
            #
            # IMPORTANT:
            #
            # Web retrieval failure must not crash the
            # ControlPlane governance pipeline.
            #
            # The factuality engine decides what an empty
            # result means, e.g. UNKNOWN / REVIEW.
            # ------------------------------------------------

            return []

    # ========================================================
    # PROVIDER REQUEST
    # ========================================================

    def _search(
        self,
        query: str,
        top_k: int,
    ) -> Dict[str, Any]:

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": top_k,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": (
                "ControlPlane.ai/"
                "web-evidence-retriever"
            ),
        }

        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:

            response = client.post(
                self.endpoint,
                json=payload,
                headers=headers,
            )

            response.raise_for_status()

            return response.json()

    # ========================================================
    # RESULT NORMALIZATION
    # ========================================================

    def _normalize_results(
        self,
        response: Any,
        query: str,
    ) -> List[Dict[str, Any]]:

        # ----------------------------------------------------
        # Validate provider response
        # ----------------------------------------------------

        if not isinstance(
            response,
            dict,
        ):
            return []

        raw_results = response.get(
            "results",
            [],
        )

        if not isinstance(
            raw_results,
            list,
        ):
            return []

        normalized: List[Dict[str, Any]] = []

        # ----------------------------------------------------
        # Normalize every result
        # ----------------------------------------------------

        for index, item in enumerate(
            raw_results
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue

            # ------------------------------------------------
            # Title
            # ------------------------------------------------

            title = str(
                item.get(
                    "title",
                    "",
                )
            ).strip()

            # ------------------------------------------------
            # URL
            # ------------------------------------------------

            url = str(
                item.get(
                    "url",
                    "",
                )
            ).strip()

            # ------------------------------------------------
            # Provider content
            # ------------------------------------------------

            content = str(
                item.get(
                    "content",
                    "",
                )
            ).strip()

            # ------------------------------------------------
            # Relevance score
            # ------------------------------------------------

            score = self._safe_score(
                item.get(
                    "score",
                    0.0,
                )
            )

            # ------------------------------------------------
            # Required fields
            # ------------------------------------------------

            if not url:
                continue

            if not content:
                continue

            # ------------------------------------------------
            # Minimum retrieval threshold
            #
            # This is a RETRIEVAL filter.
            #
            # It is NOT a factuality decision.
            # ------------------------------------------------

            if score < self.min_score:
                continue

            # ------------------------------------------------
            # Stable normalized record
            # ------------------------------------------------

            normalized.append(
                {
                    "id": str(
                        item.get(
                            "id",
                            index,
                        )
                    ),
                    "title": title,
                    "url": url,
                    "source": self._source_name(
                        url
                    ),
                    "text": content,
                    "similarity": score,
                    "query": query,
                }
            )

        return normalized

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _safe_score(
        value: Any,
    ) -> float:
        """
        Safely normalize a provider score to [0, 1].
        """

        try:

            score = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        if score < 0.0:
            return 0.0

        if score > 1.0:
            return 1.0

        return score

    @staticmethod
    def _source_name(
        url: str,
    ) -> str:
        """
        Extract the hostname from a source URL.
        """

        try:

            from urllib.parse import (
                urlparse,
            )

            hostname = urlparse(
                url
            ).hostname

            if not hostname:
                return "Unknown source"

            return hostname.lower()

        except Exception:

            return "Unknown source"