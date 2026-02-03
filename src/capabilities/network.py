"""Network capabilities.

Provides HTTP/HTTPS request functionality.
"""

from typing import Any
import httpx

from src.models.capability import CapabilityDescriptor, CapabilityResult, CapabilityStatus
from .base import Capability


class NetworkFetchCapability(Capability):
    """Make HTTP requests."""
    
    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        timeout: float = 30.0
    ):
        """Initialize network capability.
        
        Args:
            allowed_domains: If provided, only these domains are accessible.
                           If None, all domains are allowed.
            timeout: Request timeout in seconds.
        """
        self._allowed_domains = allowed_domains
        self._timeout = timeout
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        restrictions = []
        if self._allowed_domains:
            restrictions.append(f"Limited to domains: {', '.join(self._allowed_domains)}")
        restrictions.append(f"Timeout: {self._timeout}s")
        
        return CapabilityDescriptor(
            name="net.fetch",
            description="Make an HTTP request",
            status=CapabilityStatus.AVAILABLE,
            parameters={
                "url": "str - URL to fetch",
                "method": "str - HTTP method (default: GET)",
                "headers": "dict - Optional headers",
                "body": "str - Optional request body",
            },
            returns="dict - {status_code, headers, body}",
            restrictions=restrictions
        )
    
    def _is_domain_allowed(self, url: str) -> bool:
        """Check if a URL's domain is allowed."""
        if self._allowed_domains is None:
            return True
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        return any(
            domain == allowed or domain.endswith(f".{allowed}")
            for allowed in self._allowed_domains
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        url = kwargs.get("url")
        if not url:
            return CapabilityResult.fail("Missing required parameter: url")
        
        method = kwargs.get("method", "GET").upper()
        headers = kwargs.get("headers", {})
        body = kwargs.get("body")
        
        if not self._is_domain_allowed(url):
            return CapabilityResult.fail(f"Domain not allowed: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body
                )
                
                return CapabilityResult.ok({
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text
                })
                
        except httpx.TimeoutException:
            return CapabilityResult.fail(f"Request timed out after {self._timeout}s")
        except httpx.RequestError as e:
            return CapabilityResult.fail(f"Request error: {e}")
        except Exception as e:
            return CapabilityResult.fail(f"Network error: {e}")
