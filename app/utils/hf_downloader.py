import os
import requests
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class HFDownloader:
    """
    Handles interactions with Hugging Face for direct GGUF downloads.
    """
    
    BASE_API_URL = "https://huggingface.co/api/models"
    IMPORT_DIR = "/app/ollama_import"

    @staticmethod
    def list_gguf_files(repo_id):
        """
        List all GGUF files in a repository with metadata.
        """
        try:
            url = f"{HFDownloader.BASE_API_URL}/{repo_id}/tree/main"
            # Follow redirects (some repos redirect to specific branch/hash)
            response = requests.get(url, allow_redirects=True, timeout=10)
            response.raise_for_status()
            
            files = response.json()
            gguf_files = []
            
            for file in files:
                path = file.get('path', '')
                if path.endswith('.gguf'):
                    gguf_files.append({
                        'filename': path,
                        'size': file.get('size', 0),
                        'size_mb': round(file.get('size', 0) / (1024 * 1024), 2),
                        'quantization': HFDownloader._extract_quantization(path)
                    })
            
            # Sort by size (proxy for quantization quality/cost)
            gguf_files.sort(key=lambda x: x['size'])
            return gguf_files
            
        except Exception as e:
            logger.error(f"Error listing files for {repo_id}: {e}")
            raise e

    @staticmethod
    def _extract_quantization(filename):
        """Extract quantization tag from filename (e.g., Q4_K_M)."""
        filename = filename.lower()
        if 'q4_k_m' in filename: return 'Q4_K_M'
        if 'q5_k_m' in filename: return 'Q5_K_M'
        if 'q8_0' in filename: return 'Q8_0'
        if 'q4_0' in filename: return 'Q4_0'
        if 'q5_0' in filename: return 'Q5_0'
        if 'q6_k' in filename: return 'Q6_K'
        if 'q2_k' in filename: return 'Q2_K'
        if 'q3_k' in filename: return 'Q3_K'
        if 'fp16' in filename: return 'FP16'
        return 'Unknown'

    @staticmethod
    def download_file(repo_id, filename, progress_callback=None):
        """
        Stream download a file from HF.
        progress_callback: function(current, total)
        """
        url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        dest_path = os.path.join(HFDownloader.IMPORT_DIR, filename)
        
        # Ensure directory exists
        os.makedirs(HFDownloader.IMPORT_DIR, exist_ok=True)
        
        logger.info(f"Downloading {url} to {dest_path}")
        
        try:
            with requests.get(url, stream=True, allow_redirects=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                downloaded = 0
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total_size)
                                
            return dest_path
        except Exception as e:
            logger.error(f"Download failed: {e}")
            # Clean up partial file
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise e

    @staticmethod
    def create_modelfile(model_name, filename):
        """
        Create a Modelfile for the given GGUF.
        Note: The path in FROM must be viewed from the OLLAMA container.
        Ollama container sees the import dir at /root/.ollama/import
        """
        modelfile_content = f"FROM /root/.ollama/import/{filename}\n"
        
        # Determine path to save Modelfile. Ideally alongside the GGUF for temporary usage.
        modelfile_path = os.path.join(HFDownloader.IMPORT_DIR, f"{model_name}.Modelfile")
        
        with open(modelfile_path, 'w') as f:
            f.write(modelfile_content)
            
        return modelfile_content
