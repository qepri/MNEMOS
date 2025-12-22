import fitz  # PyMuPDF
from typing import List, Dict

class PDFProcessor:
    def extract_text(self, file_path: str) -> List[Dict]:
        """
        Extract text from PDF pages.
        Returns: [{"text": "...", "page": 1}, ...]
        """
        doc = fitz.open(file_path)
        pages = []
        
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append({
                    "text": text.strip(),
                    "page": i + 1
                })
                
        return pages
