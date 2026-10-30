from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # =========================================================
    # APPLICATION
    # =========================================================

    APP_NAME: str = "ControlPlane.ai"

    ENVIRONMENT: str = "development"

    DEBUG: bool = True

    # =========================================================
    # MODEL
    # =========================================================
    #
    # Provider-agnostic configuration.
    #
    # Examples:
    #
    #   MODEL_PROVIDER=mock
    #   MODEL_PROVIDER=openrouter
    #   MODEL_PROVIDER=openai
    #
    # The rest of ControlPlane should not need to know
    # which provider is being used.
    # =========================================================

    MODEL_PROVIDER: str = "mock"

    MODEL_NAME: str = "mock-model"

    MODEL_API_KEY: str | None = None

    MODEL_BASE_URL: str | None = None

    MODEL_TEMPERATURE: float = 0.2

    MODEL_MAX_TOKENS: int = 512

    MODEL_TIMEOUT_SECONDS: float = 60.0

    # =========================================================
    # GOVERNANCE
    # =========================================================

    DEFAULT_RISK_THRESHOLD: float = 0.50

    DEFAULT_COST_BUDGET: float = 0.01

    # EXPERIMENTAL. Enforce the per-profile policy engine (risk /
    # uncertainty / cost / factuality thresholds and the
    # consequential-action rule) on top of the agents. Its factuality
    # and uncertainty rules are not yet calibrated: even with a working
    # evidence source it can send or block ordinary answers, so it is
    # off by default.
    POLICY_ENGINE_ENABLED: bool = False

    # =========================================================
    # API
    # =========================================================

    API_HOST: str = "127.0.0.1"

    API_PORT: int = 8000

    # =========================================================
    # API HARDENING (all optional; disabled by default)
    # =========================================================

    # When set, mutating endpoints (/api/generate and
    # /api/reviews/{id}/resolve) require a matching
    # X-API-Key header.
    API_KEY: str | None = None

    # Maximum requests per client per minute on mutating
    # endpoints. 0 disables rate limiting.
    RATE_LIMIT_PER_MINUTE: int = 0

    # Maximum accepted prompt length (characters).
    MAX_PROMPT_CHARS: int = 8000

    # Comma-separated list of extra browser origins allowed
    # by CORS (the dashboard is same-origin by default).
    CORS_ORIGINS: str = (
        "http://127.0.0.1:5500,http://localhost:5500"
    )

    LOG_LEVEL: str = "INFO"

    # =========================================================
    # FACTUALITY / RAG
    # =========================================================

    FACTUALITY_ENABLED: bool = True

    FACTUALITY_EMBEDDING_MODEL: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    FACTUALITY_TOP_K: int = 5

    FACTUALITY_MIN_SIMILARITY: float = 0.55

    FACTUALITY_MAX_CLAIMS: int = 20

    # =========================================================
    # EVIDENCE
    # =========================================================

    EVIDENCE_FILE: str = "data/evidence.json"

    EVIDENCE_INDEX_FILE: str = "data/evidence_index.npz"

    # =========================================================
    # MODEL / HUGGING FACE
    # =========================================================

    HF_TOKEN: str | None = None

    # =========================================================
    # SETTINGS CONFIGURATION
    # =========================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()