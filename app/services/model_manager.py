"""
In-memory model selection manager.
Allows runtime switching of LLM models without restarting the app.
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ModelManager:
    """Singleton to manage current LLM model selection."""

    _instance = None
    _current_model: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_model(cls, model_name: str):
        """Set the current LLM model."""
        old_model = cls._current_model
        cls._current_model = model_name
        logger.info(f"LLM model changed: {old_model} -> {model_name}")
        
        # Persist to DB
        try:
            from app.extensions import db
            from app.models.user_preferences import UserPreferences
            
            # We need an app context to access DB
            # This method is usually called from an API request (which has context)
            # If not, we skip persistence
            if db.session.registry.has():
                prefs = db.session.query(UserPreferences).first()
                if not prefs:
                    prefs = UserPreferences()
                    db.session.add(prefs)
                
                if prefs.selected_llm_model != model_name:
                    prefs.selected_llm_model = model_name
                    db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist model selection: {e}")

    @classmethod
    def get_model(cls) -> Optional[str]:
        """Get the current LLM model."""
        if cls._current_model is None:
            # Try to load from DB
            try:
                from app.extensions import db
                from app.models.user_preferences import UserPreferences
                
                if db.session.registry.has():
                    prefs = db.session.query(UserPreferences).first()
                    if prefs and prefs.selected_llm_model:
                        cls._current_model = prefs.selected_llm_model
                        logger.info(f"Loaded persisted model: {cls._current_model}")
            except Exception as e:
                logger.warning(f"Failed to load peristed model: {e}")
                
        return cls._current_model

    @classmethod
    def has_model(cls) -> bool:
        """Check if a model is selected."""
        return cls.get_model() is not None

# Global instance
model_manager = ModelManager()
