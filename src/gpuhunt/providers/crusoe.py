import logging
from typing import List, Optional

from gpuhunt._internal.models import QueryFilter, RawCatalogItem
from gpuhunt.providers.scraper import ScraperProvider

logger = logging.getLogger(__name__)

class CrusoeProvider(ScraperProvider):
    """Provider for Crusoe Cloud GPU instances using web scraping"""
    
    NAME = "crusoe"

    def __init__(self):
        super().__init__()

    @property
    def urls(self) -> List[str]:
        return ["https://crusoe.ai/cloud/"]

    @property
    def prompt(self) -> str:
        return """
        Extract all GPU instances from the Crusoe Cloud pricing page. For each GPU instance, provide:
        1. GPU model name (e.g. H100, A100) - remove any vendor prefix
        2. GPU memory in GB (as a number)
        3. Number of GPUs per instance (as a number)
        4. Price per hour in USD (as a number)
        5. Location (set to "US" as all instances are in US)
        6. Number of CPU cores (as a number)
        7. System RAM in GB (as a number)
        8. Disk size in GB if available (as a number)

        Important:
        - Return ALL GPU instances you find
        - All numeric values should be numbers, not strings
        - Look for pricing information in USD per hour
        - The vendor is always "NVIDIA"
        - If memory/CPU/RAM information is not provided, set to 0
        
        Return the data in this format:
        {
          "gpus": [
            {
              "name": "H100",
              "memory": 80,
              "count": 8,
              "price": 25.00,
              "location": "US",
              "cpu": 0,
              "ram": 0,
              "disk": 0,
              "spot": false,
              "vendor": "NVIDIA"
            },
            ... additional GPUs ...
          ]
        }
        """
