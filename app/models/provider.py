from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import json
import time
from urllib import request as urllib_request
from urllib import error as urllib_error

from app.core.config import settings


# ============================================================
# STANDARD MODEL RESPONSE
# ============================================================

@dataclass
class ModelResponse:
    """
    Standardized response returned by every model provider.

    This keeps the provider layer independent from the
    underlying LLM vendor.
    """

    text: str

    input_tokens: int = 0

    output_tokens: int = 0

    latency_ms: float = 0.0

    model: str = "unknown"

    provider: str = "unknown"

    cost: float = 0.0

    metadata: Optional[Dict[str, Any]] = None

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
    Base interface for every model used behind ControlPlane.

    ControlPlane governance does not depend on a specific
    LLM provider.
    """

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ):
        raise NotImplementedError


# ============================================================
# MOCK MODEL PROVIDER
# ============================================================

class MockModelProvider(ModelProvider):
    """
    Existing development provider.

    This behavior is intentionally preserved so all existing
    tests and local development continue to work.
    """

    def __init__(
        self,
        model_name: str = "mock-model"
    ):

        self.model_name = model_name

    def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:

        start = time.perf_counter()

        user_message = ""

        if isinstance(messages, list):

            for message in messages:

                if not isinstance(
                    message,
                    dict
                ):
                    continue

                if message.get("role") == "user":

                    user_message = message.get(
                        "content",
                        ""
                    )

        elif isinstance(messages, str):

            user_message = messages

        else:

            user_message = str(messages)

        response = (
            "Mock response generated for: "
            f"{user_message}"
        )

        latency_ms = (
            time.perf_counter()
            - start
        ) * 1000

        input_tokens = len(
            user_message.split()
        )

        output_tokens = len(
            response.split()
        )

        return {
            "text": response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "model": self.model_name,
            "provider": "mock",
            "cost": 0.0,
            "metadata": {
                "mock": True
            }
        }


# ============================================================
# OPENAI-COMPATIBLE PROVIDER
# ============================================================

class OpenAICompatibleProvider(ModelProvider):
    """
    Provider for OpenAI-compatible chat-completions APIs.

    This works with providers such as OpenRouter and can also
    be configured for OpenAI-compatible endpoints later.

    No OpenAI SDK dependency is required; the standard Python
    HTTP client is used so the existing requirements remain
    unchanged.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        provider_name: str = "openrouter",
    ):

        self.api_key = (
            api_key
            if api_key is not None
            else getattr(
                settings,
                "MODEL_API_KEY",
                None
            )
        )

        self.model_name = (
            model_name
            if model_name is not None
            else getattr(
                settings,
                "MODEL_NAME",
                "openrouter/free"
            )
        )

        self.base_url = (
            base_url
            if base_url is not None
            else getattr(
                settings,
                "MODEL_BASE_URL",
                "https://openrouter.ai/api/v1"
            )
        )

        self.temperature = (
            temperature
            if temperature is not None
            else getattr(
                settings,
                "MODEL_TEMPERATURE",
                0.2
            )
        )

        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else getattr(
                settings,
                "MODEL_MAX_TOKENS",
                512
            )
        )

        self.timeout = (
            timeout
            if timeout is not None
            else getattr(
                settings,
                "MODEL_TIMEOUT_SECONDS",
                60.0
            )
        )

        self.provider_name = provider_name

        self.endpoint = (
            self.base_url.rstrip("/")
            + "/chat/completions"
        )

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:

        if not self.api_key:

            raise RuntimeError(
                "MODEL_API_KEY is not configured. "
                "Set MODEL_API_KEY in the .env file."
            )

        if not isinstance(
            messages,
            list
        ):

            if isinstance(
                messages,
                str
            ):

                messages = [
                    {
                        "role": "user",
                        "content": messages
                    }
                ]

            else:

                raise TypeError(
                    "messages must be a list "
                    "or string."
                )

        temperature = kwargs.get(
            "temperature",
            self.temperature
        )

        max_tokens = kwargs.get(
            "max_tokens",
            self.max_tokens
        )

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        encoded_payload = json.dumps(
            payload
        ).encode("utf-8")

        headers = {
            "Authorization": (
                f"Bearer {self.api_key}"
            ),
            "Content-Type": (
                "application/json"
            ),
        }

        # ----------------------------------------------------
        # OpenRouter-specific optional headers.
        # They are harmless for the OpenRouter endpoint.
        # ----------------------------------------------------

        if self.provider_name == "openrouter":

            headers[
                "HTTP-Referer"
            ] = "http://127.0.0.1:8000"

            headers[
                "X-Title"
            ] = "ControlPlane.ai"

        http_request = urllib_request.Request(
            self.endpoint,
            data=encoded_payload,
            headers=headers,
            method="POST",
        )

        started = time.perf_counter()

        try:

            with urllib_request.urlopen(
                http_request,
                timeout=self.timeout
            ) as response:

                response_body = (
                    response.read()
                    .decode("utf-8")
                )

                status_code = (
                    response.status
                )

        except urllib_error.HTTPError as exc:

            try:

                error_body = (
                    exc.read()
                    .decode("utf-8")
                )

            except Exception:

                error_body = str(exc)

            raise RuntimeError(
                "LLM provider request failed "
                f"(HTTP {exc.code}): "
                f"{error_body}"
            ) from exc

        except urllib_error.URLError as exc:

            raise RuntimeError(
                "Unable to connect to LLM provider: "
                f"{exc.reason}"
            ) from exc

        except TimeoutError as exc:

            raise RuntimeError(
                "LLM provider request timed out."
            ) from exc

        latency_ms = (
            time.perf_counter()
            - started
        ) * 1000

        # ----------------------------------------------------
        # Parse response.
        # ----------------------------------------------------

        try:

            data = json.loads(
                response_body
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "LLM provider returned invalid JSON."
            ) from exc

        # ----------------------------------------------------
        # Extract assistant text.
        # ----------------------------------------------------

        try:

            choices = data.get(
                "choices",
                []
            )

            if not choices:

                raise ValueError(
                    "Provider response contains "
                    "no choices."
                )

            message = choices[0].get(
                "message",
                {}
            )

            text = message.get(
                "content",
                ""
            )

        except Exception as exc:

            raise RuntimeError(
                "Unable to extract model response "
                "from provider payload."
            ) from exc

        if text is None:

            text = ""

        text = str(text)

        # ----------------------------------------------------
        # Token usage.
        # ----------------------------------------------------

        usage = data.get(
            "usage",
            {}
        )

        if not isinstance(
            usage,
            dict
        ):

            usage = {}

        input_tokens = int(
            usage.get(
                "prompt_tokens",
                0
            ) or 0
        )

        output_tokens = int(
            usage.get(
                "completion_tokens",
                0
            ) or 0
        )

        total_tokens = int(
            usage.get(
                "total_tokens",
                input_tokens + output_tokens
            ) or (
                input_tokens
                + output_tokens
            )
        )

        # ----------------------------------------------------
        # Provider-reported cost.
        #
        # OpenRouter may expose cost in usage.
        # If unavailable, keep it at zero rather than
        # inventing a price.
        # ----------------------------------------------------

        raw_cost = usage.get(
            "cost",
            0.0
        )

        try:

            cost = float(
                raw_cost or 0.0
            )

        except (
            TypeError,
            ValueError,
        ):

            cost = 0.0

        returned_model = data.get(
            "model",
            self.model_name
        )

        # ----------------------------------------------------
        # Return the existing dictionary format.
        #
        # ModelGateway already knows how to normalize this.
        # ----------------------------------------------------

        return {

            "text": text,

            "input_tokens": input_tokens,

            "output_tokens": output_tokens,

            "latency_ms": latency_ms,

            "model": str(
                returned_model
            ),

            "provider": self.provider_name,

            "cost": cost,

            "metadata": {

                "mock": False,

                "status_code": status_code,

                "endpoint": self.endpoint,

                "usage": usage,

                "total_tokens": total_tokens,

                "provider_response_id": (
                    data.get("id")
                ),

                "finish_reason": (
                    choices[0].get(
                        "finish_reason"
                    )
                ),
            },
        }


