import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from gpuhunt._internal.models import QueryFilter, RawCatalogItem
from gpuhunt.providers import AbstractProvider

logger = logging.getLogger(__name__)

class LatitudeProvider(AbstractProvider):
    NAME = "latitude"

    def get(
        self, query_filter: Optional[QueryFilter] = None, balance_resources: bool = True
    ) -> list[RawCatalogItem]:
        """
        Fetches and processes pricing data from latitude.sh.

        Returns:
            A list of RawCatalogItem objects representing available offers.
        """
        try:
            pricing_data = self.scrape_latitude_pricing()
            offers = self.process_data(pricing_data)
            return offers
        except requests.exceptions.RequestException as e:
            logger.error("Error during request to latitude.sh: %s", e)
            return []

    def scrape_latitude_pricing(self) -> dict:
        """
        Fetches the pricing data from latitude.sh's API endpoint.

        Returns:
            A dictionary containing pricing information.
        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
        """
        base_url = "https://www.latitude.sh/pricing"
        
        # Fetch the pricing page HTML
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        html_content = response.text

        # Extract the dynamic hash
        hash_value = self._extract_hash(html_content)
        if not hash_value:
            raise ValueError("Unable to find the dynamic hash on the page")

        # Build the JSON URL with the dynamic hash
        url = f"https://www.latitude.sh/_next/data/{hash_value}/en/pricing.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def _extract_hash(self, html_content: str) -> Optional[str]:
        """
        Extracts the dynamic hash from the HTML content.

        Args:
            html_content: The HTML content of the pricing page.

        Returns:
            The dynamic hash string, or None if not found.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if script_tag:
            try:
                data = script_tag.string
                if data:
                    match = re.search(r'"buildId":"([^"]+)"', data)
                    if match:
                        return match.group(1)
            except KeyError:
                return None
        return None

    def process_data(self, pricing_data: dict) -> list[RawCatalogItem]:
        """
        Processes the fetched pricing data into RawCatalogItem objects.

        Args:
            pricing_data: A dictionary containing the scraped data.

        Returns:
            A list of RawCatalogItem objects.
        """
        offers = []
        plans_data = pricing_data.get('pageProps', {}).get('plansData', [])
        for plan in plans_data:
            if 'attributes' not in plan:
                continue
            regions = plan['attributes'].get('regions', [])
            for region in regions:
                item = self.create_raw_catalog_item(plan['attributes'], region)
                if item:
                    offers.append(item)
        return offers
    
    def create_raw_catalog_item(self, plan: dict, region: dict) -> Optional[RawCatalogItem]:
        """
        Creates a RawCatalogItem from a plan's data.

        Args:
            plan: A dictionary representing the plan's data.
            region: The region data dictionary

        Returns:
             A RawCatalogItem object or None if data processing fails.
        """
        try:
            specs = plan.get('specs', {})
            if not specs:
                return None

            cpu_info = specs.get('cpu', {})
            cpu_cores = cpu_info.get('cores', 0) * cpu_info.get('count', 1)
            
            memory_info = specs.get('memory', {})
            memory_gb = memory_info.get('total', 0)
            
            gpu_info = specs.get('gpu', {})
            gpu_count = gpu_info.get('count', 0)
            gpu_name = gpu_info.get('type')
            gpu_memory = None
            if gpu_name:
                # Extract GPU memory from name if present (e.g., "NVIDIA H100 80GB")
                memory_match = re.search(r'(\d+)GB', gpu_name)
                if memory_match:
                    gpu_memory = float(memory_match.group(1))
            
            # Get pricing for USD
            pricing = region.get('pricing', {}).get('USD', {})
            price_per_hour = pricing.get('hour', 0)
            
            # Get location info
            location = region.get('locations', {}).get('available', [])[0] if region.get('locations', {}).get('available') else None
            
            if not location:
                return None

            return RawCatalogItem(
                instance_name=plan.get('name', ''),
                location=location,
                price=price_per_hour,
                cpu=cpu_cores,
                memory=memory_gb,
                gpu_vendor='NVIDIA' if gpu_name and 'NVIDIA' in gpu_name else None,
                gpu_count=gpu_count,
                gpu_name=gpu_name,
                gpu_memory=gpu_memory,
                spot=False,
                disk_size=None,
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Failed to process plan %s in %s: %s", plan.get('name', 'unknown'), region.get('name', 'unknown'), e)
            return None