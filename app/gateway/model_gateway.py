from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import json
import os
import time
import urllib.request
import urllib.error


# ============================================================
# STANDARD MODEL RESPONSE
# ============================================================

@dataclass
class ModelResponse:
    """
    Standardized response returned by every model provider.
    """

    text: str

    input_tokens: int = 0

    output_tokens: int = 0

    latency_ms: float = 0.0

    model: str = "unknown"

    provider: str = "unknown"

    cost: float = 0.0

    metadata: Dict[str, Any] = None

    def __post_init__(self):

        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:

        return asdict(self)


# ============================================================
# MODEL PROVIDER INTERFACE
# ============================================================

class ModelProvider(ABC):
    """
    Abstract interface for any foundation model.

    ControlPlane should not depend on a specific
    provider such as OpenAI, Anthropic, Gemini, etc.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        **kwargs
    ) -> ModelResponse:

        raise NotImplementedError


# ============================================================
# MOCK MODEL PROVIDER
# ============================================================

class MockModelProvider(ModelProvider):
    """
    Local provider used for development and testing.

    Existing behavior is intentionally preserved.
    """

    def __init__(
        self,
        model_name: str = "mock-model"
    ):

        self.model_name = model_name
        self.provider_name = "mock"

    def generate(
        self,
        prompt: str,
        **kwargs
    ) -> ModelResponse:

        start = time.perf_counter()

        if not isinstance(
            prompt,
            str
        ):

            prompt = str(prompt)

        text = (
            f"Mock response generated for: {prompt}"
        )

        latency_ms = (
            time.perf_counter() - start
        ) * 1000

        input_tokens = len(
            prompt.split()
        )

        output_tokens = len(
            text.split()
        )

        return ModelResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            model=self.model_name,
            provider="mock",
            cost=0.0,
            metadata={
                "mock": True
            }
        )


# ============================================================
# OPENAI-COMPATIBLE PROVIDER
# ============================================================

class OpenAICompatibleProvider(ModelProvider):
    """
    Real LLM provider using an OpenAI-compatible
    Chat Completions HTTP API.

    This supports OpenAI and other providers/endpoints
    exposing the same API shape.

    Configuration is read from environment variables:

        OPENAI_API_KEY
        OPENAI_BASE_URL
        OPENAI_MODEL

    Backward-compatible aliases are also supported:

        MODEL_API_KEY
        MODEL_BASE_URL
        MODEL_NAME
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ):

        self.api_key = (
            api_key
            or os.getenv(
                "OPENAI_API_KEY",
                ""
            )
            or os.getenv(
                "MODEL_API_KEY",
                ""
            )
        ).strip()

        self.model_name = (
            model_name
            or os.getenv(
                "OPENAI_MODEL",
                ""
            )
            or os.getenv(
                "MODEL_NAME",
                ""
            )
            or "gpt-4o-mini"
        ).strip()

        self.base_url = (
            base_url
            or os.getenv(
                "OPENAI_BASE_URL",
                ""
            )
            or os.getenv(
                "MODEL_BASE_URL",
                ""
            )
            or "https://api.openai.com/v1"
        ).strip().rstrip("/")

        self.temperature = (
            self._safe_float(
                temperature,
                os.getenv(
                    "MODEL_TEMPERATURE",
                    "0.2"
                )
            )
        )

        self.max_tokens = (
            self._safe_int(
                max_tokens,
                os.getenv(
                    "MODEL_MAX_TOKENS",
                    "512"
                )
            )
        )

        self.timeout_seconds = (
            self._safe_float(
                timeout_seconds,
                os.getenv(
                    "MODEL_TIMEOUT_SECONDS",
                    "60"
                )
            )
        )

        self.provider_name = "openai"

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        prompt: str,
        **kwargs
    ) -> ModelResponse:

        if not isinstance(
            prompt,
            str
        ):

            prompt = str(prompt)

        if not prompt.strip():

            raise ValueError(
                "prompt cannot be empty."
            )

        if not self.api_key:

            raise RuntimeError(
                "No LLM API key configured. "
                "Set OPENAI_API_KEY or MODEL_API_KEY "
                "in the environment."
            )

        model_name = (
            kwargs.get(
                "model"
            )
            or self.model_name
        )

        temperature = (
            kwargs.get(
                "temperature",
                self.temperature
            )
        )

        max_tokens = (
            kwargs.get(
                "max_tokens",
                self.max_tokens
            )
        )

        timeout = (
            kwargs.get(
                "timeout",
                self.timeout_seconds
            )
        )

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # ----------------------------------------------------
        # REMOVE None VALUES
        # ----------------------------------------------------

        payload = {
            key: value
            for key, value in payload.items()
            if value is not None
        }

        url = (
            f"{self.base_url}/chat/completions"
        )

        request = urllib.request.Request(
            url,
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": (
                    f"Bearer {self.api_key}"
                ),
            },
            method="POST",
        )

        started = time.perf_counter()

        try:

            with urllib.request.urlopen(
                request,
                timeout=float(timeout)
            ) as response:

                raw_body = (
                    response.read()
                    .decode("utf-8")
                )

        except urllib.error.HTTPError as exc:

            try:
                error_body = (
                    exc.read()
                    .decode("utf-8")
                )
            except Exception:
                error_body = str(exc)

            raise RuntimeError(
                "LLM API request failed "
                f"(HTTP {exc.code}): "
                f"{error_body}"
            ) from exc

        except urllib.error.URLError as exc:

            raise RuntimeError(
                "Unable to connect to LLM API: "
                f"{exc}"
            ) from exc

        except TimeoutError as exc:

            raise RuntimeError(
                "LLM API request timed out."
            ) from exc

        latency_ms = (
            time.perf_counter()
            - started
        ) * 1000

        try:

            data = json.loads(
                raw_body
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError
        ) as exc:

            raise RuntimeError(
                "LLM API returned invalid JSON."
            ) from exc

        # ====================================================
        # EXTRACT TEXT
        # ====================================================

        text = ""

        choices = data.get(
            "choices",
            []
        )

        if (
            isinstance(
                choices,
                list
            )
            and choices
        ):

            first_choice = choices[0]

            if isinstance(
                first_choice,
                dict
            ):

                message = first_choice.get(
                    "message",
                    {}
                )

                if isinstance(
                    message,
                    dict
                ):

                    text = message.get(
                        "content",
                        ""
                    )

                if not text:

                    text = first_choice.get(
                        "text",
                        ""
                    )

        if not isinstance(
            text,
            str
        ):

            text = str(
                text
            )

        # ====================================================
        # TOKEN USAGE
        # ====================================================

        usage = data.get(
            "usage",
            {}
        )

        if not isinstance(
            usage,
            dict
        ):

            usage = {}

        input_tokens = (
            usage.get(
                "prompt_tokens",
                usage.get(
                    "input_tokens",
                    0
                )
            )
        )

        output_tokens = (
            usage.get(
                "completion_tokens",
                usage.get(
                    "output_tokens",
                    0
                )
            )
        )

        input_tokens = (
            self._safe_int(
                input_tokens
            )
        )

        output_tokens = (
            self._safe_int(
                output_tokens
            )
        )

        # ====================================================
        # PROVIDER COST
        # ====================================================

        provider_cost = (
            usage.get(
                "cost",
                usage.get(
                    "total_cost",
                    0.0
                )
            )
        )

        provider_cost = (
            self._safe_float(
                provider_cost
            )
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        return ModelResponse(

            text=text,

            input_tokens=(
                input_tokens
            ),

            output_tokens=(
                output_tokens
            ),

            latency_ms=(
                latency_ms
            ),

            model=str(
                data.get(
                    "model",
                    model_name
                )
            ),

            provider="openai",

            cost=(
                provider_cost
            ),

            metadata={
                "usage": usage,
                "finish_reason": (
                    choices[0].get(
                        "finish_reason"
                    )
                    if choices
                    and isinstance(
                        choices[0],
                        dict
                    )
                    else None
                ),
                "api_base_url": (
                    self.base_url
                ),
            }
        )

    # ========================================================
    # PRICING
    # ========================================================

    @property
    def pricing(self):

        return None

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _safe_float(
        value,
        default=0.0
    ) -> float:

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return float(
                default
            )

    @staticmethod
    def _safe_int(
        value,
        default=0
    ) -> int:

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return int(
                default
            )


# ============================================================
# PROVIDER FACTORY
# ============================================================

def create_model_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    **kwargs
) -> ModelProvider:
    """
    Create the configured model provider.

    Existing default remains MOCK.

    Supported:

        mock
        openai
        openai-compatible
        openai_compatible
    """

    provider_name = (
        provider_name
        or os.getenv(
            "MODEL_PROVIDER",
            "mock"
        )
    ).strip().lower()

    model_name = (
        model_name
        or os.getenv(
            "MODEL_NAME",
            ""
        )
    ).strip()

    if provider_name == "mock":

        return MockModelProvider(
            model_name=(
                model_name
                or "mock-model"
            )
        )

    if provider_name in {
        "openai",
        "openai-compatible",
        "openai_compatible",
    }:

        return OpenAICompatibleProvider(
            model_name=(
                model_name
                or None
            ),
            **kwargs
        )

    raise ValueError(
        "Unsupported MODEL_PROVIDER: "
        f"{provider_name}. "
        "Supported providers: mock, openai."
    )