# ============================================================
# PROVIDER FACTORY
# ============================================================

def create_model_provider(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> ModelProvider:
    """
    Create the configured model provider.

    Supported values:

        mock
        openrouter
        openai

    The provider is selected entirely through configuration,
    so the rest of ControlPlane remains unchanged.
    """

    configured_provider = (
        provider
        if provider is not None
        else getattr(
            settings,
            "MODEL_PROVIDER",
            "mock"
        )
    )

    provider_name = (
        str(
            configured_provider
        )
        .strip()
        .lower()
    )

    configured_model = (
        model_name
        if model_name is not None
        else getattr(
            settings,
            "MODEL_NAME",
            "mock-model"
        )
    )

    # --------------------------------------------------------
    # Existing mock behavior.
    # --------------------------------------------------------

    if provider_name == "mock":

        return MockModelProvider(
            model_name=configured_model
        )

    # --------------------------------------------------------
    # OpenRouter.
    # --------------------------------------------------------

    if provider_name == "openrouter":

        return OpenAICompatibleProvider(
            api_key=getattr(
                settings,
                "MODEL_API_KEY",
                None
            ),
            model_name=configured_model,
            base_url=getattr(
                settings,
                "MODEL_BASE_URL",
                "https://openrouter.ai/api/v1"
            ),
            temperature=getattr(
                settings,
                "MODEL_TEMPERATURE",
                0.2
            ),
            max_tokens=getattr(
                settings,
                "MODEL_MAX_TOKENS",
                512
            ),
            timeout=getattr(
                settings,
                "MODEL_TIMEOUT_SECONDS",
                60.0
            ),
            provider_name="openrouter",
        )

    # --------------------------------------------------------
    # OpenAI-compatible configuration.
    # --------------------------------------------------------

    if provider_name == "openai":

        return OpenAICompatibleProvider(
            api_key=getattr(
                settings,
                "MODEL_API_KEY",
                None
            ),
            model_name=configured_model,
            base_url=getattr(
                settings,
                "MODEL_BASE_URL",
                "https://api.openai.com/v1"
            ),
            temperature=getattr(
                settings,
                "MODEL_TEMPERATURE",
                0.2
            ),
            max_tokens=getattr(
                settings,
                "MODEL_MAX_TOKENS",
                512
            ),
            timeout=getattr(
                settings,
                "MODEL_TIMEOUT_SECONDS",
                60.0
            ),
            provider_name="openai",
        )

    raise ValueError(
        "Unsupported MODEL_PROVIDER: "
        f"{configured_provider}. "
        "Supported providers are: "
        "mock, openrouter, openai."
    )


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "ModelResponse",
    "ModelProvider",
    "MockModelProvider",
    "OpenAICompatibleProvider",
    "create_model_provider",
]