import re
from typing import Any, Dict, List

from app.evidence.store import (
    EvidenceDocument,
    EvidenceStore
)


class EvidenceRetriever:
    """
    Evidence retrieval layer.

    Current implementation:
        lexical similarity

    Production extension:
        embedding retrieval
        hybrid BM25 + embeddings
        reranking
        source authority weighting
    """

    def __init__(
        self,
        store: EvidenceStore,
        embedder=None
    ):

        self.store = store
        self.embedder = embedder

    def retrieve(
        self,
        claim: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:

        if not claim:

            return []

        documents = self.store.all()

        if not documents:

            return []

        # ----------------------------------------------------
        # Embedding retrieval if an embedder is available
        # ----------------------------------------------------

        if self.embedder is not None:

            try:

                return self._embedding_retrieve(
                    claim,
                    documents,
                    top_k
                )

            except Exception:
                # Fail back to deterministic lexical retrieval.
                pass

        # ----------------------------------------------------
        # Lexical fallback
        # ----------------------------------------------------

        return self._lexical_retrieve(
            claim,
            documents,
            top_k
        )

    def _lexical_retrieve(
        self,
        claim: str,
        documents: List[EvidenceDocument],
        top_k: int
    ) -> List[Dict[str, Any]]:

        terms = {
            term.lower()
            for term in re.findall(
                r"\b[a-zA-Z0-9]+\b",
                claim
            )
            if len(term) > 2
        }

        scored = []

        for document in documents:

            text = (
                document.title
                + " "
                + document.content
            ).lower()

            document_terms = set(
                re.findall(
                    r"\b[a-zA-Z0-9]+\b",
                    text
                )
            )

            if not terms:

                score = 0.0

            else:

                overlap = (
                    len(
                        terms
                        &
                        document_terms
                    )
                    /
                    len(terms)
                )

                score = float(
                    overlap
                )

            if score > 0:

                scored.append(
                    {
                        "document":
                            document,

                        "score":
                            score,

                        "method":
                            "lexical"
                    }
                )

        scored.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        return scored[:top_k]

    def _embedding_retrieve(
        self,
        claim: str,
        documents: List[EvidenceDocument],
        top_k: int
    ) -> List[Dict[str, Any]]:

        import numpy as np

        texts = [
            document.title
            + " "
            + document.content
            for document in documents
        ]

        query_vector = self.embedder.encode(
            [claim],
            normalize_embeddings=True
        )[0]

        document_vectors = self.embedder.encode(
            texts,
            normalize_embeddings=True
        )

        scores = np.dot(
            document_vectors,
            query_vector
        )

        ranked = np.argsort(
            scores
        )[::-1]

        results = []

        for index in ranked[:top_k]:

            results.append(
                {
                    "document":
                        documents[int(index)],

                    "score":
                        float(scores[int(index)]),

                    "method":
                        "embedding"
                }
            )

        return results