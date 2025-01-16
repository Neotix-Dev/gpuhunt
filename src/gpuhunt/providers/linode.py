import logging
import json
import requests
from typing import List, Optional

from gpuhunt._internal.models import QueryFilter, RawCatalogItem
from gpuhunt.providers.scraper import ScraperProvider

logger = logging.getLogger(__name__)

class LinodeProvider(ScraperProvider):
    """Provider for Linode (Akamai Cloud) GPU instances using their API"""
    
    NAME = "linode"

    def __init__(self):
        super().__init__()

    @property
    def urls(self) -> List[str]:
        return ["https://api.linode.com/v4/linode/types"]

    def _get_pricing_data(self) -> str:
        """Get pricing data from Linode API"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        }
        response = requests.get(self.urls[0], headers=headers, timeout=30)
        response.raise_for_status()
        return json.dumps(response.json())

    @property
    def prompt(self) -> str:
        return """
        Extract all GPU instances from the Linode API response. The data is in JSON format where GPU instances have "class": "gpu". For each GPU instance, provide:
        1. GPU model name (e.g. A100, A40) - remove any vendor prefix
        2. GPU memory in GB (as a number) - this is usually in the "label" field
        3. Number of GPUs per instance (as a number) - look for GPU count in description
        4. Price per hour in USD (as a number) - use the "price.hourly" field
        5. Location (set to "US" as instances are available in multiple regions)
        6. Number of CPU cores (as a number) - use "vcpus" field
        7. System RAM in GB (as a number) - use "memory" field divided by 1024 to convert from MB to GB
        8. Disk size in GB if available (as a number) - use "disk" field

        Important:
        - Only return instances where "class" is "gpu"
        - All numeric values should be numbers, not strings
        - The vendor is always "NVIDIA"
        - Memory is in MB in the API, convert to GB by dividing by 1024
        - For any missing numeric values, use: memory=0, count=1, price=0, cpu=0, ram=0
        - Do not return instances where ALL specifications are missing
        - If only some specifications are available, return those and use defaults for missing ones
        
        Return the data in this format:
        {
          "gpus": [
            {
              "name": "A100",
              "memory": 80,
              "count": 1,
              "price": 3.99,
              "location": "US",
              "cpu": 8,
              "ram": 64,
              "disk": 100,
              "spot": false,
              "vendor": "NVIDIA"
            },
            ... additional GPUs ...
          ]
        }
        """

    def get(
        self, query_filter: Optional[QueryFilter] = None, balance_resources: bool = True
    ) -> list[RawCatalogItem]:
        """Override get method to use API data instead of webpage content"""
        try:
            content = self._get_pricing_data()
            gpus = self.scraper.scrape_url(self.urls[0], self.prompt, override_content=content)
        except Exception as e:
            logger.error(f"Error getting Linode pricing data: {str(e)}")
            return []

        # Convert GPUInfo objects to RawCatalogItem objects
        offers = []
        for gpu in gpus:
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
