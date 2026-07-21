import httpx
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ArXivSearch:
    """Search ArXiv academic papers."""
    
    def __init__(self):
        """Initialize ArXiv search."""
        self.base_url = "http://export.arxiv.org/api/query"
        self.timeout = 30.0
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        sort_by: str = "relevance"
    ) -> List[Dict[str, Any]]:
        """Search ArXiv for papers.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            sort_by: Sort order (relevance, submittedDate, etc.)
        
        Returns:
            List of papers
        """
        try:
            # Format ArXiv query
            arxiv_query = f'search_query=all:{query}&start=0&max_results={max_results}&sortBy={sort_by}'
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}?{arxiv_query}",
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return self._parse_arxiv_response(response.text)
                else:
                    logger.error(f"ArXiv API error: {response.status_code}")
                    return []
        
        except Exception as e:
            logger.error(f"ArXiv search error: {str(e)}")
            return []
    
    def _parse_arxiv_response(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse ArXiv XML response.
        
        Args:
            xml_content: XML response from ArXiv
        
        Returns:
            List of parsed papers
        """
        import xml.etree.ElementTree as ET
        
        papers = []
        root = ET.fromstring(xml_content)
        
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        
        for entry in root.findall('atom:entry', namespaces):
            paper = {
                "title": entry.findtext('atom:title', namespaces=namespaces),
                "authors": [
                    author.findtext('atom:name', namespaces=namespaces)
                    for author in entry.findall('atom:author', namespaces=namespaces)
                ],
                "summary": entry.findtext('atom:summary', namespaces=namespaces),
                "published": entry.findtext('atom:published', namespaces=namespaces),
                "arxiv_id": entry.findtext('atom:id', namespaces=namespaces).split('/abs/')[-1],
                "pdf_url": entry.findtext('atom:id', namespaces=namespaces).replace('abs', 'pdf') + '.pdf',
                "categories": entry.findtext('arxiv:primary_category', namespaces=namespaces),
            }
            papers.append(paper)
        
        return papers


class SemanticScholarSearch:
    """Search Semantic Scholar database."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Semantic Scholar search.
        
        Args:
            api_key: Optional API key for higher rate limits
        """
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.timeout = 30.0
    
    async def search_papers(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search Semantic Scholar for papers.
        
        Args:
            query: Search query
            limit: Maximum results
            offset: Result offset
        
        Returns:
            List of papers
        """
        try:
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/paper/search",
                    params={
                        "query": query,
                        "limit": limit,
                        "offset": offset,
                        "fields": "paperId,title,authors,year,citationCount,abstract"
                    },
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.error(f"Semantic Scholar error: {response.status_code}")
                    return []
        
        except Exception as e:
            logger.error(f"Semantic Scholar search error: {str(e)}")
            return []
    
    async def get_paper_details(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a paper.
        
        Args:
            paper_id: Semantic Scholar paper ID
        
        Returns:
            Paper details
        """
        try:
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/paper/{paper_id}",
                    params={
                        "fields": "paperId,title,authors,year,citationCount,references,citations,abstract"
                    },
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
        
        except Exception as e:
            logger.error(f"Error fetching paper details: {str(e)}")
            return None


class GoogleScholarSearch:
    """Search Google Scholar (unofficial via free service)."""
    
    def __init__(self):
        """Initialize Google Scholar search."""
        self.base_url = "https://scholar.google.com/scholar"
    
    async def search(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search Google Scholar.
        
        Args:
            query: Search query
            max_results: Maximum results
        
        Returns:
            List of papers
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "q": query,
                        "num": max_results
                    },
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return self._parse_scholar_html(response.text)
                else:
                    return []
        
        except Exception as e:
            logger.error(f"Google Scholar search error: {str(e)}")
            return []
    
    def _parse_scholar_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse Google Scholar HTML response.
        
        Args:
            html: HTML response
        
        Returns:
            List of papers
        """
        from bs4 import BeautifulSoup
        
        papers = []
        soup = BeautifulSoup(html, "html.parser")
        
        for result in soup.find_all("div", class_="gs_ri"):
            try:
                title_elem = result.find("h3", class_="gs_rt")
                title = title_elem.get_text() if title_elem else "Unknown"
                
                url_elem = title_elem.find("a") if title_elem else None
                url = url_elem.get("href") if url_elem else ""
                
                snippet = result.find("div", class_="gs_rs")
                summary = snippet.get_text() if snippet else ""
                
                papers.append({
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "source": "Google Scholar"
                })
            
            except Exception as e:
                logger.warning(f"Error parsing paper: {str(e)}")
                continue
        
        return papers