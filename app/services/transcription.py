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

    @classmethod
    def get_model(cls):
        # Determine target model from DB or settings
        target_model = settings.WHISPER_MODEL
        try:
            prefs = db.session.query(UserPreferences).first()
            if prefs and prefs.whisper_model:
                target_model = prefs.whisper_model
        except Exception as e:
            logger.warning(f"Could not load user preferences for Whisper: {e}")

        # If model is already loaded and is the same, return it
        if cls._model is not None and cls._current_model_name == target_model:
            return cls._model
            
        # If loading a NEW model, clear old one first to save VRAM
        if cls._model is not None:
            logger.info(f"Unloading Whisper model '{cls._current_model_name}' to load '{target_model}'")
            del cls._model
            cls._model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        # Load new model
        logger.info(f"Loading Whisper model: {target_model} on {settings.WHISPER_DEVICE}")
        cls._model = whisper.load_model(
            target_model, 
            device=settings.WHISPER_DEVICE
        )
        cls._current_model_name = target_model
        return cls._model

    def transcribe(self, audio_path: str) -> List[Dict]:
        """
        Transcribe audio/video and return segments with timestamps.
        """
        model = self.get_model()
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
