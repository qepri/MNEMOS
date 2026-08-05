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


def _normalize_local_url(url: str | None) -> str | None:
    """Make a user-supplied local base URL usable from inside a container."""
    if not url:
        return url
    if ("localhost" in url or "127.0.0.1" in url) and os.path.exists('/.dockerenv'):
        url = url.replace("localhost", "host.docker.internal").replace(
            "127.0.0.1", "host.docker.internal"
        )
        logger.debug(f"Auto-corrected local URL to: {url}")
    if not url.rstrip('/').endswith("/v1"):
        url = f"{url.rstrip('/')}/v1"
        logger.debug(f"Appended /v1 to URL: {url}")
    return url


class ProviderSpec:
    """How to construct a client for one provider.

    Replaces the previous if/elif ladder. Every provider except LM Studio and
    the connection-driven CUSTOM path is fully described by this table.
    """

    def __init__(self, cred_key, model_setting, base_url=None, sdk=OpenAI, fallback_key=None):
        self._cred_key = cred_key
        self._model_setting = model_setting
        self._base_url = base_url
        self._sdk = sdk
        self._fallback_key = fallback_key

    def build_client(self, creds: dict, base_url_override: str | None):
        key = creds.get(self._cred_key) or self._fallback_key
        url = base_url_override or self._base_url
        if self._sdk is Anthropic:
            return Anthropic(api_key=key)
        return self._sdk(base_url=url, api_key=key) if url else self._sdk(api_key=key)

    def default_model(self):
        return getattr(settings, self._model_setting, None)


PROVIDER_SPECS = {
    LLMProvider.OPENAI: ProviderSpec('openai_key', 'OPENAI_MODEL'),
    LLMProvider.ANTHROPIC: ProviderSpec('anthropic_key', 'ANTHROPIC_MODEL', sdk=Anthropic),
    LLMProvider.GROQ: ProviderSpec(
        'groq_key', 'GROQ_MODEL',
        base_url="https://api.groq.com/openai/v1", fallback_key="gsk_...",
    ),
    LLMProvider.CEREBRAS: ProviderSpec(
        'cerebras_key', 'CEREBRAS_MODEL', base_url="https://api.cerebras.ai/v1",
    ),
    LLMProvider.DEEPSEEK: ProviderSpec(
        'deepseek_key', 'DEEPSEEK_MODEL', base_url="https://api.deepseek.com/v1",
    ),
    LLMProvider.LLAMACPP: ProviderSpec(
        'llamacpp_key', 'LOCAL_LLM_MODEL',
        base_url=settings.LLAMACPP_BASE_URL, fallback_key="not-needed",
    ),
}


class LLMClient:
    @staticmethod
    def _load_prefs():
        try:
            return db.session.query(UserPreferences).first()
        except Exception as e:
            logger.warning(f"Error loading LLM config from DB: {e}")
            return None

    @staticmethod
    def _resolve_provider(provider, db_prefs):
        """Priority: constructor arg > DB > settings."""
        resolved = provider or (db_prefs.llm_provider if db_prefs else None) or settings.LLM_PROVIDER

        # Stored preferences may still name a retired provider (e.g. "ollama")
        # when the data migration has not run - RUN_MIGRATIONS may be false.
        # Degrade instead of raising.
        if resolved not in set(LLMProvider):
            logger.warning(
                f"Unknown LLM provider '{resolved}' in stored config; "
                f"falling back to '{LLMProvider.LLAMACPP.value}'"
            )
            return LLMProvider.LLAMACPP
        return resolved

    def _build_connection_client(self, db_prefs, api_key, model, local_base_url):
        """CUSTOM provider: configuration comes from a stored LLMConnection."""
        active_conn = None
        if db_prefs and db_prefs.active_connection_id:
            try:
                active_conn = db.session.query(LLMConnection).filter_by(
                    id=db_prefs.active_connection_id
                ).first()
            except Exception as e:
                logger.warning(f"Error loading active connection: {e}")

        if active_conn:
            url = active_conn.base_url
            key = active_conn.api_key
            model = model or active_conn.default_model
        else:
            if self.provider == LLMProvider.CUSTOM:
                raise ValueError(
                    "LLM Provider is set to 'Custom' but no active connection is "
                    "selected. Please select a connection in Settings."
                )
            url = local_base_url
            key = api_key or (db_prefs.custom_api_key if db_prefs else None) or "custom"

        client = OpenAI(base_url=_normalize_local_url(url), api_key=key or "not-needed")
        return client, model or settings.LOCAL_LLM_MODEL

    @staticmethod
    def _resolve_credentials(api_key, db_prefs):
        """Constructor arg > DB > settings, for every provider's credential."""
        d = db_prefs
        return {
            'openai_key': api_key or (d.openai_api_key if d else None) or settings.OPENAI_API_KEY,
            'anthropic_key': api_key or (d.anthropic_api_key if d else None) or settings.ANTHROPIC_API_KEY,
            'groq_key': api_key or (d.groq_api_key if d else None) or settings.GROQ_API_KEY,
            'cerebras_key': api_key or getattr(d, 'cerebras_api_key', None) or getattr(settings, 'CEREBRAS_API_KEY', None),
            'deepseek_key': api_key or getattr(settings, 'DEEPSEEK_API_KEY', None),
        }

    def __init__(self, provider=None, api_key=None, base_url=None, model=None):
        db_prefs = self._load_prefs()
        self.provider = self._resolve_provider(provider, db_prefs)

        creds = self._resolve_credentials(api_key, db_prefs)
        local_base_url = (
            base_url
            or (db_prefs.local_llm_base_url if db_prefs else None)
            or settings.LOCAL_LLM_BASE_URL
        )

        spec = PROVIDER_SPECS.get(self.provider)
        if spec is not None:
            self.client = spec.build_client(creds, base_url)
            self.model = model or spec.default_model()
            if self.provider == LLMProvider.LLAMACPP:
                self.llamacpp_num_ctx = getattr(settings, 'LLAMACPP_NUM_CTX', 2048)
        elif self.provider == LLMProvider.LM_STUDIO:
            self.client = OpenAI(base_url=_normalize_local_url(local_base_url), api_key="lm-studio")
            self.model = model or settings.LOCAL_LLM_MODEL
        else:
            self.client, self.model = self._build_connection_client(
                db_prefs, api_key, model, local_base_url
            )

        self._set_capability_flags()
        logger.debug(f"LLMClient Initialized. Provider: {self.provider}. Base URL: {self.client.base_url}")

    def _set_capability_flags(self):
        # deepseek-v4-pro doesn't support any response_format; flash does (json_object).
        self.supports_json_schema = self.provider in (LLMProvider.OPENAI, LLMProvider.GROQ)
        self.supports_json_object = self.provider in (
            LLMProvider.OPENAI, LLMProvider.GROQ, LLMProvider.DEEPSEEK,
        )

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
    # Availability is derived from the same configuration, so it invalidates
    # here too - one seam rather than two that can drift apart.
    from app.services.llm_availability import invalidate
    invalidate()
