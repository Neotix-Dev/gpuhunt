import logging
from typing import List, Optional

from gpuhunt._internal.models import QueryFilter, RawCatalogItem
from gpuhunt.providers.scraper import ScraperProvider

logger = logging.getLogger(__name__)

class GenesisCloudProvider(ScraperProvider):
    """Provider for Genesis Cloud GPU instances using web scraping"""
    
    NAME = "genesiscloud"

    def __init__(self):
        super().__init__()

    @property
    def urls(self) -> List[str]:
        return ["https://www.genesiscloud.com/pricing"]

    @property
    def prompt(self) -> str:
        return """
        Extract all GPU instances from the Genesis Cloud pricing page. For each GPU instance, provide:
        1. GPU model name (e.g. RTX 4090, RTX 3090, A100) - remove any vendor prefix
        2. GPU memory in GB (as a number)
        3. Number of GPUs per instance (as a number)
        4. Price per hour in USD (as a number)
        5. Location (use the region specified, default to "EU" if not specified)
        6. Number of CPU cores (as a number)
        7. System RAM in GB (as a number)
        8. Disk size in GB if available (as a number)

        Important:
        - Return ALL GPU instances you find
        - All numeric values should be numbers, not strings
        - Look for both On-Demand and Spot prices (create separate entries with spot=true for spot instances)
        - The vendor is always "NVIDIA"
        - Pay attention to both vCPU and RAM specifications
        - Look for SSD/NVMe storage sizes
        - Make sure to include both RTX and Data Center GPUs
        - Prices should already be in USD per hour
        - For any missing numeric values, use: memory=0, count=1, price=0, cpu=0, ram=0
        - Do not return instances where ALL specifications are missing
        - If only some specifications are available, return those and use defaults for missing ones
        
        Return the data in this format:
        {
          "gpus": [
            {
              "name": "4090",
              "memory": 24,
              "count": 1,
              "price": 0.99,
              "location": "EU",
              "cpu": 8,
              "ram": 32,
              "disk": 100,
              "spot": false,
              "vendor": "NVIDIA"
            },
            ... additional GPUs ...
          ]
        }
        """
