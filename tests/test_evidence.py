from app.evidence import (
    EvidenceDocument,
    EvidenceStore,
    ClaimExtractor,
    EvidenceRetriever,
    EvidenceVerifier,
)


def build_verifier():

    documents = [

        EvidenceDocument(
            document_id="india_001",
            title="India Capital",
            content=(
                "The capital of India is New Delhi."
            ),
            source="trusted_internal"
        ),

        EvidenceDocument(
            document_id="python_001",
            title="Python",
            content=(
                "Python is a high-level programming "
                "language widely used in data science."
            ),
            source="trusted_internal"
        ),
    ]

    store = EvidenceStore(
        documents
    )

    retriever = EvidenceRetriever(
        store
    )

    return EvidenceVerifier(
        retriever
    )


def test_evidence_store():

    store = EvidenceStore()

    document = EvidenceDocument(
        document_id="test",
        title="Test",
        content="This is evidence."
    )

    store.add(
        document
    )

    assert store.get(
        "test"
    ) is not None

    assert len(
        store.all()
    ) == 1


def test_claim_extraction():

    extractor = ClaimExtractor()

    claims = extractor.extract(
        "The capital of India is New Delhi."
    )

    assert len(
        claims
    ) == 1

    assert (
        "New Delhi"
        in claims[0]["text"]
    )


def test_question_is_not_claim():

    extractor = ClaimExtractor()

    claims = extractor.extract(
        "What is the capital of India?"
    )

    assert claims == []


def test_supported_claim():

    verifier = build_verifier()

    result = verifier.verify_claim(
        "The capital of India is New Delhi."
    )

    assert result["status"] == "VERIFIED"


def test_unsupported_claim():

    verifier = build_verifier()

    result = verifier.verify_claim(
        "The capital of India is Mumbai."
    )

    assert result["status"] in {
        "PARTIAL",
        "UNSUPPORTED"
    }


def test_no_evidence():

    verifier = build_verifier()

    result = verifier.verify_claim(
        "The population of Mars is exactly "
        "123456789 people."
    )

    assert result["status"] in {
        "NO_EVIDENCE",
        "UNSUPPORTED",
        "PARTIAL"
    }


def test_multiple_claims():

    verifier = build_verifier()

    claims = [
        {
            "text":
                "The capital of India is New Delhi."
        },
        {
            "text":
                "Python is a programming language."
        }
    ]

    result = verifier.verify_claims(
        claims
    )

    assert len(
        result["claims"]
    ) == 2

    assert result["status"] in {
        "VERIFIED",
        "PARTIAL"
    }