"""
ControlPlane.ai Factuality Engine

Production-oriented factuality layer.

Responsibilities:
    1. Extract factual claims from generated text.
    2. Normalize claims.
    3. Compare claims against configured evidence.
    4. Use local RAG as the primary evidence source.
    5. Use web retrieval only when local evidence is inconclusive.
    6. Apply conservative source quality and claim-support checks.
    7. Return stable verification statistics.
    8. Fail safely when evidence is unavailable.

IMPORTANT:

    This engine does NOT assume that an unsupported claim is true.

    Supported claim:
        VERIFIED

    Contradicted claim:
        FAILED

    Partially supported claims:
        PARTIAL

    Unsupported / inconclusive claim:
        UNKNOWN

    No factual claims detected:
        NO_CLAIMS

Public compatibility is preserved with:

    FactualityEngine()
    FactualityEngine.extract_claims()
    FactualityEngine.verify_claims()
    FactualityEngine.scan()
    FactualityEngine.health()

The existing local-RAG, web-fallback and FactualityAgent
interfaces are preserved.
"""

from __future__ import annotations

import json
import os
import re
import time

from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_EVIDENCE_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "evidence.json"
)


# ============================================================
# LOCAL RETRIEVAL
# ============================================================

DEFAULT_RETRIEVAL_TOP_K = 5

DEFAULT_RETRIEVAL_THRESHOLD = 0.55


# ============================================================
# WEB FALLBACK
# ============================================================

DEFAULT_WEB_TOP_K = 5

DEFAULT_WEB_THRESHOLD = 0.70


# ============================================================
# WEB RANKING
# ============================================================

DEFAULT_WEB_RELEVANCE_WEIGHT = 0.60

DEFAULT_WEB_SOURCE_QUALITY_WEIGHT = 0.25

DEFAULT_WEB_SUPPORT_WEIGHT = 0.15

DEFAULT_WEB_STRONG_RANKING_THRESHOLD = 0.72


# ============================================================
# WEB CONSENSUS
# ============================================================

DEFAULT_MIN_SUPPORTING_SOURCES = 2

DEFAULT_WEB_CONSENSUS_THRESHOLD = 0.72

DEFAULT_WEB_SINGLE_SOURCE_THRESHOLD = 0.88

DEFAULT_WEB_CONFLICT_MARGIN = 0.10


# ============================================================
# CLAIM SUPPORT
# ============================================================

DEFAULT_MIN_TOKEN_COVERAGE = 0.80

DEFAULT_EXPLICIT_SUPPORT_SCORE = 0.90

DEFAULT_EXPLICIT_CONTRADICTION_SCORE = 0.90


# ============================================================
# SOURCE QUALITY
# ============================================================

SOURCE_QUALITY_RULES = {
    "government": 1.00,
    "official_institution": 1.00,
    "academic": 0.95,
    "research": 0.90,
    "major_news": 0.80,
    "reference": 0.75,
    "wikipedia": 0.65,
    "social": 0.30,
    "unknown": 0.50,
}


HIGH_AUTHORITY_DOMAINS = {
    "nasa.gov",
    "who.int",
    "un.org",
    "worldbank.org",
    "imf.org",
    "oecd.org",
    "europa.eu",
    "gov.in",
    "india.gov.in",
}


ACADEMIC_DOMAINS = {
    "arxiv.org",
    "nature.com",
    "science.org",
    "sciencedirect.com",
    "springer.com",
    "ieee.org",
    "acm.org",
    "pubmed.ncbi.nlm.nih.gov",
}


MAJOR_NEWS_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "washingtonpost.com",
    "theguardian.com",
    "wsj.com",
    "usatoday.com",
}


REFERENCE_DOMAINS = {
    "britannica.com",
    "worldatlas.com",
}