# ============================================================
# DYNAMIC COST CALCULATOR
# ============================================================

class ModelCostCalculator:
    """
    Provider/model-aware model cost calculator.

    Pricing is expressed as USD per 1,000,000 tokens.

    Cost priority:

        1. Provider-reported cost
        2. Provider object's pricing configuration
        3. MODEL_PRICING_JSON environment variable
        4. Development mock pricing for mock provider
        5. 0.0 when no pricing is configured
    """

    MOCK_DEVELOPMENT_PRICING = {

        "input_per_1m": 0.15,

        "output_per_1m": 0.60,
    }

    @classmethod
    def calculate(
        cls,
        provider,
        provider_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        provider_cost: float = 0.0,
    ) -> tuple:

        input_tokens = max(
            cls._integer(
                input_tokens
            ),
            0
        )

        output_tokens = max(
            cls._integer(
                output_tokens
            ),
            0
        )

        provider_cost = max(
            cls._number(
                provider_cost
            ),
            0.0
        )

        # ====================================================
        # 1. PROVIDER REPORTED COST
        # ====================================================

        if provider_cost > 0.0:

            return (
                round(
                    provider_cost,
                    10
                ),
                "provider_reported",
                {
                    "input_tokens": (
                        input_tokens
                    ),
                    "output_tokens": (
                        output_tokens
                    ),
                }
            )

        # ====================================================
        # 2. PROVIDER OBJECT PRICING
        # ====================================================

        pricing = (
            cls._provider_pricing(
                provider
            )
        )

        pricing_source = (
            "provider_configured"
        )

        # ====================================================
        # 3. ENVIRONMENT PRICING
        # ====================================================

        if pricing is None:

            pricing = (
                cls._environment_pricing(
                    provider_name,
                    model_name
                )
            )

            pricing_source = (
                "environment_configured"
            )

        # ====================================================
        # 4. DEVELOPMENT MOCK PRICING
        # ====================================================

        if (
            pricing is None
            and str(
                provider_name
            ).lower()
            == "mock"
        ):

            pricing = (
                cls.MOCK_DEVELOPMENT_PRICING
            )

            pricing_source = (
                "mock_development_pricing"
            )

        # ====================================================
        # NO PRICING AVAILABLE
        # ====================================================

        if pricing is None:

            return (
                0.0,
                "unpriced",
                {
                    "input_tokens": (
                        input_tokens
                    ),
                    "output_tokens": (
                        output_tokens
                    ),
                }
            )

        input_rate = cls._number(
            pricing.get(
                "input_per_1m",
                pricing.get(
                    "input",
                    0.0
                )
            )
        )

        output_rate = cls._number(
            pricing.get(
                "output_per_1m",
                pricing.get(
                    "output",
                    0.0
                )
            )
        )

        input_cost = (
            input_tokens
            / 1_000_000.0
        ) * input_rate

        output_cost = (
            output_tokens
            / 1_000_000.0
        ) * output_rate

        total_cost = (
            input_cost
            + output_cost
        )

        return (
            round(
                total_cost,
                10
            ),
            pricing_source,
            {
                "input_tokens": (
                    input_tokens
                ),

                "output_tokens": (
                    output_tokens
                ),

                "input_per_1m": (
                    input_rate
                ),

                "output_per_1m": (
                    output_rate
                ),

                "input_cost": (
                    round(
                        input_cost,
                        10
                    )
                ),

                "output_cost": (
                    round(
                        output_cost,
                        10
                    )
                ),
            }
        )

    @classmethod
    def _provider_pricing(
        cls,
        provider
    ):

        pricing = getattr(
            provider,
            "pricing",
            None
        )

        if callable(
            pricing
        ):

            pricing = pricing()

        if isinstance(
            pricing,
            dict
        ):

            return pricing

        return None

    @classmethod
    def _environment_pricing(
        cls,
        provider_name,
        model_name
    ):

        raw = os.getenv(
            "MODEL_PRICING_JSON",
            ""
        ).strip()

        if not raw:

            return None

        try:

            data = json.loads(
                raw
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):

            return None

        if not isinstance(
            data,
            dict
        ):

            return None

        provider_name = str(
            provider_name
        ).lower()

        model_name = str(
            model_name
        )

        candidates = [

            data.get(
                f"{provider_name}:{model_name}"
            ),

            data.get(
                f"{provider_name}:{model_name.lower()}"
            ),
        ]

        provider_data = data.get(
            provider_name
        )

        if isinstance(
            provider_data,
            dict
        ):

            candidates.extend(
                [
                    provider_data.get(
                        model_name
                    ),

                    provider_data.get(
                        model_name.lower()
                    ),

                    provider_data.get(
                        "default"
                    ),
                ]
            )

        candidates.append(
            data.get(
                "default"
            )
        )

        for candidate in candidates:

            if isinstance(
                candidate,
                dict
            ):

                return candidate

        return None

    @staticmethod
    def _number(
        value
    ) -> float:

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return 0.0

    @staticmethod
    def _integer(
        value
    ) -> int:

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return 0


