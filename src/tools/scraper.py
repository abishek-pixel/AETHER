"""Web scraping tools for Aether research agents."""

import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class WebScraper:
    """Web scraper for extracting content from URLs."""
    
    def __init__(self, timeout: float = 10.0, max_content_length: int = 50000):
        """Initialize web scraper.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_content_length: Maximum content to retrieve in bytes
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape content from a URL.
        
        Args:
            url: URL to scrape
        
        Returns:
            Dictionary with scraped content or None if failed
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.headers
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Check content length
                content = response.text
                if len(content) > self.max_content_length:
                    content = content[:self.max_content_length]
                
                # Parse content
                parsed = self._parse_content(url, content, response)
                return parsed
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error scraping {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return None
    
    def _parse_content(
        self,
        url: str,
        html: str,
        response: httpx.Response
    ) -> Dict[str, Any]:
        """Parse HTML content into structured data.
        
        Args:
            url: Original URL
            html: HTML content
            response: HTTP response object
        
        Returns:
            Parsed content dictionary
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract metadata
        title = self._extract_title(soup)
        description = self._extract_description(soup)
        author = self._extract_author(soup)
        publish_date = self._extract_date(soup)
        
        # Extract main content
        text_content = self._extract_text(soup)
        
        # Extract links
        links = self._extract_links(soup, url)
        
        return {
            "url": url,
            "title": title,
            "description": description,
            "author": author,
            "publish_date": publish_date,
            "content": text_content,
            "links": links,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "scraped_at": datetime.utcnow().isoformat(),
            "content_length": len(text_content),
        }
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try <h1>
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        # Try <title>
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        
        # Try meta og:title
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title:
            return og_title.get("content", "")
        
        return ""
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract page description."""
        # Try meta description
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            return meta_desc.get("content", "")
        
        # Try og:description
        og_desc = soup.find("meta", {"property": "og:description"})
        if og_desc:
            return og_desc.get("content", "")
        
        return ""
    
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Extract author information."""
        # Try author meta tag
        author = soup.find("meta", {"name": "author"})
        if author:
            return author.get("content", "")
        
        # Try article:author
        article_author = soup.find("meta", {"property": "article:author"})
        if article_author:
            return article_author.get("content", "")
        
        # Look for byline patterns
        byline = soup.find(class_=re.compile("byline|author", re.I))
        if byline:
            return byline.get_text(strip=True)
        
        return ""
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract publication date."""
        # Try article:published_time
        pub_date = soup.find("meta", {"property": "article:published_time"})
        if pub_date:
            return pub_date.get("content")
        
        # Try datePublished schema
        date_published = soup.find("meta", {"itemprop": "datePublished"})
        if date_published:
            return date_published.get("content")
        
        # Look for date patterns in text
        date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            match = date_pattern.search(script.string or "")
            if match:
                return match.group()
        
        return None
    
    def _extract_text(self, soup: BeautifulSoup, max_paragraphs: int = 20) -> str:
        """Extract main text content."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Try article content patterns
        content = None
        for selector in ["article", ".article-content", ".post-content", ".main-content"]:
            content = soup.select_one(selector)
            if content:
                break
        
        if not content:
            content = soup.body if soup.body else soup
        
        # Extract paragraphs
        paragraphs = []
        for p in content.find_all("p")[:max_paragraphs]:
            text = p.get_text(strip=True)
            if text and len(text) > 20:  # Skip very short paragraphs
                paragraphs.append(text)
        
        return "\n\n".join(paragraphs)
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list:
        """Extract links from page."""
        links = []
        
        for link in soup.find_all("a", href=True)[:50]:  # Limit to 50 links
            href = link.get("href")
            text = link.get_text(strip=True)
            
            # Skip anchors
            if href.startswith("#"):
                continue
            
            links.append({
                "url": href,
                "text": text[:100],  # Truncate long text
            })
        
        return links


