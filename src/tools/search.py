"""Web search tools for Aether research agents."""

import httpx
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TavilySearch:
    """Tavily API wrapper for web search."""
    
    def __init__(self, api_key: str):
        """Initialize Tavily search tool.
        
        Args:
            api_key: Tavily API key from environment
        """
        self.api_key = api_key
        self.base_url = "https://api.tavily.com"
        self.client = None
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_raw_content: bool = True,
    ) -> List[Dict[str, Any]]:
        """Execute a search query using Tavily API.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (default 5)
            search_depth: "basic" or "advanced" search
            include_raw_content: Include raw page content
        
        Returns:
            List of search results with metadata
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                    "include_raw_content": include_raw_content,
                    "include_images": False,
                    "include_answer": True,
                }
                
                response = await client.post(
                    f"{self.base_url}/search",
                    json=payload,
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_tavily_results(data)
                else:
                    logger.error(f"Tavily API error: {response.status_code}")
                    return []
        
        except Exception as e:
            logger.error(f"Tavily search error: {str(e)}")
            return []
    
    def _parse_tavily_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Tavily API response into standardized format.
        
        Args:
            data: Raw response from Tavily API
        
        Returns:
            Standardized list of search results
        """
        results = []
        
        if "results" not in data:
            return results
        
        for item in data.get("results", []):
            result = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "raw_content": item.get("raw_content", ""),
                "published_date": item.get("published_date"),
                "source": "tavily",
                "relevance_score": item.get("score", 0),
            }
            results.append(result)
        
        return results


class SerperSearch:
    """Google Serper API wrapper for web search."""
    
    def __init__(self, api_key: str):
        """Initialize Serper search tool.
        
        Args:
            api_key: Serper API key from environment
        """
        self.api_key = api_key
        self.base_url = "https://google.serper.dev"
        self.client = None
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        gl: str = "us",
    ) -> List[Dict[str, Any]]:
        """Execute a search query using Serper API.
        
        Args:
            query: Search query string
            max_results: Maximum number of results
            language: Language code (default "en")
            gl: Geographic location (default "us")
        
        Returns:
            List of search results with metadata
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                }
                
                payload = {
                    "q": query,
                    "num": max_results,
                    "autocorrect": True,
                    "page": 1,
                    "type": "search",
                    "engine": "google",
                    "gl": gl,
                    "hl": language,
                }
                
                response = await client.post(
                    f"{self.base_url}/search",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_serper_results(data)
                else:
                    logger.error(f"Serper API error: {response.status_code}")
                    return []
        
        except Exception as e:
            logger.error(f"Serper search error: {str(e)}")
            return []
    
    def _parse_serper_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Serper API response into standardized format.
        
        Args:
            data: Raw response from Serper API
        
        Returns:
            Standardized list of search results
        """
        results = []
        
        # Parse organic search results
        for item in data.get("organic", []):
            result = {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "content": item.get("snippet", ""),
                "raw_content": item.get("snippet", ""),
                "published_date": None,
                "source": "serper",
                "relevance_score": 1.0 / (len(results) + 1),  # Rank-based scoring
            }
            results.append(result)
        
        # Parse answer box if available
        if "answerBox" in data:
            answer = data["answerBox"]
            result = {
                "title": answer.get("title", "Answer"),
                "url": answer.get("source", ""),
                "content": answer.get("answer", "") or answer.get("snippet", ""),
                "raw_content": answer.get("answer", "") or answer.get("snippet", ""),
                "published_date": None,
                "source": "serper_answer_box",
                "relevance_score": 1.1,  # Higher priority
            }
            results.insert(0, result)
        
        # Parse knowledge graph if available
        if "knowledgeGraph" in data:
            kg = data["knowledgeGraph"]
            result = {
                "title": kg.get("title", "Knowledge"),
                "url": kg.get("website", ""),
                "content": kg.get("description", ""),
                "raw_content": kg.get("description", ""),
                "published_date": None,
                "source": "serper_knowledge_graph",
                "relevance_score": 1.2,  # Highest priority
            }
            results.insert(0, result)
        
        return results


class HybridSearch:
    """Combines Tavily and Serper for comprehensive search coverage."""
    
    def __init__(self, tavily_api_key: str, serper_api_key: str):
        """Initialize hybrid search with both providers.
        
        Args:
            tavily_api_key: Tavily API key
            serper_api_key: Serper API key
        """
        self.tavily = TavilySearch(tavily_api_key)
        self.serper = SerperSearch(serper_api_key)
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        min_relevance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Execute hybrid search combining both APIs.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            min_relevance: Minimum relevance score threshold
        
        Returns:
            Combined and deduplicated list of results
        """
        try:
            # Execute both searches concurrently
            tavily_results = await self.tavily.search(query, max_results=10)
            serper_results = await self.serper.search(query, max_results=10)
            
            # Combine and deduplicate
            combined = self._deduplicate_results(tavily_results + serper_results)
            
            # Filter by relevance and limit
            filtered = [
                r for r in combined
                if r.get("relevance_score", 0) >= min_relevance
            ][:max_results]
            
            return filtered
        
        except Exception as e:
            logger.error(f"Hybrid search error: {str(e)}")
            return []
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate search results by URL.
        
        Args:
            results: List of search results
        
        Returns:
            Deduplicated results with merged metadata
        """
        seen_urls = {}
        deduplicated = []
        
        for result in results:
            url = result.get("url", "").lower()
            
            if not url:
                continue
            
            if url in seen_urls:
                # Merge metadata if we've seen this URL
                existing = seen_urls[url]
                existing["sources"] = list(set(
                    existing.get("sources", []) + [result.get("source", "")]
                ))
                # Keep highest relevance score
                existing["relevance_score"] = max(
                    existing.get("relevance_score", 0),
                    result.get("relevance_score", 0)
                )
            else:
                # Add new result
                result["sources"] = [result.get("source", "")]
                seen_urls[url] = result
                deduplicated.append(result)
        
        # Sort by relevance score
        deduplicated.sort(
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )
        
        return deduplicated


class SearchResult:
    """Structured search result object."""
    
    def __init__(
        self,
        title: str,
        url: str,
        content: str,
        source: str = "unknown",
        relevance_score: float = 0.0,
        published_date: Optional[str] = None,
    ):
        self.title = title
        self.url = url
        self.content = content
        self.source = source
        self.relevance_score = relevance_score
        self.published_date = published_date
        self.retrieved_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "source": self.source,
            "relevance_score": self.relevance_score,
            "published_date": self.published_date,
            "retrieved_at": self.retrieved_at.isoformat(),
        }
    
    def truncate_content(self, max_length: int = 500) -> str:
        """Truncate content to maximum length.
        
        Args:
            max_length: Maximum content length
        
        Returns:
            Truncated content
        """
        if len(self.content) <= max_length:
            return self.content
        
        truncated = self.content[:max_length]
        # Find last complete sentence
        last_period = truncated.rfind(".")
        if last_period > 0:
            return truncated[:last_period + 1]
        
        return truncated + "..."
