import requests
import re
from bs4 import BeautifulSoup
from ddgs import DDGS
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class WebSearchService:
    def __init__(self, max_results: int = 3):
        self.max_results = max_results

    def search(self, query: str) -> Dict[str, Any]:
        """
        Performs a web search and returns formatted context and source metadata.
        """
        results = []
        try:
            with DDGS() as ddgs:
                # Using 'text' (formerly 'text' or 'clean' depending on version, now 'text' is standard)
                for r in ddgs.text(query, max_results=self.max_results, region='wt-wt', safesearch='moderate'):
                    logger.info(f"Raw DDG Result: {r.get('title')} - {r.get('href')}")
                    results.append(r)
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {"context": "", "sources": []}

        if not results:
            return {"context": "", "sources": []}

        # Format context for LLM
        context_parts = []
        sources_metadata = []

        # We will attempt to scrape content for the top 2 results to provide deeper context
        MAX_SCRAPE = 2

        for i, res in enumerate(results):
            title = res.get('title', 'No Title')
            href = res.get('href', '')
            snippet = res.get('body', '')
            
            content = snippet # Default to snippet
            is_full_content = False

            # Try to scrape the top results for more detail
            if i < MAX_SCRAPE and href:
                scraped_text = self._fetch_page_content(href)
                if scraped_text:
                    content = scraped_text
                    is_full_content = True
                    logger.info(f"Successfully scraped content for: {href}")
                else:
                    logger.warning(f"Failed to scrape content for: {href}, falling back to snippet.")

            # Add to context string
            source_label = f"[Web Source {i+1}: {title}]({href})"
            if is_full_content:
                context_parts.append(f"{source_label}\n(Full Content Extracted):\n{content}")
            else:
                context_parts.append(f"{source_label}\n(Snippet):\n{content}")

            # Add to metadata for frontend citations
            sources_metadata.append({
                "document": f"Web: {title}",
                "location": href,
                "text": snippet[:300] + "...", # Keep tooltip/preview short
                "file_type": "web",
                "score": 1.0 if i == 0 else 0.8, # Simple ranking
                "document_id": f"web_{i}",
                "metadata": {"url": href}
            })

        formatted_context = "\n\n=== WEB SEARCH RESULTS ===\n" + "\n\n".join(context_parts) + "\n==========================\n"

        return {
            "context": formatted_context,
            "sources": sources_metadata
        }

    def _fetch_page_content(self, url: str) -> str:
        """
        Attempts to fetch and extract text from the given URL.
        Returns cleaned text or None if failed.
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            # Simple text extraction
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                script.decompose()

            text = soup.get_text(separator=' ', strip=True)
            
            # Collapse whitespace
            import re
            text = re.sub(r'\s+', ' ', text)
            
            # Limit length to avoid context overflow (approx 1000 tokens ~ 4000 chars)
            return text[:4000]
            
        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")
            return None
