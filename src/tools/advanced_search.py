from src.tools.search import HybridSearch
from src.tools.academic_sources import ArXivSearch, SemanticScholarSearch
from src.tools.scraper import WebScraper
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class UnifiedSearch:
    """Unified interface for all search sources."""
    
    def __init__(self, tavily_key: str, serper_key: str):
        """Initialize unified search.
        
        Args:
            tavily_key: Tavily API key
            serper_key: Serper API key
        """
        self.hybrid_search = HybridSearch(tavily_key, serper_key)
        self.arxiv = ArXivSearch()
        self.semantic_scholar = SemanticScholarSearch()
        self.scraper = WebScraper()
    
    async def search_all_sources(
        self,
        query: str,
        include_web: bool = True,
        include_academic: bool = True,
        max_results: int = 20
    ) -> Dict[str, List[Any]]:
        """Search across all available sources.
        
        Args:
            query: Search query
            include_web: Include web search results
            include_academic: Include academic sources
            max_results: Maximum results per source
        
        Returns:
            Dictionary with results by source
        """
        results = {}
        
        # Web search
        if include_web:
            results["web"] = await self.hybrid_search.search(
                query=query,
                max_results=max_results
            )
        
        # Academic sources
        if include_academic:
            results["arxiv"] = await self.arxiv.search(
                query=query,
                max_results=max_results
            )
            
            results["semantic_scholar"] = await self.semantic_scholar.search_papers(
                query=query,
                limit=max_results
            )
        
        return results
    
    async def search_with_enrichment(
        self,
        query: str,
        enrich_with_content: bool = True
    ) -> List[Dict[str, Any]]:
        """Search and enrich results with full content.
        
        Args:
            query: Search query
            enrich_with_content: Whether to scrape full content
        
        Returns:
            List of enriched results
        """
        # Get initial results
        web_results = await self.hybrid_search.search(query, max_results=5)
        
        enriched = []
        
        for result in web_results:
            if enrich_with_content:
                # Scrape full content
                scraped = await self.scraper.scrape(result.get("url"))
                
                if scraped:
                    result["full_content"] = scraped.get("content")
                    result["additional_links"] = scraped.get("links", [])
            
            enriched.append(result)
        
        return enriched


class FacetedSearch:
    """Search with filtering and faceting."""
    
    @staticmethod
    def filter_by_date(
        results: List[Dict[str, Any]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filter results by date range.
        
        Args:
            results: Search results
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Filtered results
        """
        filtered = results
        
        if start_date:
            filtered = [
                r for r in filtered
                if r.get("published_date", "") >= start_date
            ]
        
        if end_date:
            filtered = [
                r for r in filtered
                if r.get("published_date", "") <= end_date
            ]
        
        return filtered
    
    @staticmethod
    def filter_by_source_type(
        results: List[Dict[str, Any]],
        source_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Filter results by source type.
        
        Args:
            results: Search results
            source_types: List of source types to include
        
        Returns:
            Filtered results
        """
        return [
            r for r in results
            if r.get("source") in source_types
        ]
    
    @staticmethod
    def filter_by_quality(
        results: List[Dict[str, Any]],
        min_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Filter results by quality score.
        
        Args:
            results: Search results
            min_score: Minimum quality score
        
        Returns:
            Filtered results
        """
        return [
            r for r in results
            if r.get("relevance_score", 0) >= min_score
        ]