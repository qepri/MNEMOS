from openai import OpenAI
from anthropic import Anthropic
from config.settings import settings, LLMProvider
from app.services.model_manager import model_manager
from app.extensions import db
from app.models.user_preferences import UserPreferences
from app.models.llm_connection import LLMConnection

import os
import json
import copy
import logging
import threading

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM provider returns an error."""
    pass


class LLMClient:
    def __init__(self, provider=None, api_key=None, base_url=None, model=None):
        db_prefs = None
        try:
            db_prefs = db.session.query(UserPreferences).first()
            if db_prefs:
                logger.debug(f"Found UserPreferences in DB. Provider: {db_prefs.llm_provider}")
            else:
                logger.debug("UserPreferences table empty.")
        except Exception as e:
            logger.warning(f"Error loading LLM config from DB: {e}")

        # Provider priority: argument > DB > settings
        if provider:
            self.provider = provider
            logger.debug(f"Using passed provider arg: {provider}")
        elif db_prefs and db_prefs.llm_provider:
            self.provider = db_prefs.llm_provider
            logger.debug(f"Using DB provider: {self.provider}")
        else:
            self.provider = settings.LLM_PROVIDER
            logger.debug(f"Fallback to Settings provider: {self.provider}")

        # Stored preferences may still name a retired provider (e.g. "ollama")
        # when the data migration has not run — RUN_MIGRATIONS may be false.
        # Degrade to llamacpp instead of raising.
        if self.provider not in set(LLMProvider):
            logger.warning(
                f"Unknown LLM provider '{self.provider}' in stored config; "
                f"falling back to '{LLMProvider.LLAMACPP.value}'"
            )
            self.provider = LLMProvider.LLAMACPP

        d_anthropic_key = db_prefs.anthropic_api_key if db_prefs else None
        d_groq_key = db_prefs.groq_api_key if db_prefs else None
        d_cerebras_key = getattr(db_prefs, 'cerebras_api_key', None)
        d_local_base_url = db_prefs.local_llm_base_url if db_prefs else None
        d_local_model = getattr(db_prefs, 'local_llm_model', None)

        s_local_model = settings.LOCAL_LLM_MODEL
        s_local_base_url = settings.LOCAL_LLM_BASE_URL
        s_openai_key = settings.OPENAI_API_KEY
        d_openai_key = db_prefs.openai_api_key if db_prefs else None
        s_anthropic_key = settings.ANTHROPIC_API_KEY
        s_groq_key = settings.GROQ_API_KEY
        s_cerebras_key = getattr(settings, 'CEREBRAS_API_KEY', None)
        s_deepseek_key = getattr(settings, 'DEEPSEEK_API_KEY', None)

        if self.provider == LLMProvider.OPENAI:
            key = api_key or d_openai_key or s_openai_key
            self.client = OpenAI(api_key=key)
            self.model = model or settings.OPENAI_MODEL

        elif self.provider == LLMProvider.ANTHROPIC:
            key = api_key or d_anthropic_key or s_anthropic_key
            self.client = Anthropic(api_key=key)
            self.model = model or settings.ANTHROPIC_MODEL

        elif self.provider == LLMProvider.GROQ:
            key = api_key or d_groq_key or s_groq_key
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=key or "gsk_..."
            )
            self.model = model or settings.GROQ_MODEL

        elif self.provider == LLMProvider.LLAMACPP:
            url = base_url or settings.LLAMACPP_BASE_URL
            self.client = OpenAI(
                base_url=url,
                api_key="not-needed"
            )
            self.model = model or s_local_model
            self.llamacpp_num_ctx = getattr(settings, 'LLAMACPP_NUM_CTX', 2048)

        elif self.provider == LLMProvider.CEREBRAS:
            key = api_key or d_cerebras_key or s_cerebras_key
            self.client = OpenAI(
                base_url="https://api.cerebras.ai/v1",
                api_key=key
            )
            self.model = model or settings.CEREBRAS_MODEL

        elif self.provider == LLMProvider.DEEPSEEK:
            key = api_key or s_deepseek_key
            self.client = OpenAI(
                base_url="https://api.deepseek.com/v1",
                api_key=key
            )
            self.model = model or settings.DEEPSEEK_MODEL

        elif self.provider == LLMProvider.LM_STUDIO:
            url = base_url or d_local_base_url or s_local_base_url

            if url and ("localhost" in url or "127.0.0.1" in url):
                if os.path.exists('/.dockerenv'):
                    url = url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
                    logger.debug(f"Auto-corrected LM Studio URL to: {url}")

            if url and not url.endswith("/v1"):
                url = f"{url.rstrip('/')}/v1"
                logger.debug(f"Appended /v1 to LM Studio URL: {url}")

            self.client = OpenAI(
                base_url=url,
                api_key="lm-studio"
            )
            self.model = model or s_local_model

        else:
            url = None
            key = None
            active_conn = None

            if db_prefs and db_prefs.active_connection_id:
                try:
                    active_conn = db.session.query(LLMConnection).filter_by(id=db_prefs.active_connection_id).first()
                except Exception as e:
                    logger.warning(f"Error loading active connection: {e}")

            if active_conn:
                url = active_conn.base_url
                key = active_conn.api_key
                if not model and active_conn.default_model:
                    model = active_conn.default_model
            else:
                if self.provider == LLMProvider.CUSTOM:
                    raise ValueError("LLM Provider is set to 'Custom' but no active connection is selected. Please select a connection in Settings.")

                url = base_url or d_local_base_url or s_local_base_url
                key = api_key or (db_prefs.custom_api_key if db_prefs else None) or "custom"

            if url and ("localhost" in url or "127.0.0.1" in url):
                if os.path.exists('/.dockerenv'):
                    url = url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
                    logger.debug(f"Auto-corrected Custom URL to: {url}")

            if url and not url.endswith("/v1") and not url.endswith("/v1/"):
                url = f"{url.rstrip('/')}/v1"
                logger.debug(f"Appended /v1 to Custom URL: {url}")

            self.client = OpenAI(
                base_url=url,
                api_key=key or "not-needed"
            )
            self.model = model or s_local_model

        # Providers that support strict json_schema structured output
        # deepseek-v4-pro doesn't support any response_format; flash does (json_object).
        self.supports_json_schema = self.provider in (
            LLMProvider.OPENAI,
            LLMProvider.GROQ,
        )
        self.supports_json_object = self.provider in (
            LLMProvider.OPENAI,
            LLMProvider.GROQ,
            LLMProvider.DEEPSEEK,
        )

        logger.debug(f"LLMClient Initialized. Provider: {self.provider}. Base URL: {self.client.base_url}")

    def chat(self, system: str, messages: list, images: list = None, model: str = None, json_schema: dict = None) -> str:
        """
        Chat with the LLM.

        system: system prompt
        messages: list of {"role": "user"|"assistant", "content": str}
        images: optional list of base64-encoded images
        model: override the default model
        json_schema: optional JSON schema dict to force structured output
        """
        active_model = model or model_manager.get_model() or self.model

        # Load generation parameters from DB before building any provider-specific params
        try:
            prefs = db.session.query(UserPreferences).first()
            max_tokens = prefs.llm_max_tokens if prefs else 4096
            temperature = prefs.llm_temperature if prefs else 0.7
            top_p = prefs.llm_top_p if prefs else 0.9
            freq_penalty = prefs.llm_frequency_penalty if prefs else 0.3
            pres_penalty = prefs.llm_presence_penalty if prefs else 0.1
        except Exception:
            max_tokens, temperature, top_p, freq_penalty, pres_penalty = 4096, 0.7, 0.9, 0.3, 0.1

        try:
            if self.provider == LLMProvider.ANTHROPIC:
                final_messages = messages

                if images:
                    last_msg = None
                    for m in reversed(messages):
                        if m['role'] == 'user':
                            last_msg = m
                            break

                    if last_msg:
                        content_block = []
                        for img_b64 in images:
                            if "," in img_b64:
                                img_b64 = img_b64.split(",")[1]
                            content_block.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": img_b64
                                }
                            })
                        content_block.append({
                            "type": "text",
                            "text": last_msg['content']
                        })
                        last_msg['content'] = content_block

                response = self.client.messages.create(
                    model=active_model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=final_messages
                )
                return response.content[0].text

            else:
                msgs_copy = copy.deepcopy(messages)

                if images:
                    last_msg = None
                    for m in reversed(msgs_copy):
                        if m['role'] == 'user':
                            last_msg = m
                            break

                    if last_msg:
                        text_content = last_msg['content']
                        new_content = [{"type": "text", "text": text_content}]

                        for img_b64 in images:
                            if "," not in img_b64:
                                img_b64 = f"data:image/jpeg;base64,{img_b64}"
                            new_content.append({
                                "type": "image_url",
                                "image_url": {"url": img_b64}
                            })
                        last_msg['content'] = new_content

                full_messages = [{"role": "system", "content": system}] + msgs_copy

                logger.info(f"Using model: {active_model}")

                extra_body = {}
                if self.provider == LLMProvider.LLAMACPP:
                    extra_body["n_predict"] = max_tokens

                request_params = {
                    "model": active_model,
                    "messages": full_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "frequency_penalty": freq_penalty,
                    "presence_penalty": pres_penalty,
                    "extra_body": extra_body
                }

                if json_schema:
                    if self.supports_json_schema:
                        request_params["response_format"] = {
                            "type": "json_schema",
                            "json_schema": json_schema
                        }
                    elif self.supports_json_object:
                        request_params["response_format"] = {"type": "json_object"}
                    else:
                        # Provider doesn't support any response_format — the
                        # prompt already describes the required structure, so
                        # this is sufficient.
                        pass

                response = self.client.chat.completions.create(**request_params)

                try:
                    response_json = response.model_dump_json()
                    try:
                        parsed = json.loads(response_json)
                        logger.debug(f"Received response from LLM:\n{json.dumps(parsed, indent=2)}")
                    except Exception:
                        logger.debug(f"Received response from LLM: {response_json}")
                except Exception as log_err:
                    logger.debug(f"Could not serialize response for logging: {log_err}")

                return response.choices[0].message.content

        except LLMError:
            raise
        except Exception as e:
            logger.error(f"Error communicating with LLM: {str(e)}", exc_info=True)
            raise LLMError(str(e))


    def stream_chat(self, system: str, messages: list, model: str = None):
        """
        Generator that yields string token deltas.
        Falls back to yielding the full response as a single token for providers
        that don't support streaming.
        """
        active_model = model or model_manager.get_model() or self.model

        try:
            prefs = db.session.query(UserPreferences).first()
            max_tokens = prefs.llm_max_tokens if prefs else 4096
            temperature = prefs.llm_temperature if prefs else 0.7
            top_p = prefs.llm_top_p if prefs else 0.9
            freq_penalty = prefs.llm_frequency_penalty if prefs else 0.3
            pres_penalty = prefs.llm_presence_penalty if prefs else 0.1
        except Exception:
            max_tokens, temperature, top_p, freq_penalty, pres_penalty = 4096, 0.7, 0.9, 0.3, 0.1

        try:
            if self.provider == LLMProvider.ANTHROPIC:
                with self.client.messages.stream(
                    model=active_model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages
                ) as stream:
                    for text in stream.text_stream:
                        yield text
            else:
                full_messages = [{"role": "system", "content": system}] + messages
                response = self.client.chat.completions.create(
                    model=active_model,
                    messages=full_messages,
                    stream=True,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    frequency_penalty=freq_penalty,
                    presence_penalty=pres_penalty,
                )
                for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
        except Exception as e:
            logger.error(f"Error streaming from LLM: {str(e)}", exc_info=True)
            raise LLMError(str(e))


_thread_local = threading.local()


def get_llm_client():
    if not hasattr(_thread_local, 'client'):
        _thread_local.client = LLMClient()
    return _thread_local.client


def reset_client():
    """Invalidate the LLM client for the current thread (call after config changes)."""
    if hasattr(_thread_local, 'client'):
        del _thread_local.client
