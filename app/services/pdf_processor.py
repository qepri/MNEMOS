import fitz  # PyMuPDF
from typing import List, Dict

class PDFProcessor:
    def extract_text(self, file_path: str) -> tuple[List[Dict], Dict]:
        """
        Extract text and metadata from PDF.
        Returns: (
            [{"text": "...", "page": 1}, ...],
            {"title": "...", "author": "...", ...}
        )
        """
        doc = fitz.open(file_path)
        pages = []
        
        # Extract metadata
        # PyMuPDF metadata dict keys: format, title, author, subject, keywords, creator, producer, creationDate, modDate, encryption
        metadata = {}
        if doc.metadata:
            for key in ['title', 'author', 'subject', 'keywords']:
                if doc.metadata.get(key):
                    metadata[key] = doc.metadata[key]
        
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append({
                    "text": text.strip(),
                    "page": i + 1
                })
                
        return pages, metadata
