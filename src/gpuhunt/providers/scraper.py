from cmd import PROMPT
import logging
import os
from typing import Optional, Dict, Any, List
import json
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass
import openai
from openai import OpenAI
from pydantic import BaseModel, Field
from gpuhunt._internal.models import QueryFilter, RawCatalogItem, AcceleratorVendor
from gpuhunt.providers import AbstractProvider

logger = logging.getLogger(__name__)

@dataclass
class GPUInfo:
    """Information about a GPU offering from a provider"""
    name: str
    memory: float
    count: int
    price: float
    location: str
    cpu: int
    ram: float
    disk: Optional[float] = None
    spot: bool = False
    vendor: AcceleratorVendor = AcceleratorVendor.NVIDIA

class GPUSchema(BaseModel):
    """Schema for GPU information extraction"""
    name: str = Field(description="Name of the GPU, name can only be the model of the GPU, without the name of the manufacturer, ie: Nvidia H100->H100; AMD MIX3000 -> MIX3000 ")
    memory: float = Field(description="Memory of the GPU in GB")
    count: int = Field(description="Number of GPUs")
    price: float = Field(description="Price per hour in USD.")
    location: str = Field(description="Location/region of the GPU")
    cpu: int = Field(description="Number of CPU cores")
    ram: float = Field(description="Amount of RAM in GB")
    disk: Optional[float] = Field(None, description="Disk size in GB")

class WebScraper:
    """Base scraper that uses requests and OpenAI to extract GPU information"""

    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the scraper
        
        Args:
            openai_api_key: OpenAI API key. If not provided, will try to get from OPENAI_API_KEY env var
        """
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        
        self.client = OpenAI(api_key=self.api_key)
        # Cache for scraped results
        self._cache: Dict[str, list[Dict[str, Any]]] = {}

    def scrape_url(self, url: str, prompt: str) -> List[GPUInfo]:
        """Scrape GPU information from a URL
        
        Args:
            url: URL to scrape
            prompt: Custom prompt for the scraper
            
        Returns:
            List of GPUInfo objects containing GPU information
        """
        if url in self._cache:
            raw_results = self._cache[url]
        else:
            try:
                # Get the webpage content
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                content = response.text

                # Use OpenAI to extract structured data
                messages = [
                    {"role": "system", "content": "You are a helpful assistant that extracts GPU information from webpages."},
                    {"role": "user", "content": f"Here is the webpage content:\n\n{content}\n\n{prompt}"}
                ]
                
                completion = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(completion.choices[0].message.content)
                logger.info(f"Raw OpenAI result: {result}")
                
                # Expect result to be a list of GPU instances
                raw_results = result.get('gpus', [])
                if not isinstance(raw_results, list):
                    raw_results = [raw_results]
                
                # Cache the results
                self._cache[url] = raw_results

            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                return []

        # Convert raw results to GPUInfo objects
        logger.info(f"Scraped {len(raw_results)} GPUs from {url}")
        return [
            GPUInfo(
                name=result["name"],
                memory=float(result["memory"]),
                count=int(result["count"]),
                price=float(result["price"]),
                location=result["location"],
                cpu=int(result["cpu"]),
                ram=float(result["ram"]),
                disk=float(result["disk"]) if result.get("disk") else None,
                spot=bool(result.get("spot", False)),
                vendor=AcceleratorVendor.AMD if result.get("vendor", "").upper() == "AMD" else AcceleratorVendor.NVIDIA
            )
            for result in raw_results
        ]

class ScraperProvider(AbstractProvider, ABC):
    """Base class for providers that use web scraping"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the scraper provider
        
        Args:
            openai_api_key: OpenAI API key. If not provided, will try to get from OPENAI_API_KEY env var
        """
        self.scraper = WebScraper(openai_api_key)

    @property
    @abstractmethod
    def urls(self) -> List[str]:
        """URLs to scrape"""
        pass

    @property
    @abstractmethod
    def prompt(self) -> str:
        """Custom prompt for the scraper"""
        pass

    def get(
        self, query_filter: Optional[QueryFilter] = None, balance_resources: bool = True
    ) -> list[RawCatalogItem]:
        """Get GPU offerings from all configured URLs
        
        Args:
            query_filter: Optional filter for the results
            balance_resources: Whether to balance resources based on GPU specs
            
        Returns:
            List of RawCatalogItem objects
        """
        all_gpus = []
        for url in self.urls:
            gpus = self.scraper.scrape_url(url, self.prompt)
            all_gpus.extend(gpus)

        # Convert GPUInfo objects to RawCatalogItem objects
        offers = []
        for gpu in all_gpus:
            offer = RawCatalogItem(
                instance_name=f"{gpu.name}-{gpu.count}x",
                location=gpu.location,
                price=gpu.price,
                cpu=gpu.cpu,
                memory=gpu.ram,
                gpu_vendor=gpu.vendor,
                gpu_count=gpu.count,
                gpu_name=gpu.name,
                gpu_memory=gpu.memory,
                spot=gpu.spot,
                disk_size=gpu.disk,
            )
            offers.append(offer)

        return sorted(offers, key=lambda i: i.price)
