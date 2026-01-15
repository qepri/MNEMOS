import requests
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from ddgs import DDGS
from app.extensions import db
from app.models.user_preferences import UserPreferences

logger = logging.getLogger(__name__)

class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        pass

class DuckDuckGoProvider(SearchProvider):
    def search(self, query: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=3, region='wt-wt', safesearch='moderate'):
                    results.append(r)
        except Exception as e:
            logger.error(f"DDG search failed: {e}")
            return {"context": "", "sources": []}
            
        if not results:
             return {"context": "", "sources": []}

        # DDG results often need scraping for full context
        # We'll re-use the base class helper or simple scraping logic here if we were inheritance-based,
        # but for clean composition we'll just return raw results and let the service handle scraping or 
        # let's include scraping here for DDG as it was before.
        
        # Actually, let's keep the scraping logic common or specific. 
        # The previous implementation scraped top 2.
        
        return self._format_results(results)

    def _format_results(self, results):
        context_parts = []
        sources_metadata = []
        
        # We will attempt to scrape content for the top 2 results to provide deeper context
        # Ideally this should be a shared utility, but for now we'll inline it to keep providers self-contained or use a mixin
        MAX_SCRAPE = 2
        
        for i, res in enumerate(results):
            title = res.get('title', 'No Title')
            href = res.get('href', '')
            snippet = res.get('body', '')
            
            content = snippet
            is_full_content = False
            
            # Scrape top results (Simple inline version of previous logic)
            if i < MAX_SCRAPE and href:
                scraped = self._scrape(href)
                if scraped:
                    content = scraped
                    is_full_content = True
            
            source_label = f"[Web Source {i+1}: {title}]({href})"
            if is_full_content:
                context_parts.append(f"{source_label}\n(Full Content Extracted):\n{content}")
            else:
                context_parts.append(f"{source_label}\n(Snippet):\n{content}")

            sources_metadata.append({
                "document": f"Web: {title}",
                "location": href,
                "text": snippet[:300] + "...",
                "file_type": "web",
                "score": 1.0 if i == 0 else 0.8,
                "document_id": f"web_{i}",
                "metadata": {"url": href}
            })

        formatted = "\n\n=== WEB SEARCH RESULTS (DuckDuckGo) ===\n" + "\n\n".join(context_parts) + "\n==========================\n"
        return {"context": formatted, "sources": sources_metadata}

    def _scrape(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.content, 'html.parser')
                for s in soup(["script", "style", "nav", "footer", "header"]):
                    s.decompose()
                text = soup.get_text(separator=' ', strip=True)
                import re
                text = re.sub(r'\s+', ' ', text)
                return text[:4000]
        except:
            return None
        return None

class TavilyProvider(SearchProvider):
    def search(self, query: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        if not api_key:
            return {"context": "Error: Tavily API Key missing.", "sources": []}
            
        try:
            # Tavily Search API
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": api_key,
                "query": query,
                "search_depth": "basic", 
                "include_answer": True,
                "include_raw_content": False,
                "max_results": 3,
                "include_images": False
            }
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            results = data.get('results', [])
            answer = data.get('answer', '')
            
            context_parts = []
            if answer:
                context_parts.append(f"Direct Answer: {answer}")
                
            sources_metadata = []
            
            for i, res in enumerate(results):
                title = res.get('title', 'No Title')
                url = res.get('url', '')
                content = res.get('content', '')
                
                context_parts.append(f"[Web Source {i+1}: {title}]({url})\n{content}")
                
                sources_metadata.append({
                    "document": f"Web: {title}",
                    "location": url,
                    "text": content[:300] + "...",
                    "file_type": "web",
                    "score": res.get('score', 0.8),
                    "document_id": f"web_tavily_{i}",
                    "metadata": {"url": url}
                })
                
            formatted = "\n\n=== WEB SEARCH RESULTS (Tavily) ===\n" + "\n\n".join(context_parts) + "\n==========================\n"
            return {"context": formatted, "sources": sources_metadata}

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return {"context": "", "sources": []}

class BraveProvider(SearchProvider):
    def search(self, query: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        if not api_key:
            return {"context": "Error: Brave API Key missing.", "sources": []}
            
        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "X-Subscription-Token": api_key,
                "Accept": "application/json"
            }
            params = {"q": query, "count": 3}
            
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            # Brave structure: web -> results
            results = data.get('web', {}).get('results', [])
            
            context_parts = []
            sources_metadata = []
            
            for i, res in enumerate(results):
                title = res.get('title', 'No Title')
                url = res.get('url', '')
                desc = res.get('description', '')
                
                # Brave provides description snippets. We might want to scrape if we want full content,
                # but for simplicity/speed we'll stick to snippet for now as Brave is "Privacy/Index" focused, 
                # usually acts like a standard search engine.
                
                context_parts.append(f"[Web Source {i+1}: {title}]({url})\n{desc}")
                
                sources_metadata.append({
                    "document": f"Web: {title}",
                    "location": url,
                    "text": desc,
                    "file_type": "web",
                    "score": 0.9 if i==0 else 0.7,
                    "document_id": f"web_brave_{i}",
                    "metadata": {"url": url}
                })

            formatted = "\n\n=== WEB SEARCH RESULTS (Brave) ===\n" + "\n\n".join(context_parts) + "\n==========================\n"
            return {"context": formatted, "sources": sources_metadata}
            
        except Exception as e:
            logger.error(f"Brave search failed: {e}")
            return {"context": "", "sources": []}


class WebSearchService:
    def __init__(self):
        # We don't preload preferences here to avoid context issues, we'll fetch on search
        pass

    def search(self, query: str) -> Dict[str, Any]:
        """
        Performs a web search using the selected provider.
        """
        # Fetch preferences
        prefs = db.session.query(UserPreferences).first()
        provider_name = 'duckduckgo'
        tavily_key = None
        brave_key = None
        
        if prefs:
            provider_name = prefs.web_search_provider or 'duckduckgo'
            tavily_key = prefs.tavily_api_key
            brave_key = prefs.brave_search_api_key
            
        logger.info(f"Adding web search context using provider: {provider_name}")
        
        provider: SearchProvider = DuckDuckGoProvider()
        api_key = None
        
        if provider_name == 'tavily':
            provider = TavilyProvider()
            api_key = tavily_key
        elif provider_name == 'brave':
            provider = BraveProvider()
            api_key = brave_key
            
        return provider.search(query, api_key)
