from sentence_transformers import SentenceTransformer
from typing import List, Union
from config.settings import settings
from app.utils.hardware import HardwareDetector
import numpy as np
import openai
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class EmbedderService:
    _model = None
    _client = None
    _hardware_logged = False

    @classmethod
    def get_instance(cls):
        """Get or create embedding model/client instance (singleton pattern)."""
        if settings.EMBEDDING_PROVIDER == "local":
            if cls._model is None:
                # Log hardware info once
                if not cls._hardware_logged:
                    HardwareDetector.log_hardware_info()
                    cls._hardware_logged = True

                # Determine device
                if settings.EMBEDDING_DEVICE == "auto":
                    device = HardwareDetector.get_device()
                else:
                    device = settings.EMBEDDING_DEVICE

                logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL} on {device}")

                # Load model with device
                cls._model = SentenceTransformer(settings.EMBEDDING_MODEL, device=device)

                # Enable FP16 on GPU if supported and enabled
                if settings.EMBEDDING_USE_FP16 and HardwareDetector.supports_fp16():
                    logger.info("Enabling FP16 (mixed precision) for faster inference")
                    # sentence-transformers uses torch internally
                    # FP16 is handled via model.half() on CUDA
                    if device == "cuda":
                        try:
                            cls._model = cls._model.half()
                        except Exception as e:
                            logger.warning(f"Could not enable FP16: {e}. Continuing with FP32.")

            return cls._model
        else:
            # Use OpenAI client for LM Studio / Ollama / OpenAI
            if cls._client is None:
                # Determine Base URL and API Key based on provider
                base_url = settings.LOCAL_LLM_BASE_URL
                api_key = "lm-studio" # Dummy key for local

                if settings.EMBEDDING_PROVIDER == "openai":
                    base_url = None # Default
                    api_key = settings.OPENAI_API_KEY
                elif settings.EMBEDDING_PROVIDER == "ollama":
                    base_url = settings.OLLAMA_BASE_URL
                    api_key = "ollama"

                cls._client = openai.OpenAI(base_url=base_url, api_key=api_key)
            return cls._client

    def embed(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for text(s) with automatic batching optimization.

        Args:
            texts: Single string or list of strings to embed

        Returns:
            Single embedding vector or list of embedding vectors
        """
        instance = self.get_instance()
        is_single = isinstance(texts, str)

        if settings.EMBEDDING_PROVIDER == "local":
            return self._embed_local(instance, texts, is_single)
        else:
            return self._embed_remote(instance, texts, is_single)

    def _embed_local(self, model, texts: Union[str, List[str]], is_single: bool):
        """
        Embed using local sentence-transformers model with optimized batching.

        Args:
            model: SentenceTransformer instance
            texts: Text(s) to embed
            is_single: Whether input was a single string

        Returns:
            Embedding(s)
        """
        # Determine optimal batch size
        batch_size = HardwareDetector.get_optimal_batch_size(
            override=settings.EMBEDDING_BATCH_SIZE if settings.EMBEDDING_BATCH_SIZE > 0 else None
        )

        # Convert to list for uniform processing
        text_list = [texts] if is_single else texts

        logger.info(f"Embedding {len(text_list)} text(s) using local model (batch_size={batch_size})")

        try:
            # Use sentence-transformers built-in batching
            # It handles batching internally but we can specify batch_size
            embeddings = model.encode(
                text_list,
                batch_size=batch_size,
                show_progress_bar=settings.EMBEDDING_SHOW_PROGRESS and len(text_list) > 10,
                convert_to_numpy=True,
                normalize_embeddings=False  # Keep raw embeddings
            )

            # Convert to list format
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()

            # Return single embedding if input was single
            if is_single:
                return embeddings[0]

            return embeddings

        except RuntimeError as e:
            # Handle OOM errors gracefully
            if "out of memory" in str(e).lower():
                logger.warning(f"GPU OOM with batch_size={batch_size}. Retrying with smaller batches on CPU.")
                # Fallback: retry on CPU with smaller batches
                model.to('cpu')
                embeddings = model.encode(
                    text_list,
                    batch_size=8,  # Conservative CPU batch size
                    show_progress_bar=settings.EMBEDDING_SHOW_PROGRESS and len(text_list) > 10,
                    convert_to_numpy=True
                )
                if isinstance(embeddings, np.ndarray):
                    embeddings = embeddings.tolist()
                if is_single:
                    return embeddings[0]
                return embeddings
            else:
                raise

    def _embed_remote(self, client, texts: Union[str, List[str]], is_single: bool):
        """
        Embed using remote API (OpenAI, LM Studio, Ollama) with parallel batching.

        Args:
            client: OpenAI client instance
            texts: Text(s) to embed
            is_single: Whether input was a single string

        Returns:
            Embedding(s)
        """
        all_texts = [texts] if is_single else texts

        # Simple cleanup
        all_texts = [t.replace("\n", " ") for t in all_texts]

        logger.info(f"Embedding {len(all_texts)} text(s) using remote API")

        batch_size = settings.REMOTE_EMBEDDING_BATCH_SIZE
        max_workers = settings.REMOTE_EMBEDDING_MAX_WORKERS
        max_retries = 3

        # If only a few texts, use single-threaded approach
        if len(all_texts) <= batch_size:
            return self._embed_remote_batch(
                client, all_texts, is_single, max_retries
            )

        # For large datasets, use parallel batch processing
        all_embeddings = [None] * len(all_texts)

        def process_batch(batch_idx, batch_texts):
            """Process a single batch with retry logic."""
            retry_count = 0
            while retry_count < max_retries:
                try:
                    logger.debug(f"Processing batch {batch_idx} ({len(batch_texts)} texts)")
                    response = client.embeddings.create(
                        input=batch_texts,
                        model=settings.EMBEDDING_MODEL
                    )
                    # Sort by index to ensure order
                    data = sorted(response.data, key=lambda x: x.index)
                    return [d.embedding for d in data]

                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Batch {batch_idx} failed (attempt {retry_count}): {e}")
                    if retry_count < max_retries:
                        time.sleep(settings.REMOTE_EMBEDDING_RETRY_DELAY)
                    else:
                        logger.error(f"Batch {batch_idx} failed after {max_retries} retries")
                        raise

        # Create batches
        batches = []
        for i in range(0, len(all_texts), batch_size):
            batch = all_texts[i : i + batch_size]
            batches.append((i, batch))

        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_batch, idx, batch): (idx, batch)
                for idx, batch in batches
            }

            for future in as_completed(futures):
                batch_idx, batch = futures[future]
                try:
                    batch_embeddings = future.result()
                    # Place embeddings in correct position
                    for j, emb in enumerate(batch_embeddings):
                        all_embeddings[batch_idx + j] = emb

                except Exception as e:
                    logger.error(f"Fatal error processing batch starting at {batch_idx}: {e}")
                    raise

        if is_single:
            return all_embeddings[0]

        return all_embeddings

    def _embed_remote_batch(self, client, texts: List[str], is_single: bool, max_retries: int = 3):
        """
        Embed a single batch using remote API (legacy compatibility method).

        Args:
            client: OpenAI client
            texts: List of texts
            is_single: Whether to return single embedding
            max_retries: Number of retries

        Returns:
            Embedding(s)
        """
        retry_count = 0
        while retry_count < max_retries:
            try:
                logger.debug(f"Sending {len(texts)} texts to remote API")
                response = client.embeddings.create(
                    input=texts,
                    model=settings.EMBEDDING_MODEL
                )
                # Sort by index to ensure order
                data = sorted(response.data, key=lambda x: x.index)
                embeddings = [d.embedding for d in data]

                if is_single:
                    return embeddings[0]
                return embeddings

            except Exception as e:
                retry_count += 1
                logger.warning(f"Remote API call failed (attempt {retry_count}): {e}")
                if retry_count < max_retries:
                    time.sleep(settings.REMOTE_EMBEDDING_RETRY_DELAY)
                else:
                    logger.error(f"Remote API failed after {max_retries} retries")
                    raise
