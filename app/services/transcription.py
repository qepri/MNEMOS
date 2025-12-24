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

        try:
            prefs = db.session.query(UserPreferences).first()
            if prefs:
                if prefs.whisper_model:
                    target_model = prefs.whisper_model
                # Check for provider (defaulting to local)
                if hasattr(prefs, 'transcription_provider') and prefs.transcription_provider:
                    provider = prefs.transcription_provider
                if hasattr(prefs, 'groq_api_key') and prefs.groq_api_key:
                    groq_key = prefs.groq_api_key
        except Exception as e:
            logger.warning(f"Could not load settings for transcription: {e}")

        logger.info(f"Starting transcription with Provider: {provider}, Model: {target_model}")

        if provider == 'groq':
            return self._transcribe_groq(audio_path, target_model, groq_key)
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
