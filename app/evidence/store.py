from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EvidenceDocument:
    """
    A single trusted evidence document.

    In the prototype this is an in-memory store.
    Later this can be backed by:
        - PostgreSQL
        - Elasticsearch
        - Chroma
        - FAISS
        - enterprise document stores
    """

    document_id: str
    title: str
    content: str
    source: str = "internal"
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "document_id": self.document_id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "metadata": self.metadata,
        }


class EvidenceStore:
    """
    Simple evidence repository.

    Designed as a clean abstraction so the retrieval layer
    does not care where evidence actually comes from.
    """

    def __init__(
        self,
        documents: List[EvidenceDocument] | None = None
    ):

        self._documents: Dict[
            str,
            EvidenceDocument
        ] = {}

        if documents:

            for document in documents:

                self.add(
                    document
                )

    def add(
        self,
        document: EvidenceDocument
    ) -> None:

        if not isinstance(
            document,
            EvidenceDocument
        ):
            raise TypeError(
                "document must be EvidenceDocument"
            )

        self._documents[
            document.document_id
        ] = document

    def remove(
        self,
        document_id: str
    ) -> bool:

        return (
            self._documents.pop(
                document_id,
                None
            )
            is not None
        )

    def get(
        self,
        document_id: str
    ) -> EvidenceDocument | None:

        return self._documents.get(
            document_id
        )

    def all(
        self
    ) -> List[EvidenceDocument]:

        return list(
            self._documents.values()
        )

    def search_text(
        self,
        query: str
    ) -> List[EvidenceDocument]:

        """
        Lightweight lexical retrieval.

        This is intentionally deterministic and dependency-free.
        The Retriever layer can later replace this with embeddings.
        """

        if not query:

            return []

        query_terms = {
            term.lower()
            for term in query.split()
            if len(term) > 2
        }

        if not query_terms:

            return []

        scored = []

        for document in self._documents.values():

            searchable = (
                document.title
                + " "
                + document.content
            ).lower()

            score = sum(
                term in searchable
                for term in query_terms
            )

            if score > 0:

                scored.append(
                    (
                        score,
                        document
                    )
                )

        scored.sort(
            key=lambda item: item[0],
            reverse=True
        )

        return [
            document
            for _, document
            in scored
        ]