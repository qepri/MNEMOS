import os
from enum import Enum
from pydantic_settings import BaseSettings

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"
    CEREBRAS = "cerebras"
    CUSTOM = "custom"

class Settings(BaseSettings):
    # App
    SECRET_KEY: str = "dev"
    
    # Database
    DATABASE_URL: str = "postgresql://mnemos_user:mnemos_pass@db:5432/mnemos_db"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # LLM Configuration
    LLM_PROVIDER: LLMProvider = LLMProvider.LM_STUDIO
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # Cerebras
    CEREBRAS_API_KEY: str = ""
    CEREBRAS_MODEL: str = "llama-3.3-70b"

    # LM Studio / Ollama (OpenAI-compatible)
    LOCAL_LLM_BASE_URL: str = "http://host.docker.internal:1234/v1"
    LOCAL_LLM_MODEL: str = "local-model"
    
    # Ollama (Dockerized)
    # Using internal docker hostname 'ollama' and port 11434
    OLLAMA_BASE_URL: str = "http://mnemos-ollama:11434/v1"
    OLLAMA_NUM_CTX: int = 2048 # Reduced to 2048 to fit in 6GB VRAM
    
    # Embeddings
    EMBEDDING_PROVIDER: str = "ollama"  # local (sentence-transformers), openai, lm_studio
    EMBEDDING_MODEL: str = "bge-m3"  # Multilingual support
    EMBEDDING_DIMENSION: int = 1024

    # Embedding Optimization (New - Auto-tuning enabled by default)
    EMBEDDING_BATCH_SIZE: int = 0  # 0 = auto-detect based on hardware, or set manually (e.g., 32, 64)
    EMBEDDING_DEVICE: str = "cuda"  # Use GPU for embeddings
    EMBEDDING_USE_FP16: bool = True  # Use mixed precision on GPU (2x faster, half VRAM)
    EMBEDDING_SHOW_PROGRESS: bool = True  # Show progress bar for large batches

    # Remote API Batching
    REMOTE_EMBEDDING_BATCH_SIZE: int = 32  # Batch size for remote APIs (OpenAI, LM Studio)
    REMOTE_EMBEDDING_MAX_WORKERS: int = 3  # Parallel API requests (be careful with rate limits)
    REMOTE_EMBEDDING_RETRY_DELAY: float = 2.0  # Seconds to wait before retry
    
    # Whisper
    WHISPER_MODEL: str = "base"  # tiny, base, small, medium, large-v3
    WHISPER_DEVICE: str = "cuda"  # cpu, cuda
    
    # Chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    
    # Storage
    # In docker, mapped to /app/uploads
    # Default to a local 'uploads' directory for Windows dev
    UPLOAD_FOLDER: str = os.path.join(os.getcwd(), 'uploads') if os.name == 'nt' else "/app/uploads"
    MAX_CONTENT_LENGTH: int = 50 * 1024 * 1024 * 1024  # 50GB
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8' # Ensure encoding is supported
        extra = "ignore" # Ignore extra env vars

settings = Settings()
