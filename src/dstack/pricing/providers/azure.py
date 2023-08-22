import os
import re
import json
from typing import Tuple, Optional
from collections import namedtuple

from azure.core.credentials import TokenCredential
from azure.mgmt.compute import ComputeManagementClient

from dstack.pricing.models import InstanceOffer
from dstack.pricing.providers import AbstractProvider


prices_url = "https://prices.azure.com/api/retail/prices"
prices_version = "2023-01-01-preview"
prices_filters = [
    "serviceName eq 'Virtual Machines'",
    "priceType eq 'Consumption'",
    "contains(productName, 'Windows') eq false",
    "contains(productName, 'Dedicated') eq false",
    "contains(meterName, 'Low Priority') eq false",  # retires in 2025
]
VMSeries = namedtuple("VMSeries", ["pattern", "gpu_name", "gpu_memory"])
gpu_vm_series = [
    VMSeries(r"NC(\d+)ads_A100_v4", "A100", 80.0),  # NC A100 v4-series [A100 80GB]
    VMSeries(r"NC(\d+)ads_A10_v4", "A10", None),  # NC A10 v4-series [A10]  # todo, retired?
    VMSeries(r"NC(\d+)as_T4_v3", "T4", 16.0),  # NCasT4_v3-series [T4]
    VMSeries(r"NC(\d+)r?(?:_Promo)?", "K80", None),  # NC-series [K80]  # todo, retired in Sep. 2023
    VMSeries(r"NC(\d+)r?s_v2", "P100", None),  # NCv2-series [P100]  # todo, retired in Sep. 2023
    VMSeries(r"NC(\d+)r?s_v3", "V100", 16.0),  # NCv3-series [V100 16GB]
    VMSeries(r"ND(\d+)amsr_A100_v4", "A100", 80.0),  # NDm A100 v4-series [8xA100 80GB]
    VMSeries(r"ND(\d+)asr_v4", "A100", 40.0),  # ND A100 v4-series [8xA100 40GB]
    VMSeries(r"ND(\d+)rs_v2", "V100", 32.0),  # NDv2-series [8xV100 32GB]
    VMSeries(r"ND(\d+)r?s", "P40", None),  # ND-series [P40]  # todo
    VMSeries(r"NG(\d+)adm?s_V620_v1", "V620", None),  # NGads V620-series [V620]  # todo
    VMSeries(r"NV(\d+)", "M60", None),  # NV-series [M60]  # todo
    VMSeries(r"NV(\d+)adm?s_A10_v5", "A10", None),  # NVadsA10 v5-series [A10]  # todo
    VMSeries(r"NV(\d+)as_v4", "MI25", None),  # NVv4-series [MI25]  # todo
    VMSeries(r"NV(\d+)s_v3", "M60", None),  # NVv3-series [M60]  # todo
]
# todo filter retired series: https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-previous-gen


class AzureProvider(AbstractProvider):
    def __init__(self, cache_dir: str, credential: TokenCredential, subscription_id: str):
        self.cache_dir = cache_dir
        self.client = ComputeManagementClient(credential=credential, subscription_id=subscription_id)

    def get_page(self, page: int) -> dict:
        with open(os.path.join(self.cache_dir, f"{page:04}.json")) as f:
            return json.load(f)

    def get(self) -> list[InstanceOffer]:
        page = 0
        offers = []
        while True:
            data = self.get_page(page)
            for item in data["Items"]:
                offer = InstanceOffer(
                    instance_name=item["armSkuName"],
                    location=item["armRegionName"],
                    price=item["retailPrice"],
                    spot="Spot" in item["meterName"],
                )
                offers.append(offer)
            if not data["NextPageLink"]:
                break
            page += 1
        return offers

    def fill_details(self, offers: list[InstanceOffer]) -> list[InstanceOffer]:
        details = {}
        resources = self.client.resource_skus.list()
        for resource in resources:
            if resource.resource_type != "virtualMachines":
                continue
            capabilities = {pair.name: pair.value for pair in resource.capabilities}
            gpu_count, gpu_name, gpu_memory = 0, None, None
            if "GPUs" in capabilities:
                gpu_count = int(capabilities["GPUs"])
                gpu_name, gpu_memory = get_gpu_name_memory(resource.name)
            details[resource.name] = InstanceOffer(
                instance_name=resource.name,
                location="-",
                cpu=capabilities["vCPUs"],
                memory=float(capabilities["MemoryGB"]),
                gpu_count=gpu_count,
                gpu_name=gpu_name,
                gpu_memory=gpu_memory,
            )
        output = []
        for offer in offers:
            if (resources := details.get(offer.instance_name)) is None:
                print(offer.instance_name)
                continue
            offer.cpu = resources.cpu
            offer.memory = resources.memory
            offer.gpu_count = resources.gpu_count
            offer.gpu_name = resources.gpu_name
            offer.gpu_memory = resources.gpu_memory
            output.append(offer)
        return output


def get_gpu_name_memory(vm_name: str) -> Tuple[Optional[str], Optional[float]]:
    for pattern, gpu_name, gpu_memory in gpu_vm_series:
        m = re.match(f"^Standard_{pattern}$", vm_name)
        if m is None:
            continue
        return gpu_name, gpu_memory
    print(vm_name)
    return None, None
