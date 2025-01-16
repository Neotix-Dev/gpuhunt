import logging
from typing import List, Optional

from gpuhunt._internal.models import QueryFilter, RawCatalogItem
from gpuhunt.providers.scraper import ScraperProvider

logger = logging.getLogger(__name__)

class SeewebProvider(ScraperProvider):
    """Provider for Seeweb GPU instances using web scraping"""
    
    NAME = "seeweb"

    def __init__(self):
        super().__init__()

    @property
    def urls(self) -> List[str]:
        return ["https://www.seeweb.it/en/products/cloud-server-gpu"]

    @property
    def prompt(self) -> str:
        return """
        Extract all GPU instances from the Seeweb GPU Cloud Server pricing page. For each GPU instance, provide:
        1. GPU model name (e.g. A4000, A5000, A6000) - remove any vendor prefix
        2. GPU memory in GB (as a number)
        3. Number of GPUs per instance (as a number)
        4. Price per hour in USD (convert from EUR using 1 EUR = 1.10 USD, return as a number)
        5. Location (set to "Italy" as all instances are in Italy)
        6. Number of CPU cores (as a number)
        7. System RAM in GB (as a number)
        8. Disk size in GB if available (as a number)

        Important:
        - Return ALL GPU instances you find
        - All numeric values should be numbers, not strings
        - Convert monthly prices to hourly by dividing by (24 * 30)
        - Convert EUR to USD by multiplying by 1.10
        - The vendor is always "NVIDIA"
        - Pay attention to both vCPU and RAM specifications
        - Look for SSD/NVMe storage sizes
        
        Return the data in this format:
        {
          "gpus": [
            {
              "name": "A4000",
              "memory": 16,
              "count": 1,
              "price": 1.50,
              "location": "Italy",
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
