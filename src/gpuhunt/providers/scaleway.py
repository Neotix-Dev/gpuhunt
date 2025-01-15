import logging
from typing import List, Optional

from gpuhunt._internal.models import QueryFilter, RawCatalogItem
from gpuhunt.providers.scraper import ScraperProvider

logger = logging.getLogger(__name__)

class ScalewayProvider(ScraperProvider):
    """Provider for Scaleway GPU instances using web scraping"""
    
    NAME = "scaleway"

    def __init__(self):
        super().__init__()

    @property
    def urls(self) -> List[str]:
        return ["https://www.scaleway.com/en/pricing/gpu/"]

    @property
    def prompt(self) -> str:
        return """
        Extract all GPU instances from the Scaleway pricing page. For each GPU instance, provide:
        1. GPU model name (e.g. A4000, A5000, H100) - remove any vendor prefix
        2. GPU memory in GB (as a number)
        3. Number of GPUs per instance (as a number)
        4. Price per hour in USD (convert from EUR using 1 EUR = 1.10 USD, return as a number)
        5. Location (either Paris or Amsterdam)
        6. Number of CPU cores (as a number)
        7. System RAM in GB (as a number)
        8. Disk size in GB if available (as a number)

        Important:
        - Return ALL GPU instances you find
        - If a GPU name has a format like "L40s-1-48G", convert it to just "L40"
        - All numeric values should be numbers, not strings
        - Prices should be in USD (multiply EUR by 1.10)
        - The vendor is always "NVIDIA" unless explicitly stated as AMD
        
        Return the data in this format:
        {
          "gpus": [
            {
              "name": "A4000",
              "memory": 16,
              "count": 1,
              "price": 1.50,
              "location": "Paris",
              "cpu": 8,
              "ram": 32,
              "disk": 256,
              "spot": false,
              "vendor": "NVIDIA"
            },
            ... additional GPUs ...
          ]
        }
        """
