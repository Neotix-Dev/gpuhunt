import os
import pytest
import responses

from gpuhunt._internal.models import AcceleratorVendor
from gpuhunt.providers.scaleway import ScalewayProvider

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

@pytest.fixture
def provider(mock_env):
    return ScalewayProvider()

@responses.activate
def test_scrape_scaleway(provider):
    # Mock response for Scaleway pricing page
    responses.add(
        responses.GET,
        "https://www.scaleway.com/en/pricing/gpu/",
        body="""
        <html>
            <body>
                <div class="pricing-table">
                    <div class="gpu-instances">
                        <h2>GPU Instances</h2>
                        <div class="instance">
                            <h3>RENDER-S</h3>
                            <ul>
                                <li>NVIDIA RTX A4000 GPU</li>
                                <li>8 CPU cores</li>
                                <li>32 GB RAM</li>
                                <li>256 GB SSD</li>
                                <li>€1.36/hour</li>
                            </ul>
                        </div>
                        <div class="instance">
                            <h3>GPU-5000-S</h3>
                            <ul>
                                <li>NVIDIA A5000 GPU</li>
                                <li>12 CPU cores</li>
                                <li>64 GB RAM</li>
                                <li>512 GB SSD</li>
                                <li>€2.27/hour</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """,
        status=200,
    )

    offers = provider.get()
    assert len(offers) == 2

    # Check RENDER-S instance
    render_s = next(o for o in offers if o.instance_name == "A4000-1x")
    assert render_s.location in ["Paris", "Amsterdam"]
    assert render_s.price == pytest.approx(1.50)  # €1.36 * 1.10
    assert render_s.cpu == 8
    assert render_s.memory == 32
    assert render_s.gpu_vendor == AcceleratorVendor.NVIDIA
    assert render_s.gpu_count == 1
    assert render_s.gpu_name == "A4000"
    assert render_s.gpu_memory == 16
    assert render_s.disk_size == 256

    # Check GPU-5000-S instance
    gpu_5000 = next(o for o in offers if o.instance_name == "A5000-1x")
    assert gpu_5000.location in ["Paris", "Amsterdam"]
    assert gpu_5000.price == pytest.approx(2.50)  # €2.27 * 1.10
    assert gpu_5000.cpu == 12
    assert gpu_5000.memory == 64
    assert gpu_5000.gpu_vendor == AcceleratorVendor.NVIDIA
    assert gpu_5000.gpu_count == 1
    assert gpu_5000.gpu_name == "A5000"
    assert gpu_5000.gpu_memory == 24
    assert gpu_5000.disk_size == 512

@responses.activate
def test_scrape_error(provider):
    # Mock failed response
    responses.add(
        responses.GET,
        "https://www.scaleway.com/en/pricing/gpu/",
        status=500,
    )

    offers = provider.get()
    assert len(offers) == 0  # Should return empty list on error

def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable must be set"):
        ScalewayProvider()
