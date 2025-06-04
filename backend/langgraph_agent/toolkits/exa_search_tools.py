"""
Exa AI Search Tools for NBA Agent
Provides web search capabilities with NBA-specific context
"""

import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool

try:
    from exa_py import Exa
except ImportError:
    Exa = None

from config import settings


class ExaWebSearchInput(BaseModel):
    """Input schema for Exa web search tool."""
    query: str = Field(
        description="The search query string. Use natural language queries for best results."
    )
    num_results: Optional[int] = Field(
        default=5,
        description="Number of search results to return (1-20). Defaults to 5."
    )
    include_text: Optional[bool] = Field(
        default=True,
        description="Whether to include the text content of the search results. Defaults to True."
    )
    category: Optional[str] = Field(
        default="general",
        description="Search category filter: 'general', 'news', 'research', 'github', 'twitter'. Defaults to 'general'."
    )


class ExaNBASearchInput(BaseModel):
    """Input schema for NBA-specific Exa search tool."""
    query: str = Field(
        description="NBA-related search query (e.g., 'Lakers trade rumors', 'LeBron James stats analysis', 'NBA draft prospects 2024')"
    )
    num_results: Optional[int] = Field(
        default=5,
        description="Number of search results to return (1-20). Defaults to 5."
    )
    include_domains: Optional[List[str]] = Field(
        default=None,
        description="List of domains to search within (e.g., ['nba.com', 'espn.com', 'basketball-reference.com'])"
    )
    search_type: Optional[str] = Field(
        default="neural",
        description="Search type: 'neural' for semantic search or 'keyword' for traditional keyword search. Defaults to 'neural'."
    )


class ExaContentInput(BaseModel):
    """Input schema for Exa content extraction tool."""
    url: str = Field(
        description="The URL to extract content from"
    )
    max_characters: Optional[int] = Field(
        default=5000,
        description="Maximum number of characters to extract. Defaults to 5000."
    )


def get_exa_client():
    """Get initialized Exa client with API key."""
    if not Exa:
        raise ImportError("exa_py package not installed. Install with: pip install exa_py")
    
    api_key = settings.EXA_API_KEY
    if not api_key:
        raise ValueError("EXA_API_KEY not found in environment variables")
    
    return Exa(api_key=api_key)


@tool("exa_web_search", args_schema=ExaWebSearchInput)
def exa_web_search(
    query: str,
    num_results: int = 5,
    include_text: bool = True,
    category: str = "general"
) -> str:
    """
    Perform a web search using Exa AI's neural search capabilities.
    Returns comprehensive search results with optional text content.
    Best for finding current information, news, and detailed articles.
    """
    try:
        exa = get_exa_client()
        
        # Prepare search parameters
        search_params = {
            "query": query,
            "num_results": min(num_results, 20),  # Cap at 20
            "use_autoprompt": True  # Let Exa optimize the query
        }
        
        # Note: include_text parameter is handled differently by Exa API
        # We'll request text content separately if needed
        
        # Add category-specific parameters
        if category == "news":
            search_params["include_domains"] = [
                "espn.com", "nba.com", "cnn.com", "bbc.com", 
                "reuters.com", "ap.org", "cbssports.com", "si.com"
            ]
        elif category == "research":
            search_params["include_domains"] = [
                "basketball-reference.com", "statmuse.com", "fivethirtyeight.com",
                "arxiv.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov"
            ]
        elif category == "github":
            search_params["include_domains"] = ["github.com"]
        elif category == "twitter":
            search_params["include_domains"] = ["twitter.com", "x.com"]
        
        # Perform search
        results = exa.search(**search_params)
        
        # Format results
        formatted_results = []
        for i, result in enumerate(results.results, 1):
            formatted_result = {
                "rank": i,
                "title": result.title,
                "url": result.url,
                "published_date": getattr(result, 'published_date', None),
                "score": getattr(result, 'score', None)
            }
            
            # Add text content if available directly from search results
            if hasattr(result, 'text') and result.text:
                # Truncate text to reasonable length
                text = result.text[:3000] + "..." if len(result.text) > 3000 else result.text
                formatted_result["text"] = text
            
            formatted_results.append(formatted_result)
        
        return {
            "query": query,
            "num_results": len(formatted_results),
            "category": category,
            "results": formatted_results
        }
        
    except Exception as e:
        return {
            "error": f"Exa web search failed: {str(e)}",
            "query": query,
            "results": []
        }


