"""LLM service for managing LLM calls with retries and fallback mechanisms.

Groq is the $0 default provider (free tier, no credit card required, but a
free API key from console.groq.com/keys is required - Groq's client
validates this eagerly, so a missing key fails fast with a clear message
rather than a confusing error deep in the SDK). OpenAI models are only
added to the registry if OPENAI_API_KEY is explicitly set, so a fresh
checkout never silently depends on a paid API.
"""

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import groq
import openai
import logging
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger

# Transient errors worth retrying the same model for, across both providers.
RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIError,
    groq.RateLimitError,
    groq.APITimeoutError,
    groq.APIError,
)

# Broader provider-level errors that mean "this model/provider failed,
# move to the next one in the fallback chain" rather than "retry the same
# call". Both openai.OpenAIError and groq.GroqError are the root exception
# type each SDK raises for anything going wrong with a request.
PROVIDER_ERRORS = (openai.OpenAIError, groq.GroqError)


def _build_llm_registry() -> List[Dict[str, Any]]:
    """Build the list of available LLM models based on which API keys are configured.

    Groq models are always included - they are the $0 default. Groq's
    client validates its API key eagerly at construction time (unlike
    OpenAI's, which only fails on the actual call), so a missing
    GROQ_API_KEY is rejected here with a clear, actionable message rather
    than letting a confusing error surface from deep inside the groq SDK.
    Note this is a free signup requirement, not a paid one - see
    console.groq.com/keys, no credit card required.

    OpenAI models are included only if settings.OPENAI_API_KEY is
    non-empty, so an unconfigured OPENAI_API_KEY never silently becomes a
    required paid dependency.

    Returns:
        List[Dict[str, Any]]: Registry entries, each with a "name" and a
        pre-initialized "llm" instance.

    Raises:
        RuntimeError: If GROQ_API_KEY is not set.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. OpsMind's $0 default LLM provider is "
            "Groq's free tier - get a free API key (no credit card required) "
            "at https://console.groq.com/keys and set GROQ_API_KEY in your "
            ".env file."
        )

    registry: List[Dict[str, Any]] = [
        {
            "name": "openai/gpt-oss-120b",
            "llm": ChatGroq(
                model="openai/gpt-oss-120b",
                api_key=settings.GROQ_API_KEY,
                temperature=settings.DEFAULT_LLM_TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
            ),
        },
        {
            "name": "openai/gpt-oss-20b",
            "llm": ChatGroq(
                model="openai/gpt-oss-20b",
                api_key=settings.GROQ_API_KEY,
                temperature=settings.DEFAULT_LLM_TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
            ),
        },
    ]

    if settings.OPENAI_API_KEY:
        registry.extend(
            [
                {
                    "name": "gpt-5-mini",
                    "llm": ChatOpenAI(
                        model="gpt-5-mini",
                        api_key=settings.OPENAI_API_KEY,
                        max_tokens=settings.MAX_TOKENS,
                        reasoning={"effort": "low"},
                    ),
                },
                {
                    "name": "gpt-4o-mini",
                    "llm": ChatOpenAI(
                        model="gpt-4o-mini",
                        temperature=settings.DEFAULT_LLM_TEMPERATURE,
                        api_key=settings.OPENAI_API_KEY,
                        max_tokens=settings.MAX_TOKENS,
                        top_p=0.9 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
                    ),
                },
            ]
        )
        logger.info("openai_models_added_to_registry", reason="OPENAI_API_KEY is set")
    else:
        logger.info("openai_models_skipped", reason="OPENAI_API_KEY is not set - $0 default, Groq only")

    return registry


class LLMRegistry:
    """Registry of available LLM models with pre-initialized instances.

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    LLMS: List[Dict[str, Any]] = _build_llm_registry()

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name with optional argument overrides.

        Args:
            model_name: Name of the model to retrieve
            **kwargs: Optional arguments to override default model configuration

        Returns:
            BaseChatModel instance

        Raises:
            ValueError: If model_name is not found in LLMS
        """
        model_entry = None
        for entry in cls.LLMS:
            if entry["name"] == model_name:
                model_entry = entry
                break

        if not model_entry:
            available_models = [entry["name"] for entry in cls.LLMS]
            raise ValueError(
                f"model '{model_name}' not found in registry. available models: {', '.join(available_models)}"
            )

        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            is_openai_model = model_name.startswith("gpt-")
            if is_openai_model:
                return ChatOpenAI(model=model_name, api_key=settings.OPENAI_API_KEY, **kwargs)
            return ChatGroq(model=model_name, api_key=settings.GROQ_API_KEY, **kwargs)

        logger.debug("using_default_llm_instance", model_name=model_name)
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get all registered LLM names in order.

        Returns:
            List of LLM names
        """
        return [entry["name"] for entry in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Get model entry at specific index.

        Args:
            index: Index of the model in LLMS list

        Returns:
            Model entry dict
        """
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]  # Wrap around to first model


class LLMService:
    """Service for managing LLM calls with retries and circular fallback.

    This service handles all LLM interactions with automatic retry logic,
    rate limit handling, and circular fallback through all available models
    across both Groq (the $0 default) and OpenAI (only present if
    configured).
    """

    def __init__(self):
        """Initialize the LLM service."""
        self._llm: Optional[BaseChatModel] = None
        self._current_model_index: int = 0

        all_names = LLMRegistry.get_all_names()
        try:
            self._current_model_index = all_names.index(settings.DEFAULT_LLM_MODEL)
            self._llm = LLMRegistry.get(settings.DEFAULT_LLM_MODEL)
            logger.info(
                "llm_service_initialized",
                default_model=settings.DEFAULT_LLM_MODEL,
                model_index=self._current_model_index,
                total_models=len(all_names),
                environment=settings.ENVIRONMENT.value,
            )
        except (ValueError, Exception) as e:
            self._current_model_index = 0
            self._llm = LLMRegistry.LLMS[0]["llm"]
            logger.warning(
                "default_model_not_found_using_first",
                requested=settings.DEFAULT_LLM_MODEL,
                using=all_names[0] if all_names else "none",
                error=str(e),
            )

    def _get_next_model_index(self) -> int:
        """Get the next model index in circular fashion.

        Returns:
            Next model index (wraps around to 0 if at end)
        """
        total_models = len(LLMRegistry.LLMS)
        next_index = (self._current_model_index + 1) % total_models
        return next_index

    def _switch_to_next_model(self) -> bool:
        """Switch to the next model in the registry (circular).

        Returns:
            True if successfully switched, False otherwise
        """
        try:
            next_index = self._get_next_model_index()
            next_model_entry = LLMRegistry.get_model_at_index(next_index)

            logger.warning(
                "switching_to_next_model",
                from_index=self._current_model_index,
                to_index=next_index,
                to_model=next_model_entry["name"],
            )

            self._current_model_index = next_index
            self._llm = next_model_entry["llm"]

            logger.info("model_switched", new_model=next_model_entry["name"], new_index=next_index)
            return True
        except Exception as e:
            logger.error("model_switch_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(settings.MAX_LLM_CALL_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RETRYABLE_ERRORS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _call_llm_with_retry(self, messages: List[BaseMessage]) -> BaseMessage:
        """Call the LLM with automatic retry logic.

        Args:
            messages: List of messages to send to the LLM

        Returns:
            BaseMessage response from the LLM

        Raises:
            PROVIDER_ERRORS: If all retries fail
        """
        if not self._llm:
            raise RuntimeError("llm not initialized")

        try:
            response = await self._llm.ainvoke(messages)
            logger.debug("llm_call_successful", message_count=len(messages))
            return response
        except RETRYABLE_ERRORS as e:
            logger.warning(
                "llm_call_failed_retrying",
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            raise
        except PROVIDER_ERRORS as e:
            logger.error(
                "llm_call_failed",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise

    async def call(
        self,
        messages: List[BaseMessage],
        model_name: Optional[str] = None,
        **model_kwargs,
    ) -> BaseMessage:
        """Call the LLM with the specified messages and circular fallback.

        Args:
            messages: List of messages to send to the LLM
            model_name: Optional specific model to use. If None, uses current model.
            **model_kwargs: Optional kwargs to override default model configuration

        Returns:
            BaseMessage response from the LLM

        Raises:
            RuntimeError: If all models fail after retries
        """
        if model_name:
            try:
                self._llm = LLMRegistry.get(model_name, **model_kwargs)
                all_names = LLMRegistry.get_all_names()
                try:
                    self._current_model_index = all_names.index(model_name)
                except ValueError:
                    pass
                logger.info("using_requested_model", model_name=model_name, has_custom_kwargs=bool(model_kwargs))
            except ValueError as e:
                logger.error("requested_model_not_found", model_name=model_name, error=str(e))
                raise

        total_models = len(LLMRegistry.LLMS)
        models_tried = 0
        starting_index = self._current_model_index
        last_error = None

        while models_tried < total_models:
            try:
                response = await self._call_llm_with_retry(messages)
                return response
            except PROVIDER_ERRORS as e:
                last_error = e
                models_tried += 1

                current_model_name = LLMRegistry.LLMS[self._current_model_index]["name"]
                logger.error(
                    "llm_call_failed_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )

                if models_tried >= total_models:
                    logger.error(
                        "all_models_failed",
                        models_tried=models_tried,
                        starting_model=LLMRegistry.LLMS[starting_index]["name"],
                    )
                    break

                if not self._switch_to_next_model():
                    logger.error("failed_to_switch_to_next_model")
                    break

        raise RuntimeError(
            f"failed to get response from llm after trying {models_tried} models. last error: {str(last_error)}"
        )

    def get_llm(self) -> Optional[BaseChatModel]:
        """Get the current LLM instance.

        Returns:
            Current BaseChatModel instance or None if not initialized
        """
        return self._llm

    def bind_tools(self, tools: List) -> "LLMService":
        """Bind tools to the current LLM.

        Args:
            tools: List of tools to bind

        Returns:
            Self for method chaining
        """
        if self._llm:
            self._llm = self._llm.bind_tools(tools)
            logger.debug("tools_bound_to_llm", tool_count=len(tools))
        return self


# Create global LLM service instance
llm_service = LLMService()