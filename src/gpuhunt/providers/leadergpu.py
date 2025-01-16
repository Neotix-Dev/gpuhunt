import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from gpuhunt._internal.models import QueryFilter, RawCatalogItem, AcceleratorVendor
from gpuhunt.providers import AbstractProvider

logger = logging.getLogger(__name__)

def parse_memory(memory_str: str) -> float:
    """Parse memory string to get GB value"""
    if not memory_str:
        return 0.0
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:GB|GiB|G)', memory_str)
    return float(match.group(1)) if match else 0.0

def parse_cpu_cores(cpu_str: str) -> int:
    """Parse CPU string to get core count"""
    if not cpu_str:
        return 0
    match = re.search(r'(\d+)\s*(?:cores?|vCPU)', cpu_str, re.IGNORECASE)
    return int(match.group(1)) if match else 0

def parse_gpu_count_and_model(gpu_info: str) -> tuple[int, str]:
    """Parse GPU info to get count and model"""
    if not gpu_info:
        return 0, ""
    
    # Clean up the text
    gpu_info = gpu_info.replace('GPU:', '').strip()
    
    # Try to match patterns like "8 pcs RTX A6000" or "2 pcs H100"
    match = re.search(r'(\d+)\s*pcs\s*(?:NVIDIA\s*)?(?:RTX\s*)?(\w+(?:\s*\d+)?)', gpu_info)
    if match:
        count = int(match.group(1))
        model = match.group(2).strip()
        return count, model
        
    # Try to match other formats
    match = re.search(r'(\d+)x\s*(?:NVIDIA\s*)?(?:RTX\s*)?(\w+(?:\s*\d+)?)', gpu_info)
    if match:
        return int(match.group(1)), match.group(2).strip()
        
    # If no count found, assume 1
    match = re.search(r'(?:NVIDIA\s*)?(?:RTX\s*)?(\w+(?:\s*\d+)?)', gpu_info)
    if match:
        return 1, match.group(1).strip()
        
    return 1, gpu_info.replace('NVIDIA', '').replace('RTX', '').strip()

def parse_price(price_str: str) -> float:
    """Parse price string to get hourly rate in USD"""
    if not price_str:
        return 0.0
    match = re.search(r'(\d+(?:\.\d+)?)', price_str)
    if not match:
        return 0.0
    price = float(match.group(1))
    if 'month' in price_str:
        price = price / (24 * 30)  # Convert monthly to hourly
    elif 'week' in price_str:
        price = price / (24 * 7)   # Convert weekly to hourly
    elif 'day' in price_str:
        price = price / 24         # Convert daily to hourly
    elif 'minute' in price_str:
        price = price * 60         # Convert per-minute to hourly
    return round(price, 4)  # Round to 4 decimal places

class LeaderGPUProvider(AbstractProvider):
    """Provider for LeaderGPU instances"""
    
    NAME = "leadergpu"

    def __init__(self):
        super().__init__()

    def get(
        self, query_filter: Optional[QueryFilter] = None, balance_resources: bool = True
    ) -> list[RawCatalogItem]:
        """Get GPU offerings from LeaderGPU
        
        Args:
            query_filter: Optional filter for the results
            balance_resources: Whether to balance resources based on GPU specs
            
        Returns:
            List of RawCatalogItem objects
        """
        url = "https://www.leadergpu.com/filter_servers"
        
        try:
            # Get JSON response and extract HTML from it
            response = requests.get(url).json()
            logger.debug(f"LeaderGPU API response: {response}")
            html_content = response.get('matchesHtml', '')
            if not html_content:
                logger.error("No HTML content found in LeaderGPU response")
                return []
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            gpu_sections = soup.find_all('section', class_='b-product-gpu')
            offers = []
            
            for section in gpu_sections:
                # Basic info from title
                title_div = section.find('div', class_='b-product-gpu-title')
                if not title_div:
                    continue
                
                # Extract GPU configuration
                config_div = section.find('div', class_='config-list')
                if not config_div:
                    continue
                
                # Get GPU info
                gpu_div = config_div.find('div', recursive=False)
                if not gpu_div:
                    continue
                    
                gpu_text = gpu_div.get_text(strip=True)
                gpu_count, gpu_model = parse_gpu_count_and_model(gpu_text)
                
                # Get GPU RAM
                gpu_ram = None
                cpu_info = None
                ram_info = None
                nvme_info = None
                
                for div in config_div.find_all('div', recursive=False):
                    text = div.get_text(strip=True)
                    if 'GPU RAM:' in text:
                        gpu_ram = div.find('span').get_text(strip=True) if div.find('span') else None
                    elif 'CPU:' in text:
                        cpu_info = div.find('span').get_text(strip=True) if div.find('span') else None
                    elif 'RAM:' in text:
                        ram_info = div.find('span').get_text(strip=True) if div.find('span') else None
                    elif 'NVME:' in text:
                        nvme_info = div.find('span').get_text(strip=True) if div.find('span') else None
                
                # Get price
                prices_div = section.find('div', class_='b-product-gpu-prices')
                hourly_price = 0.0
                if prices_div:
                    for li in prices_div.find_all('li', class_='d-flex'):
                        price_text = li.find('p', class_='text-bold').get_text(strip=True) if li.find('p', class_='text-bold') else None
                        if price_text:
                            price = parse_price(price_text)
                            if price > 0:
                                hourly_price = price
                                break
                
                # Create catalog item
                offer = RawCatalogItem(
                    instance_name=f"{gpu_model}-{gpu_count}x",
                    location="EU",  # LeaderGPU is based in Europe
                    price=hourly_price,
                    cpu=parse_cpu_cores(cpu_info) if cpu_info else 0,
                    memory=parse_memory(ram_info) if ram_info else 0,
                    gpu_vendor=AcceleratorVendor.NVIDIA,  # LeaderGPU only offers NVIDIA
                    gpu_count=gpu_count,
                    gpu_name=gpu_model,
                    gpu_memory=parse_memory(gpu_ram) if gpu_ram else 0,
                    spot=False,
                    disk_size=parse_memory(nvme_info) if nvme_info else 0
                )
                offers.append(offer)
            
            logger.info(f"Found {len(offers)} GPU instances from LeaderGPU")
            return offers
            
        except Exception as e:
            logger.error(f"Error scraping LeaderGPU: {str(e)}")
            return []
