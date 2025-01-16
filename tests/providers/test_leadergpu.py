import os
import pytest
import responses
import json

from gpuhunt._internal.models import AcceleratorVendor
from gpuhunt.providers.leadergpu import LeaderGPUProvider, parse_memory, parse_cpu_cores, parse_gpu_count_and_model, parse_price

def test_parse_memory():
    assert parse_memory("16GB") == 16.0
    assert parse_memory("32 GB") == 32.0
    assert parse_memory("64GiB") == 64.0
    assert parse_memory("128 G") == 128.0
    assert parse_memory("invalid") == 0.0
    assert parse_memory(None) == 0.0

def test_parse_cpu_cores():
    assert parse_cpu_cores("32 cores") == 32
    assert parse_cpu_cores("64 vCPU") == 64
    assert parse_cpu_cores("16 Core") == 16
    assert parse_cpu_cores("invalid") == 0
    assert parse_cpu_cores(None) == 0

def test_parse_gpu_count_and_model():
    assert parse_gpu_count_and_model("4x NVIDIA RTX 4090") == (4, "RTX 4090")
    assert parse_gpu_count_and_model("8x A100") == (8, "A100")
    assert parse_gpu_count_and_model("NVIDIA H100") == (1, "H100")
    assert parse_gpu_count_and_model(None) == (0, "")

def test_parse_price():
    assert parse_price("€1200/month") == pytest.approx(1200 / (24 * 30))
    assert parse_price("€300/week") == pytest.approx(300 / (24 * 7))
    assert parse_price("€50/day") == pytest.approx(50 / 24)
    assert parse_price("€0.02/minute") == pytest.approx(0.02 * 60)
    assert parse_price("invalid") == 0.0
    assert parse_price(None) == 0.0

@pytest.fixture
def provider():
    return LeaderGPUProvider()

@responses.activate
def test_scrape_leadergpu(provider):
    # Mock JSON response from LeaderGPU
    mock_response = {
        "matchesHtml": """
        <section class="b-product-gpu">
            <div class="b-product-gpu-title">
                <a href="/server_configurations/123">4x RTX 4090 Server</a>
            </div>
            <div class="config-list">
                <div>GPU: <p>4x NVIDIA RTX 4090</p></div>
                <div>GPU RAM: <span>24 GB</span></div>
                <div>CPU: <span>32 cores</span></div>
                <div>RAM: <span>256 GB</span></div>
                <div>NVME: <span>2 TB</span></div>
            </div>
            <div class="b-product-gpu-prices">
                <li class="d-flex"><p>€1200/month</p></li>
                <li class="d-flex"><p>€300/week</p></li>
            </div>
        </section>
        <section class="b-product-gpu">
            <div class="b-product-gpu-title">
                <a href="/server_configurations/456">8x A100 Server</a>
            </div>
            <div class="config-list">
                <div>GPU: <p>8x NVIDIA A100</p></div>
                <div>GPU RAM: <span>80 GB</span></div>
                <div>CPU: <span>64 cores</span></div>
                <div>RAM: <span>512 GB</span></div>
                <div>NVME: <span>4 TB</span></div>
            </div>
            <div class="b-product-gpu-prices">
                <li class="d-flex"><p>€4800/month</p></li>
            </div>
        </section>
        """
    }
    
    responses.add(
        responses.GET,
        "https://www.leadergpu.com/filter_servers?filterExpression=os%3Awindows_server%3Bavailable_server%3Bavailable_server_next3d%3Bmonth%3A1",
        json=mock_response,
        status=200,
    )

    offers = provider.get()
    assert len(offers) == 2

    # Check 4x RTX 4090 instance
    rtx_4090 = next(o for o in offers if o.instance_name == "RTX 4090-4x")
    assert rtx_4090.location == "EU"
    assert rtx_4090.price == pytest.approx(1200 / (24 * 30))  # Convert monthly to hourly
    assert rtx_4090.cpu == 32
    assert rtx_4090.memory == 256
    assert rtx_4090.gpu_vendor == AcceleratorVendor.NVIDIA
    assert rtx_4090.gpu_count == 4
    assert rtx_4090.gpu_name == "RTX 4090"
    assert rtx_4090.gpu_memory == 24
    assert rtx_4090.disk_size == 2048  # 2TB in GB

    # Check 8x A100 instance
    a100 = next(o for o in offers if o.instance_name == "A100-8x")
    assert a100.location == "EU"
    assert a100.price == pytest.approx(4800 / (24 * 30))  # Convert monthly to hourly
    assert a100.cpu == 64
    assert a100.memory == 512
    assert a100.gpu_vendor == AcceleratorVendor.NVIDIA
    assert a100.gpu_count == 8
    assert a100.gpu_name == "A100"
    assert a100.gpu_memory == 80
    assert a100.disk_size == 4096  # 4TB in GB

@responses.activate
def test_scrape_error(provider):
    # Mock failed response
    responses.add(
        responses.GET,
        "https://www.leadergpu.com/filter_servers?filterExpression=os%3Awindows_server%3Bavailable_server%3Bavailable_server_next3d%3Bmonth%3A1",
        status=500,
    )

    offers = provider.get()
    assert len(offers) == 0  # Should return empty list on error
