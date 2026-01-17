from openai import OpenAI
from anthropic import Anthropic
from config.settings import settings, LLMProvider
from app.services.model_manager import model_manager
from app.extensions import db
from app.models.user_preferences import UserPreferences
from app.models.llm_connection import LLMConnection

class LLMClient:
    def __init__(self, provider=None, api_key=None, base_url=None, model=None):
        # 1. Determine Provider
        # Priority: Argument > DB > Settings
        
        db_prefs = None
        try:
            if db.session.registry.has():
                db_prefs = db.session.query(UserPreferences).first()
        except Exception as e:
            print(f"Error loading LLM config from DB: {e}")

        # Provider
        if provider:
            self.provider = provider
        elif db_prefs and db_prefs.llm_provider:
             self.provider = db_prefs.llm_provider
        else:
             self.provider = settings.LLM_PROVIDER
             
        
        d_anthropic_key = db_prefs.anthropic_api_key if db_prefs else None
        d_groq_key = db_prefs.groq_api_key if db_prefs else None
        d_cerebras_key = getattr(db_prefs, 'cerebras_api_key', None) # Handle migration later
        d_local_base_url = db_prefs.local_llm_base_url if db_prefs else None
        d_local_model = getattr(db_prefs, 'local_llm_model', None) # Use getattr for safety
        
        # Settings Fallbacks
        s_local_model = settings.LOCAL_LLM_MODEL
        s_local_base_url = settings.LOCAL_LLM_BASE_URL
        s_openai_key = settings.OPENAI_API_KEY
        d_openai_key = db_prefs.openai_api_key if db_prefs else None
        s_anthropic_key = settings.ANTHROPIC_API_KEY
        s_groq_key = settings.GROQ_API_KEY
        s_cerebras_key = getattr(settings, 'CEREBRAS_API_KEY', None)
        
        # Initialize Client based on Provider
        if self.provider == LLMProvider.OPENAI:
            key = api_key or d_openai_key or s_openai_key
            self.client = OpenAI(api_key=key)
            self.model = model or settings.OPENAI_MODEL # Fallback defaults
            
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
            
        elif self.provider == LLMProvider.OLLAMA:
            # For Ollama, we can use the passed base_url or the internal docker one
            # If base_url is passed (e.g. from Custom/LM Studio override), use it, otherwise default to internal
            url = base_url or settings.OLLAMA_BASE_URL
            self.client = OpenAI(
                base_url=url,
                api_key="ollama" 
            )
            self.model = model or s_local_model

        elif self.provider == LLMProvider.CEREBRAS:
            key = api_key or d_cerebras_key or s_cerebras_key
            self.client = OpenAI(
                base_url="https://api.cerebras.ai/v1",
                api_key=key
            )
            self.model = model or settings.CEREBRAS_MODEL

        elif self.provider == LLMProvider.LM_STUDIO:
            url = base_url or d_local_base_url or s_local_base_url
            self.client = OpenAI(
                base_url=url,
                api_key="lm-studio"
            )
            self.model = model or s_local_model
        
        # Generic Custom Provider (Dynamic Connections)
        else:
             url = None
             key = None
             active_conn = None
             
             # Try to load from active connection if set
             if db_prefs and db_prefs.active_connection_id:
                 try:
                     active_conn = db.session.query(LLMConnection).filter_by(id=db_prefs.active_connection_id).first()
                 except Exception as e:
                     print(f"Error loading active connection: {e}")
             
             if active_conn:
                 url = active_conn.base_url
                 key = active_conn.api_key
                 # Use connection default model if no specific override
                 if not model and active_conn.default_model:
                     model = active_conn.default_model
             else:
                 # Fallback logic: check if we have manual overrides, otherwise ERROR if strictly custom
                 # If the provider is explicitly set to 'custom' via DB/Settings, we MUST have a connection.
                 # Failing to have one and falling back to localhost causes the confusing "Connection refused"
                 
                 # Check if we have explicit manual overrides (e.g. from env vars or partial DB state)
                 # If we are here, it means provider was 'custom' (or fell through to else) AND active_conn was None.
                 
                 if self.provider == LLMProvider.CUSTOM:
                      # If we don't have a valid active_conn ID, this is a misconfiguration.
                      # We shouldn't silently default to localhost unless that WAS the intention.
                      # But for 'custom', the intention is a specific connection.
                      raise ValueError("LLM Provider is set to 'Custom' but no active connection is selected. Please select a connection in Settings.")

                 # Legacy/Default fallback (for non-strict custom or other cases)
                 url = base_url or d_local_base_url or s_local_base_url
                 key = api_key or (db_prefs.custom_api_key if db_prefs else None) or "custom"

             self.client = OpenAI(
                base_url=url,
                api_key=key
            )
             self.model = model or s_local_model
             
        print(f"DEBUG: LLMClient Initialized. Provider: {self.provider}. Base URL: {self.client.base_url}")
            
    def chat(self, system: str, messages: list, images: list = None, model: str = None) -> str:
        """
        Unified chat method.
        messages format: [{"role": "user", "content": "..."}]
        images: list of base64 strings (optional)
        model: optional model name to override the default/selected model
        """
        # Use explicit model if provided, otherwise check manager, otherwise default
        active_model = model or model_manager.get_model() or self.model

        try:
            if self.provider == LLMProvider.ANTHROPIC:
                # Convert system message to Anthropic format (param)
                # Anthropic Vision support: format user message content as list
                
                final_messages = messages
                
                # If there are images, we need to restructure the LAST user message (which contains the prompt)
                if images:
                     # Find the last user message
                     last_msg = None
                     for m in reversed(messages):
                         if m['role'] == 'user':
                             last_msg = m
                             break
                     
                     if last_msg:
                         content_block = []
                         # Add images first
                         for img_b64 in images:
                             # Strip prefix if present (data:image/jpeg;base64,...)
                             if "," in img_b64:
                                 img_b64 = img_b64.split(",")[1]
                                 
                             content_block.append({
                                 "type": "image",
                                 "source": {
                                     "type": "base64",
                                     "media_type": "image/jpeg", # Assuming jpeg for now, or detect?
                                     "data": img_b64
                                 }
                             })
                         # Add text
                         content_block.append({
                             "type": "text",
                             "text": last_msg['content']
                         })
                         last_msg['content'] = content_block

                response = self.client.messages.create(
                    model=active_model,
                    max_tokens=1024,
                    system=system,
                    messages=final_messages
                )
                return response.content[0].text

            else:
                # OpenAI / Compatible (Ollama, LM Studio)
                # Prepend system message
                
                # Handle images for OpenAI/Ollama 
                # They use "content": [{"type": "text", "text": "..." }, { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } }]
                
                final_messages = []
                # Copy messages to avoid mutating original list reference issues
                import copy
                msgs_copy = copy.deepcopy(messages)
                
                if images:
                     # Attach images to the last user message
                     last_msg = None
                     for m in reversed(msgs_copy):
                         if m['role'] == 'user':
                             last_msg = m
                             break
                     
                     if last_msg:
                         text_content = last_msg['content']
                         new_content = [{"type": "text", "text": text_content}]
                         
                         for img_b64 in images:
                             # Ensure prefix is present for OpenAI/Ollama
                             if "," not in img_b64:
                                 img_b64 = f"data:image/jpeg;base64,{img_b64}"
                                 
                             new_content.append({
                                 "type": "image_url",
                                 "image_url": {
                                     "url": img_b64
                                 }
                             })
                         last_msg['content'] = new_content

                full_messages = [{"role": "system", "content": system}] + msgs_copy

                import json
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Using model: {active_model}")
                # logger.info(f"Sending payload to LLM: {json.dumps(full_messages, indent=2)}") # Too verbose with base64

                # Prepare options directly supported by Ollama
                extra_body = {}
                if self.provider == LLMProvider.OLLAMA:
                     extra_body["options"] = {
                         "num_ctx": settings.OLLAMA_NUM_CTX
                     }

                response = self.client.chat.completions.create(
                    model=active_model,
                    messages=full_messages, # Pass full_messages here instead of messages
                    temperature=0.7,
                    extra_body=extra_body
                )
                logger.info(f"Received response from LLM: {response.model_dump_json()}")
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"Error communicating with LLM: {str(e)}", exc_info=True)
            return f"Error communicating with LLM: {str(e)}"

_client_instance = None

def get_llm_client():
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient()
    return _client_instance

def reset_client():
    """Force re-initialization of the LLM client (e.g. after config change)."""
    global _client_instance
    _client_instance = None