@tool("exa_nba_search", args_schema=ExaNBASearchInput)
def exa_nba_search(
    query: str,
    num_results: int = 5,
    include_domains: Optional[List[str]] = None,
    search_type: str = "neural"
) -> str:
    """
    Perform NBA-specific search using Exa AI with optimized domains and parameters.
    Searches major NBA and basketball websites for the most relevant and current information.
    """
    try:
        exa = get_exa_client()
        
        # Default NBA-focused domains if none provided
        if not include_domains:
            include_domains = [
                "nba.com",
                "espn.com", 
                "basketball-reference.com",
                "bleacherreport.com",
                "cbssports.com",
                "si.com",
                "theringer.com",
                "fivethirtyeight.com",
                "statmuse.com",
                "hoopshype.com"
            ]
        
        # Enhance query with NBA context if not already present
        nba_keywords = ["nba", "basketball", "player", "team", "game", "stats", "season"]
        if not any(keyword in query.lower() for keyword in nba_keywords):
            enhanced_query = f"NBA {query}"
        else:
            enhanced_query = query
        
        # Prepare search parameters
        search_params = {
            "query": enhanced_query,
            "num_results": min(num_results, 20),
            "include_domains": include_domains,
            "use_autoprompt": True
        }
        
        # Add search type specific parameters
        if search_type == "keyword":
            search_params["type"] = "keyword"
        else:
            search_params["type"] = "neural"
        
        # Perform search
        results = exa.search(**search_params)
        
        # Format results with NBA-specific enhancements
        formatted_results = []
        for i, result in enumerate(results.results, 1):
            formatted_result = {
                "rank": i,
                "title": result.title,
                "url": result.url,
                "domain": result.url.split("//")[-1].split("/")[0] if result.url else "unknown",
                "published_date": getattr(result, 'published_date', None),
                "score": getattr(result, 'score', None)
            }
            
            if hasattr(result, 'text') and result.text:
                # Extract key NBA information from text
                text = result.text[:3000] + "..." if len(result.text) > 3000 else result.text
                formatted_result["text"] = text
                
                # Add relevance indicators
                nba_mentions = sum(1 for keyword in nba_keywords if keyword in text.lower())
                formatted_result["nba_relevance_score"] = nba_mentions
            
            formatted_results.append(formatted_result)
        
        # Sort by NBA relevance if available
        if formatted_results and "nba_relevance_score" in formatted_results[0]:
            formatted_results.sort(key=lambda x: x.get("nba_relevance_score", 0), reverse=True)
        
        return {
            "original_query": query,
            "enhanced_query": enhanced_query,
            "search_type": search_type,
            "num_results": len(formatted_results),
            "domains_searched": include_domains,
            "results": formatted_results
        }
        
    except Exception as e:
        return {
            "error": f"Exa NBA search failed: {str(e)}",
            "query": query,
            "results": []
        }


@tool("exa_extract_content", args_schema=ExaContentInput)
def exa_extract_content(
    url: str,
    max_characters: int = 5000
) -> str:
    """
    Extract and clean content from a specific URL using Exa AI.
    Returns structured content with title, text, and metadata.
    """
    try:
        exa = get_exa_client()
        
        # Extract content from URL
        content = exa.get_contents([url])
        
        if not content.results:
            return {
                "error": "No content found for the provided URL",
                "url": url
            }
        
        result = content.results[0]
        
        # Format the extracted content
        formatted_content = {
            "url": url,
            "title": getattr(result, 'title', 'No title available'),
            "text": "",
            "published_date": getattr(result, 'published_date', None),
            "author": getattr(result, 'author', None)
        }
        
        if hasattr(result, 'text') and result.text:
            # Truncate to specified length
            text = result.text[:max_characters]
            if len(result.text) > max_characters:
                text += "... [content truncated]"
            formatted_content["text"] = text
            formatted_content["character_count"] = len(text)
            formatted_content["full_length"] = len(result.text)
        
        return formatted_content
        
    except Exception as e:
        return {
            "error": f"Content extraction failed: {str(e)}",
            "url": url
        }


# Export all tools for tool manager
__all__ = [
    "exa_web_search",
    "exa_nba_search", 
    "exa_extract_content"
]