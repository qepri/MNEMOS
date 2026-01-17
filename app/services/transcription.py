import whisper
import gc
import torch
import logging
from typing import List, Dict
from config.settings import settings
from app.extensions import db
from app.models.user_preferences import UserPreferences

logger = logging.getLogger(__name__)

class TranscriptionService:
    _model = None
    _current_model_name = None

    def transcribe(self, audio_path: str) -> List[Dict]:
        """
        Transcribe audio/video using the selected provider (Local or Groq).
        """
        # Default settings
        provider = 'local'
        target_model = settings.WHISPER_MODEL
        groq_key = None
        deepgram_key = None

        try:
            prefs = db.session.query(UserPreferences).first()
            if prefs:
                if prefs.whisper_model:
                    target_model = prefs.whisper_model
                # Check for provider (defaulting to local)
                if hasattr(prefs, 'stt_provider') and prefs.stt_provider:
                    provider = prefs.stt_provider
                # Fallback to older field name if stt_provider is not set or default
                elif hasattr(prefs, 'transcription_provider') and prefs.transcription_provider:
                    provider = prefs.transcription_provider

                if hasattr(prefs, 'groq_api_key') and prefs.groq_api_key:
                    groq_key = prefs.groq_api_key
                if hasattr(prefs, 'deepgram_api_key') and prefs.deepgram_api_key:
                    deepgram_key = prefs.deepgram_api_key
        except Exception as e:
            logger.warning(f"Could not load settings for transcription: {e}")

        logger.info(f"Starting transcription with Provider: {provider}, Model: {target_model}")

        if provider == 'groq':
            return self._transcribe_groq(audio_path, target_model, groq_key)
        elif provider == 'deepgram':
            return self._transcribe_deepgram(audio_path, target_model, deepgram_key)
        elif provider == 'openai':
            # Use api key from prefs
            api_key = None
            try:
                if prefs and prefs.openai_api_key:
                    api_key = prefs.openai_api_key
            except: pass
            return self._transcribe_openai(audio_path, target_model, api_key)
        else:
            return self._transcribe_local(audio_path, target_model)

    def _transcribe_local(self, audio_path: str, model_name: str) -> List[Dict]:
        """Use local Whisper model."""
        # Ensure correct model is loaded
        # We need to bypass the caching check if we are switching providers or models manually, 
        # but get_model handles logic for 'same model name'.
        # However, we must ensure we don't accidentally use a Groq model name for local loading
        # if the user messed up settings, but we assume UI handles this.
        
        # Determine actual local model name if needed, or trust input.
        # If model_name starts with "whisper-large" (Groq style) and we are in local, 
        # we might want to fallback to 'base' to avoid error, or let it fail.
        # For now, we trust the input.
        
        # Logic from original get_model is slightly specific about using settings.WHISPER_MODEL
        # We will adapt get_model to take an argument or just set the class var.
        
        # Accessing private logic from get_model via class method
        # But get_model pulls from DB itself.
        # We should probably update get_model to NOT pull from DB and take arguments,
        # OR just set the class logic here.
        
        # Simpler: Let's reuse get_model but we need to ensure it uses the intended model_name
        # passing it down is hard since get_model has no args.
        # Let's modify get_model to accept an optional model_name override?
        # Or better, just refactor _transcribe_local to do the loading logic if needed.
        
        # To avoid breaking existing calls to get_model (if any), 
        # I'll rely on get_model's DB lookup for now, BUT if I passed model_name here,
        # it might conflict if get_model reads DB again.
        # ACTUALLY, strict clean approach:
        # Refactor get_model to accept model_name.
        model = self._load_local_model(model_name)
        
        result = model.transcribe(
            audio_path,
            word_timestamps=True,
            verbose=False
        )
        
        segments = []
        for segment in result["segments"]:
            segments.append({
                "text": segment["text"].strip(),
                "start": float(segment["start"]),
                "end": float(segment["end"])
            })
        return segments

    def _transcribe_groq(self, audio_path: str, model_name: str, api_key: str) -> List[Dict]:
        """Use Groq API for transcription."""
        if not api_key:
            raise ValueError("Groq API Key is required for Groq transcription.")
            
        # Ensure model is valid for Groq
        # fallback if local model names are passed
        valid_models = ['whisper-large-v3', 'whisper-large-v3-turbo', 'distil-whisper-large-v3-en']
        if not model_name or model_name not in valid_models:
            logger.warning(f"Invalid Groq model '{model_name}' requested. Defaulting to 'whisper-large-v3-turbo'.")
            model_name = 'whisper-large-v3-turbo'

        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key
        )
        
        with open(audio_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(audio_path, file.read()),
                model=model_name,
                response_format="verbose_json"
            )
            
        segments = []
        # Groq (via OpenAI) verbose_json returns an object with 'segments'
        if hasattr(transcription, 'segments'):
             for segment in transcription.segments:
                # OpenAI objects are Pydantic models in v1+ or dicts?
                # Usually objects.
                segments.append({
                    "text": segment['text'].strip() if isinstance(segment, dict) else segment.text.strip(),
                    "start": float(segment['start'] if isinstance(segment, dict) else segment.start),
                    "end": float(segment['end'] if isinstance(segment, dict) else segment.end)
                })
        else:
             # Fallback if no segments (short audio?)
             segments.append({
                 "text": transcription.text,
                 "start": 0.0,
                 "end": transcription.duration
             })
             
        return segments

    def _transcribe_deepgram(self, audio_path: str, model_name: str, api_key: str) -> List[Dict]:
        """Use Deepgram API for transcription."""
        if not api_key:
            raise ValueError("Deepgram API Key is required for Deepgram transcription.")

        import requests
        url = "https://api.deepgram.com/v1/listen"
        
        # Default to nova-2 if no specific model requested or if it's an OpenAI model name
        model = "nova-2"
        if model_name and "nova" in model_name:
            model = model_name
            
        params = {
            "model": model,
            "smart_format": "true",
            "punctuate": "true",
            "utterances": "true",
            "diarize": "false"
        }
        
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav" # Assumed, or detect
        }
        
        # Detect mime type roughly or just send as audio/* if possible, 
        # but Deepgram prefers Content-Type. audio/wav is safe for the recorded chunks usually.
        # Check file extension
        if audio_path.endswith('.mp3'):
            headers["Content-Type"] = "audio/mpeg"
        elif audio_path.endswith('.webm'):
            headers["Content-Type"] = "audio/webm"
            
        with open(audio_path, "rb") as file:
            response = requests.post(url, headers=headers, params=params, data=file)
            
        if response.status_code != 200:
             logger.error(f"Deepgram Error: {response.text}")
             raise Exception(f"Deepgram API failed with status {response.status_code}: {response.text}")
             
        data = response.json()
        segments = []
        
        # Parse Deepgram response to match Whisper format
        if 'results' in data and 'utterances' in data['results']:
            for utt in data['results']['utterances']:
                segments.append({
                    "text": utt['transcript'].strip(),
                    "start": float(utt['start']),
                    "end": float(utt['end'])
                })
        elif 'results' in data and 'channels' in data['results']:
             # Fallback if utterances not enabled or empty
             channel = data['results']['channels'][0]
             if 'alternatives' in channel:
                 alt = channel['alternatives'][0]
                 segments.append({
                     "text": alt['transcript'].strip(),
                     "start": 0.0,
                     "end": float(data['metadata']['duration'])
                 })

        return segments

    def _transcribe_openai(self, audio_path: str, model_name: str, api_key: str) -> List[Dict]:
        """Use OpenAI API for transcription."""
        if not api_key:
            raise ValueError("OpenAI API Key is required for OpenAI transcription.")
            
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # OpenAI Whisper model names: whisper-1
        if not model_name or model_name == 'base': # Fallback if local default passed
            model_name = 'whisper-1'

        try:
            with open(audio_path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=file,
                    model=model_name,
                    response_format="verbose_json"
                )
        except Exception as e:
            logger.error(f"OpenAI Transcription failed: {e}")
            raise e
            
        segments = []
        if hasattr(transcription, 'segments'):
             for segment in transcription.segments:
                segments.append({
                    "text": segment['text'].strip() if isinstance(segment, dict) else segment.text.strip(),
                    "start": float(segment['start'] if isinstance(segment, dict) else segment.start),
                    "end": float(segment['end'] if isinstance(segment, dict) else segment.end)
                })
        else:
             segments.append({
                 "text": transcription.text,
                 "start": 0.0,
                 "end": transcription.duration
             })
             
        return segments

    @classmethod
    def _load_local_model(cls, target_model: str):
        """Helper to load local model matching get_model logic."""
        if cls._model is not None and cls._current_model_name == target_model:
            return cls._model
            
        if cls._model is not None:
            logger.info(f"Unloading model '{cls._current_model_name}'")
            del cls._model
            cls._model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        logger.info(f"Loading Whisper model: {target_model} on {settings.WHISPER_DEVICE}")
        cls._model = whisper.load_model(target_model, device=settings.WHISPER_DEVICE)
        cls._current_model_name = target_model
        return cls._model
