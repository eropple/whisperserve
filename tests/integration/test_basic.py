import os
import pytest
from pprint import pprint

import whisperserve_client
from whisperserve_client.api.health_api import HealthApi
from whisperserve_client.api_client import ApiClient
from whisperserve_client.configuration import Configuration


@pytest.fixture
def api_client():
    """Create a configured API client using environment variables."""
    # Get connection details from environment
    host = os.environ.get("SERVER__HOST", "0.0.0.0")
    # Use localhost instead of 0.0.0.0 for client connections
    if host == "0.0.0.0":
        host = "localhost"
    
    port = os.environ.get("SERVER__PORT", "8000")
    
    # Create API configuration
    config = Configuration(
        host=f"http://{host}:{port}"
    )
    
    # Create API client
    with ApiClient(config) as client:
        yield client


@pytest.fixture
def health_api(api_client):
    """Create a health API client."""
    return HealthApi(api_client)


def test_health_check(health_api):
    """Test that the API health endpoint returns OK status."""
    # Call the health endpoint
    response = health_api.health_check_health_get()
    
    # Print the response for debugging
    print("\nHealth check response:")
    pprint(response)
    
    # Verify the response contains expected fields
    assert "status" in response, "Response should contain 'status' field"
    assert response["status"] == "ok", "Status should be 'ok'"
    assert "version" in response, "Response should contain 'version' field"
    assert "service" in response, "Response should contain 'service' field"
    assert response["service"] == "whisperserve", "Service name should be 'whisperserve'"
