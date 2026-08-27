"""
ControlPlane.ai Evidence Retriever

Semantic evidence retrieval layer for factuality verification.

Responsibilities:
    1. Load evidence documents.
    2. Convert evidence into semantic embeddings.
    3. Retrieve the most relevant evidence for a claim.
    4. Return evidence with similarity scores and provenance.
    5. Keep retrieval separate from factuality decision logic.

This module does NOT decide whether a claim is true or false.

It only answers:

    "What evidence is most relevant to this claim?"
"""

from __future__ import annotations

import hashlib
import json
import time

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


DEFAULT_EVIDENCE_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "evidence.json"
)

DEFAULT_INDEX_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "evidence_index.npz"
)

DEFAULT_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

DEFAULT_TOP_K = 5

DEFAULT_MIN_SCORE = 0.55


class EvidenceRetriever:
    """
    Semantic evidence retriever.

    Uses SentenceTransformer embeddings and cosine similarity.

    The retriever is intentionally independent from the
    FactualityAgent so it can later be replaced by:

        - FAISS
        - Chroma
        - Qdrant
        - Milvus
        - Elasticsearch
        - managed vector databases

    without changing the factuality agent contract.
    """

    def __init__(
        self,
        evidence_file: Optional[str] = None,
        index_file: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
    ):
        self.evidence_file = Path(
            evidence_file
            if evidence_file
            else DEFAULT_EVIDENCE_FILE
        )

        self.index_file = Path(
            index_file
            if index_file
            else DEFAULT_INDEX_FILE
        )

        self.model_name = str(
            model_name
        )

        self.top_k = max(
            1,
            int(top_k),
        )

        self.min_score = float(
            min_score
        )

        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError(
                "min_score must be between 0.0 and 1.0."
            )

        self.model = None

        self.documents: List[
            Dict[str, Any]
        ] = []

        self.embeddings: Optional[
            np.ndarray
        ] = None

        self.index_metadata: Dict[
            str, Any
        ] = {}

        # Simple in-process query embedding cache.
        self._query_cache: Dict[
            str, np.ndarray
        ] = {}

        self._max_query_cache_size = 256

        self._load_model()

        self._load_or_build_index()

    # =========================================================
    # MODEL
    # =========================================================

    def _load_model(self) -> None:

        try:

            from sentence_transformers import (
                SentenceTransformer,
            )

        except ImportError as exc:

            raise RuntimeError(
                "sentence-transformers is required "
                "for semantic evidence retrieval."
            ) from exc

        self.model = SentenceTransformer(
            self.model_name
        )

    # =========================================================
    # EVIDENCE LOADING
    # =========================================================

    def _load_evidence(
        self,
    ) -> List[Dict[str, Any]]:

        if not self.evidence_file.exists():

            return []

        try:

            with self.evidence_file.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "Evidence file contains invalid JSON: "
                f"{self.evidence_file}"
            ) from exc

        except OSError as exc:

            raise RuntimeError(
                "Failed to read evidence file: "
                f"{self.evidence_file}"
            ) from exc

        return self._normalize_documents(
            data
        )

    # =========================================================
    # NORMALIZATION
    # =========================================================

    def _normalize_documents(
        self,
        data: Any,
    ) -> List[Dict[str, Any]]:

        documents = []

        if isinstance(data, dict):

            items = data.get(
                "claims",
                [],
            )

        elif isinstance(data, list):

            items = data

        else:

            items = []

        if not isinstance(items, list):

            return []

        for index, item in enumerate(
            items
        ):

            if isinstance(
                item,
                dict,
            ):

                claim = str(
                    item.get(
                        "claim",
                        "",
                    )
                ).strip()

                evidence = str(
                    item.get(
                        "evidence",
                        item.get(
                            "text",
                            "",
                        ),
                    )
                ).strip()

                source = item.get(
                    "source"
                )

                if source is not None:
                    source = str(
                        source
                    ).strip()

                status = str(
                    item.get(
                        "status",
                        "SUPPORTED",
                    )
                ).upper().strip()

                # Preserve optional provenance fields.
                metadata = item.get(
                    "metadata",
                    {},
                )

                if not isinstance(
                    metadata,
                    dict,
                ):
                    metadata = {}

            else:

                claim = str(
                    item
                ).strip()

                evidence = claim

                source = None

                status = "SUPPORTED"

                metadata = {}

            if not claim and not evidence:

                continue

            text = (
                evidence
                if evidence
                else claim
            )

            documents.append(
                {
                    "id": str(index),
                    "claim": claim,
                    "evidence": evidence,
                    "source": source,
                    "status": status,
                    "text": text,
                    "metadata": metadata,
                }
            )

        return documents

    # =========================================================
    # INDEX FINGERPRINT
    # =========================================================

    def _calculate_corpus_hash(
        self,
    ) -> str:

        payload = json.dumps(
            self.documents,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            payload.encode(
                "utf-8"
            )
        ).hexdigest()

    # =========================================================
    # INDEX MANAGEMENT
    # =========================================================

    def _load_or_build_index(
        self,
    ) -> None:

        self.documents = (
            self._load_evidence()
        )

        if not self.documents:

            self.embeddings = np.empty(
                (0, 0),
                dtype=np.float32,
            )

            self.index_metadata = {}

            return

        corpus_hash = (
            self._calculate_corpus_hash()
        )

        if self._can_load_index(
            corpus_hash
        ):

            try:

                data = np.load(
                    self.index_file,
                    allow_pickle=False,
                )

                embeddings = data[
                    "embeddings"
                ]

                if (
                    embeddings.ndim == 2
                    and embeddings.shape[0]
                    == len(self.documents)
                ):

                    self.embeddings = (
                        embeddings.astype(
                            np.float32
                        )
                    )

                    self.index_metadata = {
                        "corpus_hash": corpus_hash,
                        "model_name": self.model_name,
                        "document_count": len(
                            self.documents
                        ),
                    }

                    return

            except Exception:

                # Corrupt or incompatible index.
                # Rebuild safely.
                pass

        self._build_index(
            corpus_hash=corpus_hash
        )

    def _can_load_index(
        self,
        corpus_hash: str,
    ) -> bool:

        if not self.index_file.exists():
            return False

        try:

            data = np.load(
                self.index_file,
                allow_pickle=False,
            )

            stored_hash = str(
                data["corpus_hash"].item()
            )

            stored_model = str(
                data["model_name"].item()
            )

            stored_count = int(
                data["document_count"].item()
            )

            return (
                stored_hash
                == corpus_hash
                and stored_model
                == self.model_name
                and stored_count
                == len(self.documents)
            )

        except Exception:

            return False

    def _build_index(
        self,
        corpus_hash: Optional[str] = None,
    ) -> None:

        if not self.documents:

            self.embeddings = np.empty(
                (0, 0),
                dtype=np.float32,
            )

            return

        texts = [
            document["text"]
            for document
            in self.documents
        ]

        try:

            embeddings = (
                self.model.encode(
                    texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )
            )

        except Exception as exc:

            raise RuntimeError(
                "Failed to generate evidence embeddings."
            ) from exc

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        if embeddings.ndim != 2:

            raise RuntimeError(
                "Evidence embedding matrix "
                "has an invalid shape."
            )

        if embeddings.shape[0] != len(
            self.documents
        ):

            raise RuntimeError(
                "Evidence embedding count does not "
                "match document count."
            )

        self.embeddings = embeddings

        self.index_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if corpus_hash is None:

            corpus_hash = (
                self._calculate_corpus_hash()
            )

        np.savez_compressed(
            self.index_file,
            embeddings=self.embeddings,
            corpus_hash=np.array(
                corpus_hash
            ),
            model_name=np.array(
                self.model_name
            ),
            document_count=np.array(
                len(self.documents)
            ),
        )

        self.index_metadata = {
            "corpus_hash": corpus_hash,
            "model_name": self.model_name,
            "document_count": len(
                self.documents
            ),
        }

    # =========================================================
    # REBUILD
    # =========================================================

    def rebuild(
        self,
    ) -> Dict[str, Any]:

        started = time.perf_counter()

        self.documents = (
            self._load_evidence()
        )

        if not self.documents:

            self.embeddings = np.empty(
                (0, 0),
                dtype=np.float32,
            )

            self.index_metadata = {}

            return {
                "status": "REBUILT",
                "document_count": 0,
                "latency_ms": (
                    time.perf_counter()
                    - started
                ) * 1000,
            }

        self._build_index(
            corpus_hash=(
                self._calculate_corpus_hash()
            )
        )

        self._query_cache.clear()

        return {
            "status": "REBUILT",
            "document_count": len(
                self.documents
            ),
            "latency_ms": (
                time.perf_counter()
                - started
            ) * 1000,
        }

    # =========================================================
    # QUERY EMBEDDING
    # =========================================================

    def _encode_query(
        self,
        query: str,
    ) -> np.ndarray:

        cached = self._query_cache.get(
            query
        )

        if cached is not None:

            return cached

        try:

            embedding = (
                self.model.encode(
                    [query],
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )[0]
            )

        except Exception as exc:

            raise RuntimeError(
                "Failed to generate query embedding."
            ) from exc

        embedding = np.asarray(
            embedding,
            dtype=np.float32,
        )

        if len(
            self._query_cache
        ) >= self._max_query_cache_size:

            oldest_key = next(
                iter(
                    self._query_cache
                )
            )

            del self._query_cache[
                oldest_key
            ]

        self._query_cache[
            query
        ] = embedding

        return embedding

    # =========================================================
    # RETRIEVAL
    # =========================================================

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:

        started = time.perf_counter()

        if not isinstance(
            query,
            str,
        ):

            return []

        query = query.strip()

        if not query:

            return []

        if (
            self.embeddings is None
            or len(self.documents) == 0
        ):

            return []

        k = (
            self.top_k
            if top_k is None
            else max(
                1,
                int(top_k),
            )
        )

        threshold = (
            self.min_score
            if min_score is None
            else float(min_score)
        )

        if not 0.0 <= threshold <= 1.0:

            raise ValueError(
                "min_score must be between 0.0 and 1.0."
            )

        query_embedding = (
            self._encode_query(
                query
            )
        )

        scores = np.dot(
            self.embeddings,
            query_embedding,
        )

        indices = np.argsort(
            -scores,
            kind="stable",
        )

        results = []

        for index in indices:

            if len(results) >= k:
                break

            score = float(
                scores[index]
            )

            if score < threshold:
                continue

            document = dict(
                self.documents[
                    int(index)
                ]
            )

            document[
                "similarity"
            ] = score

            document[
                "retrieval_latency_ms"
            ] = (
                time.perf_counter()
                - started
            ) * 1000

            results.append(
                document
            )

        return results

    # =========================================================
    # HEALTH
    # =========================================================

    def health(
        self,
    ) -> Dict[str, Any]:

        return {
            "status": "healthy",
            "model": self.model_name,
            "document_count": len(
                self.documents
            ),
            "embedding_dimension": (
                int(
                    self.embeddings.shape[1]
                )
                if (
                    self.embeddings is not None
                    and self.embeddings.ndim == 2
                    and self.embeddings.shape[0] > 0
                )
                else 0
            ),
            "top_k": self.top_k,
            "min_score": self.min_score,
            "index_file": str(
                self.index_file
            ),
            "index_metadata": (
                dict(
                    self.index_metadata
                )
            ),
            "query_cache_size": len(
                self._query_cache
            ),
        }