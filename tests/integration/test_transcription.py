import os
import time
import pytest
from jose import jwt
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from whisperserve_client.api.jobs_api import JobsApi
from whisperserve_client.api_client import ApiClient
from whisperserve_client.configuration import Configuration
from whisperserve_client.models.create_job_request import CreateJobRequest
from whisperserve_client.models.job_state import JobState


def generate_jwt(tenant_id):
    """Generate a valid JWT token for testing."""
    import json
    
    # Get the signing key from environment
    jwk_string = os.environ.get("TEST__SIGNING_JWK")
    signing_jwk = json.loads(jwk_string)
    
    # Get the expected audience from environment
    audience = os.environ.get("TEST__JWT_AUDIENCE", "whisperserve")
    
    # Prepare token claims
    now = datetime.utcnow()
    expiration = now + timedelta(hours=1)
    
    # Create the payload with the correct audience
    payload = {
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
        "tenant_id": tenant_id,
        "sub": f"test-user-{tenant_id}",
        "iss": "whisperserve-test",
        "aud": audience  # Include the proper audience claim
    }

    print(f"JWT payload: {payload}")
    
    # Create headers with key ID
    headers = {"kid": signing_jwk["kid"]}
    
    # Generate token using the signing key
    token = jwt.encode(
        payload, 
        signing_jwk,
        algorithm="ES256",
        headers=headers
    )
    
    return token

@pytest.fixture
def api_client():
    """Create a configured API client for API requests."""
    # Get connection details
    host = os.environ.get("SERVER__HOST", "0.0.0.0")
    if host == "0.0.0.0":
        host = "localhost"
    port = os.environ.get("SERVER__PORT", "8000")
    
    api_host = f"http://{host}:{port}"

    # Create configuration
    config = Configuration(host=api_host)

    print(f"API host: {api_host}")
    
    # Generate test token
    test_tenant_id = "test-tenant-123"
    token = generate_jwt(test_tenant_id)
    
    # Create client
    with ApiClient(config) as client:
        # Directly set the Authorization header
        client.set_default_header("Authorization", f"Bearer {token}")
        
        # Verify header is set
        default_headers = client.default_headers
        print(f"Authorization header: {default_headers.get('Authorization')}")
        
        yield client




@pytest.fixture
def jobs_api(api_client):
    """Create a jobs API client."""
    return JobsApi(api_client)


@pytest.fixture
def testdata_url():
    """Get the base URL for the test data server."""
    host = "localhost"
    port = os.environ.get("TEST__TESTDATA_PORT", "8090")
    return f"http://{host}:{port}/"


def test_mp3_transcription(jobs_api, testdata_url):
    """
    Test end-to-end transcription of an MP3 file.
    
    1. Upload MP3 via jobs API
    2. Poll for completion
    3. Verify results against expected JSON
    4. Verify tenant isolation - another tenant cannot access the job
    """
    # Construct MP3 URL from test data server
    mp3_file = "eisenhower-farewell_address-short-64kbps.mp3"
    mp3_url = urljoin(testdata_url, mp3_file)
    
    # Construct expected results file path
    expected_json_file = "eisenhower-farewell_address-short-64kbps-cpu.base.json"
    expected_json_url = urljoin(testdata_url, expected_json_file)
    
    print(f"\nSubmitting job with MP3: {mp3_url}")
    
    # Create job request
    job_request = CreateJobRequest(
        media_url=mp3_url,
        processing_mode="downmix"
    )
    
    # Submit job
    job_response = jobs_api.create_job_jobs_post(job_request)
    job_id = job_response.id
    
    print(f"Job created with ID: {job_id}")
    
    # Poll for completion with timeout
    max_wait_minutes = 15
    poll_interval_seconds = 10
    timeout = time.time() + (max_wait_minutes * 60)
    
    # Define terminal states
    terminal_states = [JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELED]
    
    # Poll until completion or timeout
    current_state = None
    while time.time() < timeout:
        job = jobs_api.get_job_jobs_job_id_get(job_id)
        
        # Log status changes
        if job.state != current_state:
            current_state = job.state
            print(f"Job state: {current_state}")
        
        # Check if job has reached a terminal state
        if job.state in [s.value for s in terminal_states]:
            break
            
        # Wait before polling again
        time.sleep(poll_interval_seconds)
    else:
        pytest.fail(f"Job did not complete within {max_wait_minutes} minutes")

    print(f"Final job response: {job}")
    
    # Verify job completed successfully
    assert job.state == JobState.SUCCEEDED.value, f"Job failed with state {job.state}: {job.error}"
    
    # Load expected results
    import requests
    expected_data = requests.get(expected_json_url).json()
    
    # Verify basic metadata
    assert job.result is not None, "Job result should not be None"
    assert "text" in job.result, "Result should contain 'text' field"
    
    # Compare transcribed text (allowing for some formatting differences)
    normalized_expected = " ".join(expected_data["text"].split())
    normalized_actual = " ".join(job.result["text"].split())
    assert normalized_actual, "Transcribed text should not be empty"
    
    # Calculate text similarity (allowing for minor differences in transcription)
    from difflib import SequenceMatcher
    text_similarity = SequenceMatcher(None, normalized_expected, normalized_actual).ratio()
    print(f"Text similarity ratio: {text_similarity:.2f}")
    assert text_similarity > 0.8, "Transcribed text differs significantly from expected"
    
    # Verify segments exist
    assert "segments" in job.result, "Result should contain 'segments' field"
    assert len(job.result["segments"]) > 0, "There should be at least one segment"

    # TODO: this isn't being passed through, we'll do that later.
    # # Verify processing metrics exist
    # assert job.media_duration_seconds is not None, "Media duration should be reported"
    # assert job.processing_time_seconds is not None, "Processing time should be reported"
    # 
    # print(f"Transcription verified successfully. Duration: {job.media_duration_seconds}s, "
    #       f"Processing time: {job.processing_time_seconds}s")
    
    # Now test tenant isolation with a different tenant
    print("\nTesting tenant isolation with a different tenant ID")
    
    # Generate a different tenant ID and token
    different_tenant_id = "test-tenant-different"
    different_tenant_token = generate_jwt(different_tenant_id)
    
    # Create a new client for the different tenant
    config = jobs_api.api_client.configuration
    with ApiClient(config) as different_tenant_client:
        # Set the different tenant's auth token
        different_tenant_client.set_default_header("Authorization", f"Bearer {different_tenant_token}")
        
        # Create a new jobs API client with the different tenant's client
        different_jobs_api = JobsApi(different_tenant_client)
        
        # Attempt to access the job
        try:
            different_jobs_api.get_job_jobs_job_id_get(job_id)
            pytest.fail("Security violation: Different tenant was able to access the job")
        except Exception as e:
            # Extract status code from the exception
            status_code = getattr(e, "status", None)
            if status_code != 404:
                pytest.fail(f"Expected 404 status code, got {status_code}")
            print(f"Tenant isolation verified: Different tenant received 404 Not Found as expected")
    