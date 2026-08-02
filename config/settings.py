import os
from enum import Enum
from pydantic_settings import BaseSettings

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    LM_STUDIO = "lm_studio"
    LLAMACPP = "llamacpp"
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
    LLM_PROVIDER: LLMProvider = LLMProvider.LLAMACPP
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Cerebras
    CEREBRAS_API_KEY: str = ""
    CEREBRAS_MODEL: str = "llama-3.3-70b"

    # LM Studio / generic OpenAI-compatible local server
    LOCAL_LLM_BASE_URL: str = "http://host.docker.internal:1234/v1"
    LOCAL_LLM_MODEL: str = "local-model"

    # llama.cpp (Dockerized) - Lightweight GGUF server
    LLAMACPP_BASE_URL: str = "http://llamacpp:8080/v1"
    LLAMACPP_NUM_CTX: int = 2048

    # Embeddings
    # Defaults must match the environment that produced the live vectors:
    # local sentence-transformers with BAAI/bge-m3 at dimension 1024.
    # Changing EMBEDDING_DIMENSION invalidates every stored chunk vector.
    EMBEDDING_PROVIDER: str = "local"  # local (sentence-transformers), openai, lm_studio
    EMBEDDING_MODEL: str = "BAAI/bge-m3"  # Multilingual support
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
    
    # Hypergraph LLM provider (default: llamacpp to reduce API costs)
    # Set empty ("") to use the same provider as chat.
    HYPERGRAPH_LLM_PROVIDER: str = ""

    # Chunking
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 100
    
    # Vision / Diagram Extraction
    VISION_ENABLED: bool = False          # Set True to describe diagrams via vision LLM
    VISION_MODEL: str = ""                # Override model for vision calls (e.g. deepseek-vl2). Empty = use active LLM model.
    VISION_SKIP_UNKNOWN_MODELS: bool = True  # Skip vision call if model isn't in the known-vision allowlist
    DIAGRAMS_MAX_PER_DOC: int = 50        # Safety cap: max images extracted per document

    # Storage
    # In docker, mapped to /app/uploads
    # Default to a local 'uploads' directory for Windows dev
    UPLOAD_FOLDER: str = os.path.join(os.getcwd(), 'uploads') if os.name == 'nt' else "/app/uploads"
    TRANSCRIPTION_FOLDER: str = os.path.join(UPLOAD_FOLDER, 'transcriptions')
    ARCHIVE_FOLDER: str = os.path.join(os.getcwd(), 'archive') if os.name == 'nt' else "/app/archive"
    # Per-file-type upload ceilings. Enforced at the upload boundary before
    # anything is written to disk or queued. MAX_CONTENT_LENGTH is the
    # framework-level backstop and is set to the largest of these.
    MAX_UPLOAD_DOCUMENT: int = 512 * 1024 * 1024      # 512 MB - pdf, epub
    MAX_UPLOAD_AUDIO: int = 2 * 1024 * 1024 * 1024    # 2 GB
    MAX_UPLOAD_VIDEO: int = 8 * 1024 * 1024 * 1024    # 8 GB
    MAX_CONTENT_LENGTH: int = 8 * 1024 * 1024 * 1024  # backstop = largest above

    # VideoMix Settings
    VIDEOMIX_MAX_SEGMENTS: int = 50  # Maximum segments per video
    VIDEOMIX_DEFAULT_RESOLUTION: str = '1080p'
    VIDEOMIX_RENDER_TIMEOUT: int = 3600  # 1 hour timeout for rendering tasks

    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8' # Ensure encoding is supported
        extra = "ignore" # Ignore extra env vars

settings = Settings()