# ============================================================
# MODEL GATEWAY
# ============================================================

class ModelGateway:
    """
    Provider-agnostic model gateway.
    """

    def __init__(
        self,
        provider: Optional[ModelProvider] = None
    ):

        if provider is None:

            provider = create_model_provider()

        if provider is None:

            raise ValueError(
                "A model provider is required."
            )

        self.provider = provider

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        prompt: str,
        **kwargs
    ) -> ModelResponse:

        if not isinstance(
            prompt,
            str
        ):

            raise TypeError(
                "prompt must be a string."
            )

        prompt = prompt.strip()

        if not prompt:

            raise ValueError(
                "prompt cannot be empty."
            )

        started = time.perf_counter()

        response = (
            self._invoke_provider(
                prompt=prompt,
                kwargs=kwargs
            )
        )

        gateway_latency = (
            time.perf_counter()
            - started
        ) * 1000

        if isinstance(
            response,
            ModelResponse
        ):

            result = response

        elif isinstance(
            response,
            str
        ):

            result = ModelResponse(
                text=response,
                latency_ms=(
                    gateway_latency
                ),
                model="unknown",
                provider=(
                    getattr(
                        self.provider,
                        "provider_name",
                        type(
                            self.provider
                        ).__name__
                    )
                )
            )

        elif isinstance(
            response,
            dict
        ):

            result = (
                self._normalize_dict_response(
                    response=response,
                    gateway_latency=(
                        gateway_latency
                    )
                )
            )

        elif hasattr(
            response,
            "text"
        ):

            result = ModelResponse(

                text=str(
                    getattr(
                        response,
                        "text",
                        ""
                    )
                ),

                latency_ms=(
                    self._safe_float(
                        getattr(
                            response,
                            "latency_ms",
                            gateway_latency
                        ),
                        gateway_latency
                    )
                ),

                model=str(
                    getattr(
                        response,
                        "model",
                        "unknown"
                    )
                ),

                provider=str(
                    getattr(
                        response,
                        "provider",
                        type(
                            self.provider
                        ).__name__
                    )
                ),

                input_tokens=(
                    self._safe_int(
                        getattr(
                            response,
                            "input_tokens",
                            0
                        )
                    )
                ),

                output_tokens=(
                    self._safe_int(
                        getattr(
                            response,
                            "output_tokens",
                            0
                        )
                    )
                ),

                cost=(
                    self._safe_float(
                        getattr(
                            response,
                            "cost",
                            0.0
                        )
                    )
                ),

                metadata=(
                    self._safe_metadata(
                        getattr(
                            response,
                            "metadata",
                            {}
                        )
                    )
                )
            )

        else:

            raise TypeError(
                "Model provider returned an "
                "unsupported response type: "
                f"{type(response).__name__}"
            )

        # ====================================================
        # DYNAMIC COST
        # ====================================================

        calculated_cost, cost_source, cost_details = (
            ModelCostCalculator.calculate(

                provider=self.provider,

                provider_name=(
                    result.provider
                ),

                model_name=(
                    result.model
                ),

                input_tokens=(
                    result.input_tokens
                ),

                output_tokens=(
                    result.output_tokens
                ),

                provider_cost=(
                    result.cost
                ),
            )
        )

        result.cost = (
            calculated_cost
        )

        result.metadata = (
            self._safe_metadata(
                result.metadata
            )
        )

        result.metadata.update(
            {

                "cost_source": (
                    cost_source
                ),

                "cost": (
                    calculated_cost
                ),

                "estimated_cost": (
                    calculated_cost
                ),

                "token_count": (
                    max(
                        int(
                            result.input_tokens
                            or 0
                        ),
                        0
                    )
                    +
                    max(
                        int(
                            result.output_tokens
                            or 0
                        ),
                        0
                    )
                ),

                "cost_details": (
                    cost_details
                ),
            }
        )

        try:

            if (
                result.latency_ms <= 0
            ):

                result.latency_ms = (
                    gateway_latency
                )

        except (
            AttributeError,
            TypeError
        ):

            result.latency_ms = (
                gateway_latency
            )

        return result

    # ========================================================
    # PROVIDER INVOCATION
    # ========================================================

    def _invoke_provider(
        self,
        prompt: str,
        kwargs: Dict[str, Any]
    ):

        try:

            return self.provider.generate(
                prompt,
                **kwargs
            )

        except AttributeError as first_exc:

            error_text = str(
                first_exc
            )

            if (
                "'str' object has no attribute 'get'"
                not in error_text
            ):

                raise

            try:

                return self.provider.generate(
                    [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    **kwargs
                )

            except AttributeError as second_exc:

                second_error = str(
                    second_exc
                )

                if (
                    "'str' object has no attribute 'get'"
                    not in second_error
                ):

                    raise

                return self.provider.generate(
                    {
                        "prompt": prompt
                    },
                    **kwargs
                )

    # ========================================================
    # DICTIONARY NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_dict_response(
        response: dict,
        gateway_latency: float
    ) -> ModelResponse:

        def safe_get(
            key,
            default=None
        ):

            try:

                return response.get(
                    key,
                    default
                )

            except (
                AttributeError,
                TypeError
            ):

                return default

        text = safe_get(
            "text"
        )

        if text is None:

            text = safe_get(
                "content"
            )

        if text is None:

            text = safe_get(
                "response"
            )

        if text is None:

            text = safe_get(
                "output"
            )

        if text is None:

            text = ""

        choices = safe_get(
            "choices"
        )

        if (
            isinstance(
                choices,
                list
            )
            and choices
        ):

            first = choices[0]

            if isinstance(
                first,
                dict
            ):

                message = first.get(
                    "message"
                )

                if isinstance(
                    message,
                    dict
                ):

                    content = (
                        message.get(
                            "content"
                        )
                    )

                    if content is not None:

                        text = content

                elif first.get(
                    "text"
                ) is not None:

                    text = first.get(
                        "text"
                    )

                elif first.get(
                    "content"
                ) is not None:

                    text = first.get(
                        "content"
                    )

        if not isinstance(
            text,
            str
        ):

            text = str(
                text
            )

        usage = safe_get(
            "usage",
            {}
        )

        if not isinstance(
            usage,
            dict
        ):

            usage = {}

        input_tokens = safe_get(
            "input_tokens",
            usage.get(
                "prompt_tokens",
                usage.get(
                    "input_tokens",
                    0
                )
            )
        )

        output_tokens = safe_get(
            "output_tokens",
            usage.get(
                "completion_tokens",
                usage.get(
                    "output_tokens",
                    0
                )
            )
        )

        latency_ms = safe_get(
            "latency_ms",
            gateway_latency
        )

        cost = safe_get(
            "cost",
            usage.get(
                "cost",
                usage.get(
                    "total_cost",
                    0.0
                )
            )
        )

        input_tokens = (
            ModelGateway._safe_int(
                input_tokens
            )
        )

        output_tokens = (
            ModelGateway._safe_int(
                output_tokens
            )
        )

        latency_ms = (
            ModelGateway._safe_float(
                latency_ms,
                gateway_latency
            )
        )

        cost = (
            ModelGateway._safe_float(
                cost
            )
        )

        model = safe_get(
            "model",
            "unknown"
        )

        provider = safe_get(
            "provider",
            "unknown"
        )

        metadata = (
            ModelGateway._safe_metadata(
                safe_get(
                    "metadata",
                    {}
                )
            )
        )

        metadata.setdefault(
            "usage",
            usage
        )

        return ModelResponse(

            text=text,

            input_tokens=(
                input_tokens
            ),

            output_tokens=(
                output_tokens
            ),

            latency_ms=(
                latency_ms
            ),

            model=str(
                model
            ),

            provider=str(
                provider
            ),

            cost=(
                cost
            ),

            metadata=(
                metadata
            )
        )

    # ========================================================
    # SAFE HELPERS
    # ========================================================

    @staticmethod
    def _safe_metadata(
        metadata
    ) -> Dict[str, Any]:

        if isinstance(
            metadata,
            dict
        ):

            return metadata

        return {
            "raw_metadata": metadata
        }

    @staticmethod
    def _safe_float(
        value,
        default=0.0
    ) -> float:

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return float(
                default
            )

    @staticmethod
    def _safe_int(
        value
    ) -> int:

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return 0

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    def health_check(
        self
    ) -> Dict[str, Any]:

        return {

            "healthy": (
                self.provider
                is not None
            ),

            "provider": type(
                self.provider
            ).__name__,
        }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "ModelResponse",
    "ModelProvider",
    "MockModelProvider",
    "OpenAICompatibleProvider",
    "create_model_provider",
    "ModelGateway",
    "ModelCostCalculator",
]