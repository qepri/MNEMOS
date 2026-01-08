from openai import OpenAI
from anthropic import Anthropic
from config.settings import settings, LLMProvider
from app.services.model_manager import model_manager
from app.extensions import db
from app.models.user_preferences import UserPreferences

class LLMClient:
    def __init__(self):
        # Default defaults
        self.provider = settings.LLM_PROVIDER
        openai_key = settings.OPENAI_API_KEY
        anthropic_key = settings.ANTHROPIC_API_KEY
        groq_key = settings.GROQ_API_KEY
        local_base_url = settings.LOCAL_LLM_BASE_URL
        local_model = settings.LOCAL_LLM_MODEL
        
        # Try loading from DB
        try:
            if db.session.registry.has():
                prefs = db.session.query(UserPreferences).first()
                if prefs:
                    if prefs.llm_provider:
                        self.provider = prefs.llm_provider
                    if prefs.openai_api_key:
                        openai_key = prefs.openai_api_key
                    if prefs.anthropic_api_key:
                        anthropic_key = prefs.anthropic_api_key
                    if prefs.groq_api_key:
                        groq_key = prefs.groq_api_key
                    if prefs.local_llm_base_url:
                        local_base_url = prefs.local_llm_base_url
                    # Note: Local Model Name is usually handled by ModelManager selection, 
                    # but we keep a default here just in case.
        except Exception as e:
            print(f"Error loading LLM config from DB: {e}")

        # Initialize Client based on Provider
        if self.provider == LLMProvider.OPENAI:
            self.client = OpenAI(api_key=openai_key)
            self.model = settings.OPENAI_MODEL # Fallback defaults
            
        elif self.provider == LLMProvider.ANTHROPIC:
            self.client = Anthropic(api_key=anthropic_key)
            self.model = settings.ANTHROPIC_MODEL

        elif self.provider == LLMProvider.GROQ:
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key or "gsk_..." # Placeholder if empty, will fail gracefully
            )
            self.model = settings.GROQ_MODEL
            
        elif self.provider == LLMProvider.OLLAMA:
            self.client = OpenAI(
                base_url=settings.OLLAMA_BASE_URL,
                api_key="ollama" 
            )
            self.model = local_model

        elif self.provider == LLMProvider.LM_STUDIO:
            self.client = OpenAI(
                base_url=local_base_url,
                api_key="lm-studio"
            )
            self.model = local_model
        
        # Generic Custom Provider (treated as OpenAI compatible)
        else:
             self.client = OpenAI(
                base_url=local_base_url,
                api_key="custom"
            )
             self.model = local_model
            
    def chat(self, system: str, messages: list, images: list = None) -> str:
        """
        Unified chat method.
        messages format: [{"role": "user", "content": "..."}]
        images: list of base64 strings (optional)
        """
        # Use runtime-selected model if available, otherwise fall back to config
        active_model = model_manager.get_model() or self.model

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