class ContentValidator:
    """Validate and assess content quality."""
    
    @staticmethod
    def is_relevant(
        content: str,
        keywords: list[str],
        min_matches: int = 1
    ) -> bool:
        """Check if content is relevant based on keywords.
        
        Args:
            content: Content to check
            keywords: Keywords to search for
            min_matches: Minimum keyword matches required
        
        Returns:
            True if content meets relevance criteria
        """
        matches = sum(
            1 for keyword in keywords
            if keyword.lower() in content.lower()
        )
        return matches >= min_matches
    
    @staticmethod
    def assess_credibility(url: str, content_length: int) -> str:
        """Assess source credibility based on domain and content.
        
        Args:
            url: Source URL
            content_length: Length of content in characters
        
        Returns:
            Credibility level: "high", "medium", or "low"
        """
        high_credibility_domains = [
            ".edu", ".gov", "academic", "scholar", "journal",
            "nature.com", "science.org", "arxiv.org", "jstor.org",
            "ieee.org", "springer.com", "sciencedirect.com",
            "pubmed.gov", "nist.gov"
        ]
        
        low_credibility_domains = [
            "reddit.com", "medium.com", "quora.com", "blogspot",
            "wordpress.com", "tumblr.com", "facebook.com"
        ]
        
        url_lower = url.lower()
        
        # Check domain credibility
        if any(domain in url_lower for domain in high_credibility_domains):
            credibility = "high"
        elif any(domain in url_lower for domain in low_credibility_domains):
            credibility = "low"
        else:
            credibility = "medium"
        
        # Adjust based on content length (very short content is less credible)
        if content_length < 500 and credibility != "high":
            credibility = "low"
        elif content_length > 5000 and credibility != "low":
            credibility = "high"
        
        return credibility
    
    @staticmethod
    def extract_claims(content: str) -> list[str]:
        """Extract potential factual claims from content.
        
        Args:
            content: Text content
        
        Returns:
            List of sentences that appear to contain claims
        """
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', content)
        
        claims = []
        for sentence in sentences:
            sentence = sentence.strip()
            
            # Skip very short sentences
            if len(sentence) < 20:
                continue
            
            # Look for sentences with factual indicators
            if any(indicator in sentence.lower() for indicator in [
                "is", "are", "was", "were", "found", "showed",
                "demonstrated", "indicates", "suggests", "according"
            ]):
                claims.append(sentence)
        
        return claims[:20]  # Return top 20 claims


class LinkValidator:
    """Validate and check links for accessibility."""
    
    def __init__(self, timeout: float = 5.0):
        """Initialize link validator.
        
        Args:
            timeout: HTTP timeout for link checks
        """
        self.timeout = timeout
    
    async def is_accessible(self, url: str) -> bool:
        """Check if a URL is accessible.
        
        Args:
            url: URL to check
        
        Returns:
            True if URL is accessible (status 200-299)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.head(url, follow_redirects=True)
                return 200 <= response.status_code < 300
        except Exception as e:
            logger.warning(f"Could not validate URL {url}: {str(e)}")
            return False
    
    async def batch_validate(self, urls: list[str]) -> Dict[str, bool]:
        """Validate multiple URLs concurrently.
        
        Args:
            urls: List of URLs to validate
        
        Returns:
            Dictionary mapping URLs to accessibility status
        """
        results = {}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                tasks = [
                    self._check_url(client, url)
                    for url in urls
                ]
                
                for url, accessible in zip(urls, tasks):
                    results[url] = accessible
        
        except Exception as e:
            logger.error(f"Batch validation error: {str(e)}")
            for url in urls:
                results[url] = False
        
        return results
    
    async def _check_url(self, client: httpx.AsyncClient, url: str) -> bool:
        """Check single URL accessibility."""
        try:
            response = await client.head(url, follow_redirects=True)
            return 200 <= response.status_code < 300
        except Exception:
            return False
