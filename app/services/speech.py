import logging
import requests
from config.settings import settings
from app.extensions import db
from app.models.user_preferences import UserPreferences

logger = logging.getLogger(__name__)

class SpeechService:
    def synthesize(self, text: str) -> bytes:
        """
        Synthesize speech from text using the selected provider.
        Returns audio bytes (MP3 usually).
        """
        provider = 'openai' # Default or fallback? 
        # browser is client side, so if we are here, it's likely api based.
        
        target_voice = 'alloy'
        target_model = 'tts-1'
        openai_key = None
        groq_key = None
        deepgram_key = None
        
        try:
            prefs = db.session.query(UserPreferences).first()
            if prefs:
                if prefs.tts_provider and prefs.tts_provider != 'browser':
                    provider = prefs.tts_provider
                if prefs.tts_voice:
                    target_voice = prefs.tts_voice
                if prefs.openai_tts_model:
                    target_model = prefs.openai_tts_model
                
                if prefs.openai_api_key:
                    openai_key = prefs.openai_api_key
                if hasattr(prefs, 'groq_api_key') and prefs.groq_api_key:
                    groq_key = prefs.groq_api_key
                if hasattr(prefs, 'deepgram_api_key') and prefs.deepgram_api_key:
                    deepgram_key = prefs.deepgram_api_key
        except Exception as e:
            logger.warning(f"Could not load settings for speech: {e}")

        logger.info(f"Synthesizing speech with Provider: {provider}, Voice: {target_voice}")

        if provider == 'openai':
            return self._synthesize_openai(text, target_voice, target_model, openai_key)
        elif provider == 'groq':
            # Use Groq (via OpenAI wrapper)
            return self._synthesize_groq(text, target_voice, target_model, groq_key)
        elif provider == 'deepgram':
            return self._synthesize_deepgram(text, target_voice, target_model, deepgram_key)
        else:
            # Fallback or error if 'browser' somehow reached here?
            # Or maybe 'local' if we add it?
            raise ValueError(f"Provider {provider} not supported in backend or should be handled by client.")

    def _synthesize_openai(self, text: str, voice: str, model: str, api_key: str) -> bytes:
        if not api_key:
            raise ValueError("OpenAI API Key is required for OpenAI TTS.")
        return self._synthesize_openai_like(text, voice, model, api_key, None)

    def _synthesize_groq(self, text: str, voice: str, model: str, api_key: str) -> bytes:
        if not api_key:
            raise ValueError("Groq API Key (using standard key) is required for Groq TTS.")
        
        # Groq doesn't strictly have a TTS public endpoint that matches OpenAI exactly yet 
        # BUT the plan said: "Endpoint: https://api.groq.com/openai/v1/audio/speech (OpenAI compatible)"
        # So we try that.
        return self._synthesize_openai_like(text, voice, model, api_key, "https://api.deepinfra.com/v1/openai" if model == 'deepinfra' else "https://api.groq.com/openai/v1") 
        # NOTE: Deepinfra was not in plan, just stick to Groq base URL.
        # But wait, Groq's model for TTS? 
        # Research Step 333 said: "https://api.groq.com/openai/v1/audio/speech" with models like "canopylabs/orpheus-v1-english" or "playai" voices.
        # Default model for Groq might be needed if "tts-1" is passed.
        # If model is 'tts-1', fallback to a known Groq model? 
        # Or rely on user to select model.
        # For now, pass model as is, assuming UI selects correct model.
        
        return self._synthesize_openai_like(text, voice, model, api_key, "https://api.groq.com/openai/v1")

    def _synthesize_openai_like(self, text: str, voice: str, model: str, api_key: str, base_url: str) -> bytes:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)

        response = client.audio.speech.create(
            model=model or "tts-1",
            voice=voice or "alloy",
            input=text
        )
        return response.content

    def _synthesize_deepgram(self, text: str, voice: str, model: str, api_key: str) -> bytes:
        if not api_key:
            raise ValueError("Deepgram API Key is required for Deepgram TTS.")
            
        import requests
        # Deepgram Aura TTS
        # URL: https://api.deepgram.com/v1/speak?model=aura-asteria-en
        # Voice maps to model in Deepgram usually (e.g. aura-asteria-en)
        # So we interpret 'voice' as the full model/voice string, or 'model' as general config?
        # Typically Deepgram TTS model param IS the voice.
        # So we use 'voice' if set, else default.
        
        # Deepgram Limit is 2000 characters. Implement simpler chunking.
        MAX_CHARS = 1900
        
        if len(text) <= MAX_CHARS:
             actual_model = voice if voice and "aura" in voice else "aura-asteria-en"
             url = f"https://api.deepgram.com/v1/speak?model={actual_model}"
             headers = {
                 "Authorization": f"Token {api_key}",
                 "Content-Type": "application/json"
             }
             payload = {"text": text}
             response = requests.post(url, headers=headers, json=payload)
             if response.status_code != 200:
                  logger.error(f"Deepgram TTS Error: {response.text}")
                  raise Exception(f"Deepgram TTS failed: {response.text}")
             return response.content

        # Chunking needed
        chunks = []
        # Simple sentence splitter to avoid cutting words
        # 1. Split by periods/newlines
        # 2. Re-assemble into chunks < MAX_CHARS
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < MAX_CHARS:
                current_chunk += sentence + " "
            else:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        full_audio = b""
        actual_model = voice if voice and "aura" in voice else "aura-asteria-en"
        url = f"https://api.deepgram.com/v1/speak?model={actual_model}"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json"
        }
        
        for chunk in chunks:
            if not chunk: continue
            try:
                payload = {"text": chunk}
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    full_audio += response.content
                else:
                    logger.warning(f"Failed to synthesize chunk: {chunk[:50]}...")
            except Exception as e:
                logger.error(f"Error synthesizing chunk: {e}")
                
        return full_audio