LOW_QUALITY_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "quora.com",
    "reddit.com",
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(
    text: Any,
) -> str:
    """
    Normalize text for deterministic comparison.
    """

    if text is None:
        return ""

    text = str(text)

    # --------------------------------------------------------
    # Markdown / presentation normalization
    # --------------------------------------------------------
    # Model responses frequently contain Markdown emphasis,
    # headings and bullets. Those are presentation details, not
    # factual content, and must never turn a supported claim into
    # a contradiction.
    text = re.sub(r"```(?:[a-zA-Z0-9_+-]+)?", " ", text)
    text = text.replace("```", " ")
    text = re.sub(r"[*_~`]+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text)

    text = text.replace(
        "\r\n",
        "\n",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip().lower()


# ============================================================
# CLAIM EXTRACTION
# ============================================================

def extract_claims(
    text: str,
) -> List[str]:
    """
    Lightweight factual claim extraction.

    Important compatibility rule:

    The current development MockModelProvider returns:

        Mock response generated for: <prompt>

    That is not an actual model answer. It must not be counted
    as a factual claim.

    Real declarative model responses continue through the
    existing extraction and verification pipeline unchanged.
    """

    if not isinstance(
        text,
        str,
    ):
        return []

    text = text.strip()

    if not text:
        return []

    # --------------------------------------------------------
    # Development/mock-provider response.
    #
    # Do NOT treat the wrapper itself as a factual claim.
    #
    # This preserves factuality semantics without changing
    # model generation or gateway behavior.
    # --------------------------------------------------------

    mock_response_pattern = re.compile(
        r"^\s*mock\s+response\s+generated\s+for\s*:",
        re.IGNORECASE,
    )

    if mock_response_pattern.match(
        text
    ):

        return []

    # --------------------------------------------------------
    # Split into sentences.
    # --------------------------------------------------------

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    claims: List[str] = []

    for sentence in sentences:

        sentence = sentence.strip()

        if not sentence:
            continue

        # ----------------------------------------------------
        # Ignore questions.
        # ----------------------------------------------------

        if sentence.endswith("?"):
            continue

        # ----------------------------------------------------
        # Remove markdown bullets.
        # ----------------------------------------------------

        sentence = re.sub(
            r"^[\-\*\•\d\.\)\s]+",
            "",
            sentence,
        ).strip()

        if not sentence:
            continue

        normalized = normalize_text(
            sentence
        )

        # ----------------------------------------------------
        # Ignore obvious conversational statements.
        # ----------------------------------------------------

        conversational_prefixes = (
            "i think ",
            "i believe ",
            "in my opinion ",
            "i am not sure ",
            "i'm not sure ",
            "perhaps ",
            "maybe ",
            "it seems ",
            "it might be ",
            "it may be ",
            "that's absolutely correct",
            "that is absolutely correct",
            "exactly",
            "absolutely",
            "sure",
            "of course",
            "certainly",
        )

        if normalized.startswith(
            conversational_prefixes
        ):
            # A conversational acknowledgement is not itself a
            # factual claim. If a factual clause follows it in
            # the same sentence, strip only the acknowledgement.
            normalized_without_ack = re.sub(
                r"^(?:that's|that is)\s+absolutely\s+correct[!,:;\-\s]*",
                "",
                normalized,
            )
            normalized_without_ack = re.sub(
                r"^(?:exactly|absolutely|of course|certainly)[!,:;\-\s]+",
                "",
                normalized_without_ack,
            )

            if normalized_without_ack and normalized_without_ack != normalized:
                sentence = normalized_without_ack.strip()
                normalized = normalize_text(sentence)
            else:
                continue

        # ----------------------------------------------------
        # Ignore assistant self-state / conversational metadata.
        # These statements are about the assistant's conversational
        # state, not externally verifiable world facts.
        # ----------------------------------------------------
        conversational_patterns = (
            r"^(?:i am|i'm) (?:doing|feeling) (?:great|good|well|fine|okay|ok)",
            r"^(?:i am|i'm) happy to help",
            r"^(?:i am|i'm) here to help",
            r"^(?:i can|i'll|i will) help",
            r"^(?:thanks|thank you) for (?:asking|your question)",
            r"^(?:user safety|safety)\s*:\s*(?:safe|okay|ok)",
            r"^(?:i apologize|i'm sorry|sorry)",
        )

        if any(
            re.match(pattern, normalized, re.IGNORECASE)
            for pattern in conversational_patterns
        ):
            continue

        # ----------------------------------------------------
        # Ignore extremely short fragments.
        # ----------------------------------------------------

        if len(normalized) < 12:
            continue

        claims.append(
            sentence
        )

    return claims


# ============================================================
# CLAIM COLLECTION COMPATIBILITY
# ============================================================

def _normalize_claim_collection(
    claims: Any,
) -> List[str]:
    """
    Normalize supported claim input formats.

    Supports:

        ["claim one", "claim two"]

        {"claims": ["claim one", "claim two"]}

        "single claim"
    """

    if claims is None:
        return []

    if isinstance(
        claims,
        dict,
    ):

        claims = claims.get(
            "claims",
            [],
        )

    if isinstance(
        claims,
        (list, tuple, set),
    ):

        result = []

        for claim in claims:

            if claim is None:
                continue

            claim = str(
                claim
            ).strip()

            if claim:
                result.append(
                    claim
                )

        return result

    claim = str(
        claims
    ).strip()

    if not claim:
        return []

    return [claim]


# ============================================================
# EVIDENCE LOADING
# ============================================================

def load_evidence(
    evidence: Any = None,
) -> Any:
    """
    Load evidence.

    Priority:

        1. Explicit evidence
        2. CONTROLPLANE_EVIDENCE_FILE
        3. data/evidence.json
        4. empty evidence
    """

    if evidence is not None:

        if isinstance(
            evidence,
            (str, Path),
        ):

            path = Path(
                evidence
            )

            if path.exists():

                return _load_json_file(
                    path
                )

        return evidence

    configured_file = os.getenv(
        "CONTROLPLANE_EVIDENCE_FILE"
    )

    if configured_file:

        path = Path(
            configured_file
        )

        if path.exists():

            return _load_json_file(
                path
            )

    if DEFAULT_EVIDENCE_FILE.exists():

        return _load_json_file(
            DEFAULT_EVIDENCE_FILE
        )

    return {}


def _load_json_file(
    path: Path,
) -> Any:
    """
    Safely load JSON evidence.
    """

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except Exception:

        return {}


# ============================================================
# EVIDENCE NORMALIZATION
# ============================================================

def _iter_evidence(
    evidence: Any,
) -> Iterable[
    Tuple[
        str,
        str,
        Optional[str],
    ]
]:
    """
    Yield normalized evidence rows.

    Public tuple shape:

        normalized_claim
        original_evidence
        source

    Explicit contradictory evidence is represented internally
    through the [CONTRADICTED] marker.
    """

    if evidence is None:
        return

    # --------------------------------------------------------
    # Dictionary evidence.
    # --------------------------------------------------------

    if isinstance(
        evidence,
        dict,
    ):

        if isinstance(
            evidence.get("claims"),
            list,
        ):

            for item in evidence["claims"]:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                claim = item.get(
                    "claim",
                    "",
                )

                supporting = item.get(
                    "evidence",
                    item.get(
                        "text",
                        "",
                    ),
                )

                source = item.get(
                    "source"
                )

                status = normalize_text(
                    item.get(
                        "status",
                        "SUPPORTED",
                    )
                )

                if status in {
                    "failed",
                    "false",
                    "contradicted",
                    "unsupported",
                    "rejected",
                }:

                    supporting = (
                        f"[CONTRADICTED] "
                        f"{supporting}"
                    )

                if claim:

                    yield (
                        normalize_text(
                            claim
                        ),
                        str(
                            supporting
                        ),
                        (
                            str(source)
                            if source
                            else None
                        ),
                    )

            return

        # ----------------------------------------------------
        # Dictionary key/value evidence.
        # ----------------------------------------------------

        for key, value in evidence.items():

            if key == "claims":
                continue

            if isinstance(
                value,
                dict,
            ):

                claim = value.get(
                    "claim",
                    key,
                )

                supporting = value.get(
                    "evidence",
                    value.get(
                        "text",
                        "",
                    ),
                )

                source = value.get(
                    "source"
                )

                status = normalize_text(
                    value.get(
                        "status",
                        "SUPPORTED",
                    )
                )

                if status in {
                    "failed",
                    "false",
                    "contradicted",
                    "unsupported",
                    "rejected",
                }:

                    supporting = (
                        f"[CONTRADICTED] "
                        f"{supporting}"
                    )

                yield (
                    normalize_text(
                        claim
                    ),
                    str(
                        supporting
                    ),
                    (
                        str(source)
                        if source
                        else None
                    ),
                )

            else:

                yield (
                    normalize_text(
                        key
                    ),
                    str(
                        value
                    ),
                    None,
                )

        return

    # --------------------------------------------------------
    # List evidence.
    # --------------------------------------------------------

    if isinstance(
        evidence,
        (list, tuple, set),
    ):

        for item in evidence:

            if isinstance(
                item,
                dict,
            ):

                claim = item.get(
                    "claim",
                    item.get(
                        "text",
                        "",
                    ),
                )

                supporting = item.get(
                    "evidence",
                    item.get(
                        "text",
                        "",
                    ),
                )

                source = item.get(
                    "source"
                )

                status = normalize_text(
                    item.get(
                        "status",
                        "SUPPORTED",
                    )
                )

                if status in {
                    "failed",
                    "false",
                    "contradicted",
                    "unsupported",
                    "rejected",
                }:

                    supporting = (
                        f"[CONTRADICTED] "
                        f"{supporting}"
                    )

                if claim:

                    yield (
                        normalize_text(
                            claim
                        ),
                        str(
                            supporting
                        ),
                        (
                            str(source)
                            if source
                            else None
                        ),
                    )

            else:

                text = str(
                    item
                ).strip()

                if text:

                    yield (
                        normalize_text(
                            text
                        ),
                        text,
                        None,
                    )


# ============================================================
# LOCAL RETRIEVER
# ============================================================

def _build_retriever(
    evidence: Any,
):
    """
    Build the existing local evidence retriever.

    Retrieval remains optional and lazy.
    """

    try:

        from app.core.evidence_retriever import (
            EvidenceRetriever,
        )

        return EvidenceRetriever(
            evidence=evidence,
            top_k=DEFAULT_RETRIEVAL_TOP_K,
            min_score=DEFAULT_RETRIEVAL_THRESHOLD,
        )

    except Exception:

        return None


# ============================================================
# WEB RETRIEVER
# ============================================================

def _build_web_retriever():
    """
    Build the existing web evidence retriever lazily.

    No external request is made during engine construction.
    """

    try:

        from app.core.web_evidence_retriever import (
            WebEvidenceRetriever,
        )

        return WebEvidenceRetriever()

    except Exception:

        return None


# ============================================================
# CLAIM MATCHING
# ============================================================

def _claim_matches_evidence(
    claim: str,
    evidence_claim: str,
) -> bool:
    """
    Conservative exact/containment matching.

    Semantic similarity alone does not establish truth.
    """

    claim_normalized = normalize_text(
        claim
    )

    evidence_normalized = normalize_text(
        evidence_claim
    )

    if not claim_normalized:
        return False

    if not evidence_normalized:
        return False

    if (
        claim_normalized
        ==
        evidence_normalized
    ):
        return True

    if (
        claim_normalized
        in
        evidence_normalized
    ):
        return True

    if (
        evidence_normalized
        in
        claim_normalized
    ):
        return True

    # --------------------------------------------------------
    # Relation-level equivalence
    # --------------------------------------------------------
    # LLMs often add harmless discourse words such as "indeed",
    # "actually" or "really". Compare simple subject/object
    # relations after the same normalization used by the
    # deterministic contradiction detector.
    claim_relation = _extract_simple_relation(claim_normalized)
    evidence_relation = _extract_simple_relation(evidence_normalized)

    if (
        claim_relation is not None
        and evidence_relation is not None
        and claim_relation == evidence_relation
    ):
        return True

    return False


# ============================================================
# TOKEN SUPPORT
# ============================================================

def _claim_token_coverage(
    claim: str,
    evidence: str,
) -> float:
    """
    Calculate conservative token coverage.
    """

    claim_tokens = {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            normalize_text(
                claim
            ),
        )
        if len(token) > 2
    }

    if not claim_tokens:
        return 0.0

    evidence_normalized = normalize_text(
        evidence
    )

    matched = sum(
        token in evidence_normalized
        for token in claim_tokens
    )

    return (
        matched
        /
        len(claim_tokens)
    )


def _extract_simple_relation(
    text: Any,
) -> Optional[Tuple[str, str]]:
    """Extract a conservative subject/object pair from simple factual statements."""

    normalized = normalize_text(text)

    if not normalized:
        return None

    normalized = re.sub(
        r"^[\s\-\*\•\d\.\)]+",
        "",
        normalized,
    ).strip()

    normalized = re.sub(
        r"^(the|a|an)\s+",
        "",
        normalized,
    ).strip()

    # Natural LLM wording such as "is indeed a star" and
    # "is actually a star" expresses the same relation as
    # "is a star". Remove these discourse fillers before
    # deterministic subject/object comparison.
    normalized = re.sub(
        r"\b(is|are|was|were)\s+(?:indeed|actually|really|simply|basically)\s+",
        r"\1 ",
        normalized,
        flags=re.IGNORECASE,
    )

    normalized = normalized.rstrip(".!?;:").strip()

    match = re.match(
        r"^(.*?)\s+(?:is|are|was|were)\s+(.+?)$",
        normalized,
    )

    if not match:
        return None

    subject = re.sub(r"\s+", " ", match.group(1)).strip()
    obj = re.sub(r"\s+", " ", match.group(2)).strip()

    if not subject or not obj:
        return None

    if len(re.findall(r"[a-z0-9]+", subject)) < 1:
        return None

    return subject, obj


def _find_deterministic_contradiction(
    claim: str,
    evidence_rows: Iterable[Tuple[str, str, Optional[str]]],
) -> Optional[Dict[str, Any]]:
    """Find clear contradictions in configured evidence without semantic RAG."""

    claim_relation = _extract_simple_relation(claim)

    if claim_relation is None:
        return None

    claim_subject, claim_object = claim_relation
    claim_object = normalize_text(claim_object)

    for evidence_claim, evidence_text, source in evidence_rows:

        evidence_text_normalized = normalize_text(evidence_text)

        if evidence_text_normalized.startswith("[contradicted]"):
            candidate_text = evidence_text[len("[CONTRADICTED] "):]
        else:
            candidate_text = evidence_text

        evidence_relation = _extract_simple_relation(evidence_claim)
        if evidence_relation is None:
            evidence_relation = _extract_simple_relation(candidate_text)

        if evidence_relation is None:
            continue

        evidence_subject, evidence_object = evidence_relation

        if normalize_text(evidence_subject) != claim_subject:
            continue

        evidence_object = normalize_text(evidence_object)

        if evidence_object == claim_object:
            continue

        return {
            "claim": evidence_claim,
            "evidence": candidate_text,
            "source": source,
            "status": "CONTRADICTED",
            "similarity": 1.0,
            "claim_support": -1.0,
        }

    return None


def _relation_support_score(
    claim: str,
    evidence: str,
) -> float:
    """
    Conservative relation score.

    Positive values indicate textual support.
    Negative values indicate explicit contradiction.
    """

    claim_normalized = normalize_text(
        claim
    )

    evidence_normalized = normalize_text(
        evidence
    )

    if not claim_normalized:
        return 0.0

    if not evidence_normalized:
        return 0.0

    if (
        claim_normalized
        in
        evidence_normalized
    ):

        return 1.0

    coverage = _claim_token_coverage(
        claim,
        evidence,
    )

    return (
        coverage
        -
        0.5
    )


# ============================================================
# SOURCE QUALITY
# ============================================================

def _domain_from_url(
    url: Any,
) -> str:
    """
    Extract a normalized domain from a URL.
    """

    if not url:
        return ""

    value = str(
        url
    ).strip().lower()

    value = re.sub(
        r"^https?://",
        "",
        value,
    )

    value = value.split(
        "/",
        1,
    )[0]

    value = value.split(
        ":",
        1,
    )[0]

    return value


def _source_quality(
    result: Dict[str, Any],
) -> float:
    """
    Determine source quality.
    """

    if not isinstance(
        result,
        dict,
    ):

        return (
            SOURCE_QUALITY_RULES[
                "unknown"
            ]
        )

    source_type = normalize_text(
        result.get(
            "source_type",
            result.get(
                "type",
                "",
            ),
        )
    )

    if source_type in SOURCE_QUALITY_RULES:

        return SOURCE_QUALITY_RULES[
            source_type
        ]

    domain = _domain_from_url(
        result.get(
            "url"
        )
    )

    if not domain:

        return SOURCE_QUALITY_RULES[
            "unknown"
        ]

    for high_domain in HIGH_AUTHORITY_DOMAINS:

        if (
            domain == high_domain
            or
            domain.endswith(
                "." + high_domain
            )
        ):

            return SOURCE_QUALITY_RULES[
                "government"
                if high_domain
                in {
                    "nasa.gov",
                    "who.int",
                    "un.org",
                    "worldbank.org",
                    "imf.org",
                    "oecd.org",
                    "europa.eu",
                    "gov.in",
                    "india.gov.in",
                }
                else
                "official_institution"
            ]

    for domain_name in ACADEMIC_DOMAINS:

        if (
            domain == domain_name
            or
            domain.endswith(
                "." + domain_name
            )
        ):

            return SOURCE_QUALITY_RULES[
                "academic"
            ]

    for domain_name in MAJOR_NEWS_DOMAINS:

        if (
            domain == domain_name
            or
            domain.endswith(
                "." + domain_name
            )
        ):

            return SOURCE_QUALITY_RULES[
                "major_news"
            ]

    for domain_name in REFERENCE_DOMAINS:

        if (
            domain == domain_name
            or
            domain.endswith(
                "." + domain_name
            )
        ):

            return SOURCE_QUALITY_RULES[
                "reference"
            ]

    for domain_name in LOW_QUALITY_DOMAINS:

        if (
            domain == domain_name
            or
            domain.endswith(
                "." + domain_name
            )
        ):

            return SOURCE_QUALITY_RULES[
                "social"
            ]

    return SOURCE_QUALITY_RULES[
        "unknown"
    ]


# ============================================================
# WEB RESULT SUPPORT
# ============================================================

def _web_result_supports_claim(
    claim: str,
    result: Dict[str, Any],
) -> bool:
    """
    Conservative web support check.

    Requirements:

        1. similarity >= threshold
        2. explicit textual support
        3. sufficient claim-token coverage
    """

    if not isinstance(
        result,
        dict,
    ):

        return False

    try:

        similarity = float(
            result.get(
                "similarity",
                0.0,
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):

        return False

    if (
        similarity
        <
        DEFAULT_WEB_THRESHOLD
    ):

        return False

    claim_normalized = normalize_text(
        claim
    )

    text_normalized = normalize_text(
        result.get(
            "text",
            "",
        )
    )

    if not claim_normalized:
        return False

    if not text_normalized:
        return False

    if (
        claim_normalized
        in
        text_normalized
    ):

        return True

    coverage = _claim_token_coverage(
        claim,
        text_normalized,
    )

    return (
        coverage
        >=
        DEFAULT_MIN_TOKEN_COVERAGE
    )


# ============================================================
# WEB RESULT CONTRADICTION
# ============================================================

def _web_result_contradicts_claim(
    claim: str,
    result: Dict[str, Any],
) -> bool:
    """
    Conservative web contradiction detection.
    """

    if not isinstance(
        result,
        dict,
    ):

        return False

    try:

        similarity = float(
            result.get(
                "similarity",
                0.0,
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):

        return False

    if (
        similarity
        <
        DEFAULT_WEB_THRESHOLD
    ):

        return False

    text = normalize_text(
        result.get(
            "text",
            "",
        )
    )

    if not text:
        return False

    relation_score = (
        _relation_support_score(
            claim,
            text,
        )
    )

    return (
        relation_score
        <
        0.0
    )


# ============================================================
# WEB RESULT RANKING
# ============================================================

def _rank_web_results(
    claim: str,
    results: Any,
) -> List[
    Dict[str, Any]
]:

    if not isinstance(
        results,
        list,
    ):

        return []

    ranked = []

    for result in results:

        if not isinstance(
            result,
            dict,
        ):

            continue

        try:

            similarity = float(
                result.get(
                    "similarity",
                    0.0,
                )
                or 0.0
            )

        except (
            TypeError,
            ValueError,
        ):

            similarity = 0.0

        source_quality = (
            _source_quality(
                result
            )
        )

        claim_support = (
            1.0
            if _web_result_supports_claim(
                claim,
                result,
            )
            else
            (
                -1.0
                if _web_result_contradicts_claim(
                    claim,
                    result,
                )
                else 0.0
            )
        )

        ranking_score = (
            (
                DEFAULT_WEB_RELEVANCE_WEIGHT
                * similarity
            )
            +
            (
                DEFAULT_WEB_SOURCE_QUALITY_WEIGHT
                * source_quality
            )
            +
            (
                DEFAULT_WEB_SUPPORT_WEIGHT
                * claim_support
            )
        )

        item = dict(
            result
        )

        item[
            "source_quality"
        ] = float(
            source_quality
        )

        item[
            "claim_support"
        ] = float(
            claim_support
        )

        item[
            "ranking_score"
        ] = float(
            ranking_score
        )

        ranked.append(
            item
        )

    ranked.sort(
        key=lambda item: (
            float(
                item.get(
                    "ranking_score",
                    0.0,
                )
                or 0.0
            ),
            float(
                item.get(
                    "similarity",
                    0.0,
                )
                or 0.0
            ),
        ),
        reverse=True,
    )

    return ranked


# ============================================================
# WEB CONSENSUS
# ============================================================

def _web_consensus(
    claim: str,
    ranked_results: List[
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    """
    Evaluate web evidence after claim-level filtering.
    """

    supporting = []

    contradicting = []

    for result in ranked_results:

        if _web_result_supports_claim(
            claim,
            result,
        ):

            supporting.append(
                result
            )

        elif _web_result_contradicts_claim(
            claim,
            result,
        ):

            contradicting.append(
                result
            )

    best_support = (
        supporting[0]
        if supporting
        else None
    )

    best_contradiction = (
        contradicting[0]
        if contradicting
        else None
    )

    best_support_score = float(
        best_support.get(
            "ranking_score",
            0.0,
        )
        or 0.0
    ) if best_support else 0.0

    best_contradiction_score = float(
        best_contradiction.get(
            "ranking_score",
            0.0,
        )
        or 0.0
    ) if best_contradiction else 0.0

    # --------------------------------------------------------
    # Strong contradiction.
    # --------------------------------------------------------

    if (
        best_contradiction is not None
        and
        best_contradiction_score
        >=
        best_support_score
        +
        DEFAULT_WEB_CONFLICT_MARGIN
    ):

        return {
            "status": "CONTRADICTED",
            "supporting_sources": len(
                supporting
            ),
            "contradicting_sources": len(
                contradicting
            ),
            "best_support_score":
                best_support_score,
            "best_contradiction_score":
                best_contradiction_score,
            "best_result":
                best_contradiction,
        }

    # --------------------------------------------------------
    # Multiple strong supporting sources.
    # --------------------------------------------------------

    strong_supporting = [
        item
        for item in supporting
        if float(
            item.get(
                "ranking_score",
                0.0,
            )
            or 0.0
        )
        >=
        DEFAULT_WEB_CONSENSUS_THRESHOLD
    ]

    if (
        len(
            strong_supporting
        )
        >=
        DEFAULT_MIN_SUPPORTING_SOURCES
        and
        best_support_score
        >=
        DEFAULT_WEB_CONSENSUS_THRESHOLD
    ):

        return {
            "status": "VERIFIED",
            "supporting_sources":
                len(
                    strong_supporting
                ),
            "contradicting_sources":
                len(
                    contradicting
                ),
            "best_support_score":
                best_support_score,
            "best_result":
                best_support,
        }

    # --------------------------------------------------------
    # Single extremely strong source.
    # --------------------------------------------------------

    if (
        len(supporting) == 1
        and
        best_support_score
        >=
        DEFAULT_WEB_SINGLE_SOURCE_THRESHOLD
    ):

        return {
            "status": "VERIFIED",
            "supporting_sources": 1,
            "contradicting_sources":
                len(
                    contradicting
                ),
            "best_support_score":
                best_support_score,
            "best_result":
                best_support,
        }

    # --------------------------------------------------------
    # Ambiguous.
    # --------------------------------------------------------

    return {
        "status": "UNKNOWN",
        "supporting_sources":
            len(
                supporting
            ),
        "contradicting_sources":
            len(
                contradicting
            ),
        "best_support_score":
            best_support_score,
        "best_contradiction_score":
            best_contradiction_score,
        "best_result":
            best_support,
    }


# ============================================================
# LOCAL + WEB VERIFICATION
# ============================================================

def verify_claims(
    claims: Any,
    evidence: Any = None,
    retriever: Any = None,
    web_retriever: Any = None,
) -> Dict[str, Any]:

    started = time.perf_counter()

    normalized_claims = (
        _normalize_claim_collection(
            claims
        )
    )

    evidence_store = load_evidence(
        evidence
    )

    evidence_rows = list(
        _iter_evidence(
            evidence_store
        )
    )

    # --------------------------------------------------------
    # No claims.
    # --------------------------------------------------------

    if not normalized_claims:

        return {
            "status": "NO_CLAIMS",
            "claims": [],
            "verified_count": 0,
            "failed_count": 0,
            "unknown_count": 0,
            "evidence_count":
                len(
                    evidence_rows
                ),
            "retrieval": {
                "enabled":
                    retriever is not None,
                "top_k":
                    DEFAULT_RETRIEVAL_TOP_K,
                "min_similarity":
                    DEFAULT_RETRIEVAL_THRESHOLD,
            },
            "web_fallback": {
                "enabled": True,
                "provider": "tavily",
                "top_k":
                    DEFAULT_WEB_TOP_K,
                "min_similarity":
                    DEFAULT_WEB_THRESHOLD,
                "used": False,
            },
            "verification_counts": {
                "local_verified": 0,
                "local_failed": 0,
                "web_verified": 0,
            },
            "details": [],
            "latency_ms": (
                time.perf_counter()
                - started
            ) * 1000,
        }

    # --------------------------------------------------------
    # Build local retriever.
    # --------------------------------------------------------

    if retriever is None:

        retriever = _build_retriever(
            evidence_store
        )

    details = []

    verified_count = 0

    failed_count = 0

    unknown_count = 0

    local_verified_count = 0

    local_failed_count = 0

    web_verified_count = 0

    # ========================================================
    # CLAIM-BY-CLAIM VERIFICATION
    # ========================================================

    for claim in normalized_claims:

        retrieved = []

        # ====================================================
        # 1. EXACT CONFIGURED EVIDENCE
        # ====================================================

        exact_supported = None

        exact_contradicted = None

        for (
            evidence_claim,
            evidence_text,
            source,
        ) in evidence_rows:

            if not _claim_matches_evidence(
                claim,
                evidence_claim,
            ):

                continue

            if (
                normalize_text(
                    evidence_text
                ).startswith(
                    "[contradicted]"
                )
            ):

                if (
                    exact_contradicted
                    is None
                ):

                    exact_contradicted = {
                        "claim":
                            evidence_claim,
                        "evidence":
                            evidence_text.replace(
                                "[CONTRADICTED] ",
                                "",
                                1,
                            ),
                        "source":
                            source,
                        "status":
                            "CONTRADICTED",
                        "similarity":
                            1.0,
                    }

            else:

                if (
                    exact_supported
                    is None
                ):

                    exact_supported = {
                        "claim":
                            evidence_claim,
                        "evidence":
                            evidence_text,
                        "source":
                            source,
                        "status":
                            "SUPPORTED",
                        "similarity":
                            1.0,
                    }

        # ----------------------------------------------------
        # Explicit contradiction wins.
        # ----------------------------------------------------

        if (
            exact_contradicted
            is not None
        ):

            failed_count += 1

            local_failed_count += 1

            details.append(
                {
                    "claim":
                        claim,
                    "status":
                        "FAILED",
                    "reason":
                        (
                            "Claim matched "
                            "explicitly "
                            "contradictory "
                            "local evidence."
                        ),
                    "source":
                        exact_contradicted.get(
                            "source"
                        ),
                    "evidence":
                        exact_contradicted.get(
                            "evidence"
                        ),
                    "similarity":
                        1.0,
                    "retrieved_evidence":
                        retrieved,
                    "verification_source":
                        "LOCAL",
                }
            )

            continue

        # ----------------------------------------------------
        # Local explicit support.
        # ----------------------------------------------------

        if (
            exact_supported
            is not None
        ):

            verified_count += 1

            local_verified_count += 1

            details.append(
                {
                    "claim":
                        claim,
                    "status":
                        "VERIFIED",
                    "reason":
                        (
                            "Claim was explicitly "
                            "supported by local "
                            "evidence."
                        ),
                    "source":
                        exact_supported.get(
                            "source"
                        ),
                    "evidence":
                        exact_supported.get(
                            "evidence"
                        ),
                    "similarity":
                        1.0,
                    "retrieved_evidence":
                        retrieved,
                    "verification_source":
                        "LOCAL",
                }
            )

            continue

        # ====================================================
        # 2. LOCAL RAG
        # ====================================================

        local_decision = {
            "status": "UNKNOWN",
            "best_result": None,
        }

        if retriever is not None:

            try:

                retrieved = (
                    retriever.retrieve(
                        claim,
                        top_k=
                            DEFAULT_RETRIEVAL_TOP_K,
                    )
                    or []
                )

            except Exception:

                retrieved = []

        # ----------------------------------------------------
        # Evaluate retrieved local evidence conservatively.
        # ----------------------------------------------------

        best_local_support = None

        best_local_contradiction = None

        for result in retrieved:

            if not isinstance(
                result,
                dict,
            ):

                continue

            evidence_text = result.get(
                "text",
                result.get(
                    "evidence",
                    "",
                ),
            )

            similarity = float(
                result.get(
                    "similarity",
                    0.0,
                )
                or 0.0
            )

            if (
                similarity
                <
                DEFAULT_RETRIEVAL_THRESHOLD
            ):

                continue

            relation_score = (
                _relation_support_score(
                    claim,
                    evidence_text,
                )
            )

            candidate = {
                **result,
                "similarity":
                    similarity,
                "claim_support":
                    relation_score,
            }

            if (
                normalize_text(
                    evidence_text
                ).startswith(
                    "[contradicted]"
                )
                or
                relation_score
                <
                0.0
            ):

                if (
                    best_local_contradiction
                    is None
                    or
                    similarity
                    >
                    float(
                        best_local_contradiction.get(
                            "similarity",
                            0.0,
                        )
                        or 0.0
                    )
                ):

                    best_local_contradiction = (
                        candidate
                    )

            elif (
                relation_score
                >=
                DEFAULT_EXPLICIT_SUPPORT_SCORE
            ):

                if (
                    best_local_support
                    is None
                    or
                    similarity
                    >
                    float(
                        best_local_support.get(
                            "similarity",
                            0.0,
                        )
                        or 0.0
                    )
                ):

                    best_local_support = (
                        candidate
                    )

        if (
            best_local_contradiction
            is not None
        ):

            local_decision = {
                "status":
                    "CONTRADICTED",
                "best_result":
                    best_local_contradiction,
            }

        elif (
            best_local_support
            is not None
        ):

            local_decision = {
                "status":
                    "SUPPORTED",
                "best_result":
                    best_local_support,
            }

        # ----------------------------------------------------
        # Deterministic local-evidence fallback.
        #
        # If semantic retrieval is unavailable or returns no
        # usable result, compare configured evidence at the
        # subject/relation/object level. Existing exact matching
        # and semantic RAG decisions remain unchanged.
        # ----------------------------------------------------

        if (
            local_decision.get(
                "status"
            )
            ==
            "UNKNOWN"
        ):

            fallback_contradiction = (
                _find_deterministic_contradiction(
                    claim,
                    evidence_rows,
                )
            )

            if fallback_contradiction is not None:

                local_decision = {
                    "status":
                        "CONTRADICTED",
                    "best_result":
                        fallback_contradiction,
                }

        # ----------------------------------------------------
        # Local contradiction.
        # ----------------------------------------------------

        if (
            local_decision.get(
                "status"
            )
            ==
            "CONTRADICTED"
        ):

            contradiction = (
                local_decision.get(
                    "best_result"
                )
            )

            failed_count += 1

            local_failed_count += 1

            details.append(
                {
                    "claim":
                        claim,
                    "status":
                        "FAILED",
                    "reason":
                        (
                            "Local evidence "
                            "contradicted "
                            "the claim."
                        ),
                    "source":
                        (
                            contradiction.get(
                                "source"
                            )
                            if contradiction
                            else None
                        ),
                    "evidence":
                        (
                            contradiction.get(
                                "evidence",
                                contradiction.get(
                                    "text",
                                    "",
                                ),
                            )
                            if contradiction
                            else None
                        ),
                    "similarity":
                        (
                            contradiction.get(
                                "similarity"
                            )
                            if contradiction
                            else None
                        ),
                    "retrieved_evidence":
                        retrieved,
                    "verification_source":
                        "LOCAL",
                }
            )

            continue

        # ----------------------------------------------------
        # Local explicit support.
        # ----------------------------------------------------

        if (
            local_decision.get(
                "status"
            )
            ==
            "SUPPORTED"
        ):

            supported = (
                local_decision.get(
                    "best_result"
                )
            )

            verified_count += 1

            local_verified_count += 1

            details.append(
                {
                    "claim":
                        claim,
                    "status":
                        "VERIFIED",
                    "reason":
                        (
                            "Claim was explicitly "
                            "supported by local "
                            "evidence."
                        ),
                    "source":
                        (
                            supported.get(
                                "source"
                            )
                            if supported
                            else None
                        ),
                    "evidence":
                        (
                            supported.get(
                                "evidence",
                                supported.get(
                                    "text",
                                    "",
                                ),
                            )
                            if supported
                            else None
                        ),
                    "similarity":
                        (
                            supported.get(
                                "similarity"
                            )
                            if supported
                            else None
                        ),
                    "retrieved_evidence":
                        retrieved,
                    "verification_source":
                        "LOCAL",
                }
            )

            continue

        # ====================================================
        # 3. TAVILY FALLBACK
        #
        # Reached ONLY when local evidence is UNKNOWN.
        # ====================================================

        web_results = []

        web_error = None

        if web_retriever is None:

            web_retriever = (
                _build_web_retriever()
            )

        if web_retriever is not None:

            try:

                web_results = (
                    web_retriever.retrieve(
                        claim,
                        top_k=
                            DEFAULT_WEB_TOP_K,
                    )
                    or []
                )

            except Exception as exc:

                web_results = []

                web_error = str(
                    exc
                )

        else:

            web_error = (
                "Web evidence retriever "
                "unavailable."
            )

        # ====================================================
        # 4. WEB SOURCE QUALITY + RANKING
        # ====================================================

        ranked_web_results = (
            _rank_web_results(
                claim,
                web_results,
            )
        )

        # ====================================================
        # 5. WEB CONSENSUS
        # ====================================================

        consensus = _web_consensus(
            claim,
            ranked_web_results,
        )

        # ----------------------------------------------------
        # Web VERIFIED.
        # ----------------------------------------------------

        if (
            consensus.get(
                "status"
            )
            ==
            "VERIFIED"
        ):

            best_result = (
                consensus.get(
                    "best_result"
                )
            )

            if not best_result:

                unknown_count += 1

                details.append(
                    {
                        "claim":
                            claim,
                        "status":
                            "UNKNOWN",
                        "reason":
                            (
                                "Web retrieval "
                                "returned evidence "
                                "but no valid "
                                "claim-supporting "
                                "result could be "
                                "selected."
                            ),
                        "source":
                            None,
                        "retrieved_evidence":
                            retrieved,
                        "web_evidence":
                            ranked_web_results,
                        "web_consensus":
                            consensus,
                        "web_error":
                            web_error,
                        "verification_source":
                            "UNKNOWN",
                    }
                )

                continue

            verified_count += 1

            web_verified_count += 1

            details.append(
                {
                    "claim":
                        claim,
                    "status":
                        "VERIFIED",
                    "reason":
                        (
                            "Local evidence was "
                            "inconclusive; web "
                            "evidence was verified "
                            "using claim-level "
                            "support, relevance, "
                            "source quality, and "
                            "consensus."
                        ),
                    "source":
                        best_result.get(
                            "source"
                        ),
                    "title":
                        best_result.get(
                            "title"
                        ),
                    "url":
                        best_result.get(
                            "url"
                        ),
                    "evidence":
                        best_result.get(
                            "text",
                            "",
                        ),
                    "similarity":
                        best_result.get(
                            "similarity"
                        ),
                    "source_quality":
                        best_result.get(
                            "source_quality"
                        ),
                    "claim_support":
                        best_result.get(
                            "claim_support"
                        ),
                    "ranking_score":
                        best_result.get(
                            "ranking_score"
                        ),
                    "retrieved_evidence":
                        retrieved,
                    "web_evidence":
                        ranked_web_results,
                    "web_consensus":
                        consensus,
                    "verification_source":
                        "TAVILY",
                }
            )

            continue

        # ----------------------------------------------------
        # Web contradiction.
        # ----------------------------------------------------

        if (
            consensus.get(
                "status"
            )
            ==
            "CONTRADICTED"
        ):

            contradiction = (
                consensus.get(
                    "best_result"
                )
            )

            failed_count += 1

            details.append(
                {
                    "claim":
                        claim,
                    "status":
                        "FAILED",
                    "reason":
                        (
                            "Local evidence was "
                            "inconclusive; web "
                            "evidence explicitly "
                            "contradicted the claim."
                        ),
                    "source":
                        (
                            contradiction.get(
                                "source"
                            )
                            if contradiction
                            else None
                        ),
                    "title":
                        (
                            contradiction.get(
                                "title"
                            )
                            if contradiction
                            else None
                        ),
                    "url":
                        (
                            contradiction.get(
                                "url"
                            )
                            if contradiction
                            else None
                        ),
                    "evidence":
                        (
                            contradiction.get(
                                "text",
                                "",
                            )
                            if contradiction
                            else None
                        ),
                    "similarity":
                        (
                            contradiction.get(
                                "similarity"
                            )
                            if contradiction
                            else None
                        ),
                    "source_quality":
                        (
                            contradiction.get(
                                "source_quality"
                            )
                            if contradiction
                            else None
                        ),
                    "claim_support":
                        (
                            contradiction.get(
                                "claim_support"
                            )
                            if contradiction
                            else None
                        ),
                    "ranking_score":
                        (
                            contradiction.get(
                                "ranking_score"
                            )
                            if contradiction
                            else None
                        ),
                    "retrieved_evidence":
                        retrieved,
                    "web_evidence":
                        ranked_web_results,
                    "web_consensus":
                        consensus,
                    "web_error":
                        web_error,
                    "verification_source":
                        "TAVILY",
                }
            )

            continue

        # ====================================================
        # STILL UNKNOWN
        # ====================================================

        unknown_count += 1

        max_web_ranking_score = None

        if ranked_web_results:

            max_web_ranking_score = max(
                float(
                    item.get(
                        "ranking_score",
                        0.0,
                    )
                    or 0.0
                )
                for item
                in ranked_web_results
            )

        details.append(
            {
                "claim":
                    claim,
                "status":
                    "UNKNOWN",
                "reason":
                    (
                        "Local evidence could not "
                        "establish the claim and "
                        "web evidence was insufficient "
                        "to establish the same "
                        "factual relation."
                    ),
                "source":
                    None,
                "retrieved_evidence":
                    retrieved,
                "web_evidence":
                    ranked_web_results,
                "web_consensus":
                    consensus,
                "web_error":
                    web_error,
                "best_web_ranking_score":
                    max_web_ranking_score,
                "verification_source":
                    "UNKNOWN",
            }
        )

    # ========================================================
    # AGGREGATE STATUS
    # ========================================================

    if failed_count > 0:

        if (
            failed_count
            ==
            len(
                normalized_claims
            )
        ):

            status = "FAILED"

        else:

            status = "PARTIAL"

    elif (
        verified_count
        ==
        len(
            normalized_claims
        )
    ):

        status = "VERIFIED"

    elif verified_count > 0:

        status = "PARTIAL"

    else:

        status = "UNKNOWN"

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "status":
            status,

        "claims":
            normalized_claims,

        "verified_count":
            verified_count,

        "failed_count":
            failed_count,

        "unknown_count":
            unknown_count,

        "evidence_count":
            len(
                evidence_rows
            ),

        "retrieval": {
            "enabled":
                retriever is not None,
            "top_k":
                DEFAULT_RETRIEVAL_TOP_K,
            "min_similarity":
                DEFAULT_RETRIEVAL_THRESHOLD,
        },

        "web_fallback": {
            "enabled":
                True,
            "provider":
                "tavily",
            "top_k":
                DEFAULT_WEB_TOP_K,
            "min_similarity":
                DEFAULT_WEB_THRESHOLD,
            "used":
                any(
                    item.get(
                        "verification_source"
                    )
                    ==
                    "TAVILY"
                    for item
                    in details
                ),
        },

        "web_ranking": {
            "enabled":
                True,
            "relevance_weight":
                DEFAULT_WEB_RELEVANCE_WEIGHT,
            "source_quality_weight":
                DEFAULT_WEB_SOURCE_QUALITY_WEIGHT,
            "claim_support_weight":
                DEFAULT_WEB_SUPPORT_WEIGHT,
            "strong_threshold":
                DEFAULT_WEB_STRONG_RANKING_THRESHOLD,
        },

        "web_consensus": {
            "enabled":
                True,
            "minimum_supporting_sources":
                DEFAULT_MIN_SUPPORTING_SOURCES,
            "consensus_result_threshold":
                DEFAULT_WEB_CONSENSUS_THRESHOLD,
            "single_source_threshold":
                DEFAULT_WEB_SINGLE_SOURCE_THRESHOLD,
            "conflict_margin":
                DEFAULT_WEB_CONFLICT_MARGIN,
        },

        "claim_support": {
            "enabled":
                True,
            "min_token_coverage":
                DEFAULT_MIN_TOKEN_COVERAGE,
            "explicit_support_score":
                DEFAULT_EXPLICIT_SUPPORT_SCORE,
            "explicit_contradiction_score":
                DEFAULT_EXPLICIT_CONTRADICTION_SCORE,
        },

        "verification_counts": {
            "local_verified":
                local_verified_count,
            "local_failed":
                local_failed_count,
            "web_verified":
                web_verified_count,
        },

        "details":
            details,

        "latency_ms": (
            time.perf_counter()
            - started
        ) * 1000,
    }


# ============================================================
# PUBLIC FACTUALITY ENGINE
# ============================================================

class FactualityEngine:
    """
    Stable object interface used by
    ControlPlane's FactualityAgent.
    """

    def __init__(
        self,
        evidence: Any = None,
    ):

        self.evidence = (
            load_evidence(
                evidence
            )
        )

        # ----------------------------------------------------
        # Local RAG
        # ----------------------------------------------------

        self.retriever = (
            _build_retriever(
                self.evidence
            )
        )

        # ----------------------------------------------------
        # Web retriever remains lazy.
        #
        # No Tavily request is performed during construction.
        # ----------------------------------------------------

        self.web_retriever = None

    # ========================================================
    # CLAIM EXTRACTION
    # ========================================================

    def extract_claims(
        self,
        text: str,
    ) -> List[str]:

        return extract_claims(
            text
        )

    # ========================================================
    # VERIFICATION
    # ========================================================

    def verify_claims(
        self,
        claims: Any,
        evidence: Any = None,
    ) -> Dict[str, Any]:

        if evidence is None:

            evidence = self.evidence

        return verify_claims(
            claims,
            evidence,
            self.retriever,
            self.web_retriever,
        )

    # ========================================================
    # SCAN
    # ========================================================

    def scan(
        self,
        text: str,
    ) -> Dict[str, Any]:

        claims = (
            self.extract_claims(
                text
            )
        )

        verification = (
            self.verify_claims(
                claims
            )
        )

        return {
            "claims":
                claims,
            "verification":
                verification,
        }

    # ========================================================
    # HEALTH
    # ========================================================

    def health(
        self,
    ) -> Dict[str, Any]:

        web_health = None

        try:

            from app.core.web_evidence_retriever import (
                WebEvidenceRetriever,
            )

            web_health = (
                WebEvidenceRetriever()
                .health()
            )

        except Exception as exc:

            web_health = {
                "status":
                    "unavailable",
                "error":
                    str(exc),
            }

        return {
            "status":
                "healthy",

            "local_rag": {
                "enabled":
                    self.retriever is not None,
                "top_k":
                    DEFAULT_RETRIEVAL_TOP_K,
                "min_score":
                    DEFAULT_RETRIEVAL_THRESHOLD,
            },

            "web_fallback":
                web_health,

            "web_ranking": {
                "enabled":
                    True,
                "relevance_weight":
                    DEFAULT_WEB_RELEVANCE_WEIGHT,
                "source_quality_weight":
                    DEFAULT_WEB_SOURCE_QUALITY_WEIGHT,
                "claim_support_weight":
                    DEFAULT_WEB_SUPPORT_WEIGHT,
                "strong_threshold":
                    DEFAULT_WEB_STRONG_RANKING_THRESHOLD,
            },

            "web_consensus": {
                "enabled":
                    True,
                "minimum_supporting_sources":
                    DEFAULT_MIN_SUPPORTING_SOURCES,
                "consensus_result_threshold":
                    DEFAULT_WEB_CONSENSUS_THRESHOLD,
                "single_source_threshold":
                    DEFAULT_WEB_SINGLE_SOURCE_THRESHOLD,
                "conflict_margin":
                    DEFAULT_WEB_CONFLICT_MARGIN,
            },

            "claim_support": {
                "enabled":
                    True,
                "min_token_coverage":
                    DEFAULT_MIN_TOKEN_COVERAGE,
                "explicit_support_score":
                    DEFAULT_EXPLICIT_SUPPORT_SCORE,
                "explicit_contradiction_score":
                    DEFAULT_EXPLICIT_CONTRADICTION_SCORE,
            },
        }