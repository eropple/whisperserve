# Task: Design a Multi-Tenant Whisper API Service

I need your help designing a standalone speech-to-text transcription service that wraps Whisper models with a clean, multi-tenant API. This is an open-source project separate from other systems I'm working on, but follows similar architectural principles.

## Architecture

### Process Model
- Single-process design combining API and worker in one application
- FastAPI for HTTP endpoints
- Background task loop for job processing
- Shared model loading for efficient resource usage
- PostgreSQL with SKIP LOCKED pattern for job queue

#### Example Logging Implementation
```python
import structlog
import logging
import contextvars
from fastapi import FastAPI, Request, Depends
from uuid import uuid4

# Create context variables
request_id_var = contextvars.ContextVar("request_id", default=None)
tenant_id_var = contextvars.ContextVar("tenant_id", default=None)

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

app = FastAPI()

# Middleware to set context vars
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    # Generate unique request ID
    request_id = str(uuid4())
    request_id_var.set(request_id)
    
    # Extract tenant from JWT (placeholder implementation)
    tenant_id = get_tenant_from_jwt(request)
    tenant_id_var.set(tenant_id)
    
    # Bind context vars that will be included in all log entries
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        tenant_id=tenant_id,
        path=request.url.path,
        method=request.method
    )
    
    # Add request ID to response headers for correlation
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response

# Create logger instance
logger = structlog.get_logger()

# Usage in API endpoint
@app.post("/jobs/")
async def create_job(job_request: JobRequest):
    logger.info("Creating new transcription job", media_url=job_request.media_url)
    
    # Process request...
    job_id = await create_job_in_db(job_request)
    
    logger.info("Job created successfully", job_id=job_id)
    return {"job_id": job_id}

# Usage in background worker
async def process_job(job_id: str, model):
    # Set context for this background task
    structlog.contextvars.bind_contextvars(
        job_id=job_id,
        tenant_id=job.tenant_id,
        worker_id=worker_id
    )
    
    logger.info("Starting job processing")
    
    try:
        # Process job...
        logger.info("Media download started", url=job.media_url)
        # More processing...
        
        logger.info("Job completed successfully", 
                    processing_time=processing_time,
                    media_duration=media_duration)
                    
    except Exception as e:
        logger.exception("Job processing failed", error=str(e))
        # Handle failure...
```

## Database Design
- PostgreSQL for both API data and job queue
- Transactional job queue using SKIP LOCKED
- Job status tracking and result storage
- Tenant isolation at the database level

### Process Flow
1. Client submits job via API
2. Job stored in PostgreSQL
3. Background worker loop claims jobs
4. Models loaded once at startup
5. Results written back to database
6. Client polls for completion

## Core Requirements

### Media Processing
- Support for both audio and video input files
- FFmpeg integration for extracting audio tracks from video files
- Handling of various media formats (MP4, MKV, MP3, WAV, etc.)
- Smart handling of multitrack audio with multiple processing modes:
  - `downmix`: Standard mono downmix (default)
  - `select`: Process only a specific track by index
  - `multitrack`: Process all tracks separately and interleave results based on timestamps

### Multi-Tenant Design
- Authentication via JWT tokens
- Each JWT contains a configurable tenant key claim
- Complete isolation between tenants (tenant A cannot access tenant B's resources)
- All operations (jobs, results) are scoped to tenant

### Technology Stack
- Python 3.11.11 with FastAPI
- Pydantic for data validation and schema generation
- Asynchronous API design
- FFmpeg for media processing
- OpenTelemetry for observability
- Kubernetes deployment ready

### Pluggable Model Backends
The service needs to support multiple Whisper implementations:
1. PyTorch Whisper - for AMD GPUs and Apple Metal
2. Faster Whisper - for NVIDIA GPUs with optimal performance
3. whisper.cpp - for CPU-optimized deployment
4. Mock/Static backend - for testing (returns predetermined transcriptions)

### Configuration
- Server-level backend selection (PyTorch Whisper, Faster Whisper, whisper.cpp, mock)
- Server-level model size/path configuration
- Runtime configuration for hardware acceleration (CUDA, ROCm, Metal, CPU)
- Local model caching in a persistent volume
- Optional OpenTelemetry configuration

## API Design

### Asynchronous Job Pattern
- Submit transcription job → receive job ID
- Poll for job completion using job ID
- Jobs are created, accessed, and managed within tenant boundaries

### Endpoints
The API should implement:
1. Job submission endpoint
   - Takes media URL (audio or video - client manages storage/pre-signed URLs)
   - Returns job ID
   - Should handle various media formats (MP4, MKV, MP3, WAV, etc.)
   
2. Job status/result endpoint
   - Takes job ID
   - Returns status, errors, or completed transcription

3. Health/diagnostics endpoint
   - Reports backend availability, loaded models, etc.

### Request Parameters
The job submission should accept:
- Media URL (required)
- Target language (optional, for translation)
- Option for word-level timestamps (if supported by backend)
- Quality/accuracy settings
- Media type hint (optional, to help with processing)
- Audio processing mode (`downmix`, `select`, `multitrack`)
- Track selection index (when using `select` mode)

### Response Format
The transcription result should include:
- Full text transcription
- Detected language
- Segments with timestamps
- Track source for each segment (track ID or "downmix")
- Confidence scores
- Word-level details (when available)
- Rich error information when failures occur
- Usage metrics (media duration, processing time)

## Database Design

### Job Queue Schema
The service should use PostgreSQL for the job queue with:
- Jobs table with appropriate indexes
- SKIP LOCKED pattern for job claiming
- Transactional safety for job status updates
- Tenant isolation through schema design
- Monitoring queries for queue health
- Job retry and error tracking

### Example Schema
```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    media_url TEXT NOT NULL,
    processing_mode TEXT NOT NULL DEFAULT 'downmix',
    track_index INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    worker_id TEXT,
    retry_count INTEGER DEFAULT 0,
    error JSON,
    result JSON,
    media_duration_seconds NUMERIC(10, 2),
    processing_time_seconds NUMERIC(10, 2)
);

CREATE INDEX idx_jobs_status_tenant ON jobs (status, tenant_id, created_at) 
    WHERE status = 'pending';
```

## Testing Requirements
- Complete unit test coverage using the mock backend
- Integration tests for each backend type
- Environment-specific testing pipeline
- Mocking strategies for testing the job queue and storage systems

## Innovative Features

### Multitrack Transcription
- Process multi-channel audio/video intelligently
- Tag each segment with its source track ID
- Interleave transcriptions from multiple tracks based on timestamps
- Provide natural speaker separation without diarization algorithms
- Maintain individual track metadata where available

## Logging & Observability

### Structured Logging
- JSON-formatted structured logs for all events
- Use `structlog` as the primary logging library
- Consistent log schema across all components
- Contextualized logging with tenant and request information
- Standard fields in all logs:
  - `timestamp` (ISO 8601 format)
  - `level` (INFO, WARNING, etc.)
  - `tenant_id` (from JWT)
  - `request_id` (correlation ID)
  - `trace_id` (when OpenTelemetry is enabled)
  - `event` (the primary log message)

### Log Context Enrichment
- Automatic context injection via FastAPI middleware
- Request context variables (tenant, request ID)
- Background task context tracking
- Error and exception enrichment

### OpenTelemetry Integration
- Optional integration with OpenTelemetry (configurable)
- Distributed tracing across API requests and async processing when enabled
- Metrics collection for service performance
- Integration with popular backends (Jaeger, Prometheus, etc.)
- Graceful fallback when OpenTelemetry is not configured
- Correlation between logs and traces via trace/span IDs

### Usage Metrics
- Track audio/video duration processed per request
- Aggregate usage metrics by tenant
- Include processing duration in API responses
- Export consumption metrics to external monitoring systems
- API endpoint for tenant usage statistics

### Startup Configuration
The service should be configured at startup with:
- Backend selection (PyTorch Whisper, Faster Whisper, whisper.cpp, mock)
- Model size/path
- Hardware acceleration settings (CUDA, ROCm, Metal, CPU)
- JWT configuration (secret, tenant claim field)
- Model caching location
- Runtime constraints (threads, memory limits)

### Deployment Considerations
- Kubernetes-ready configuration
- Single container image with combined API and worker
- Persistent volume for model storage
- Resource requests/limits appropriate for ML workloads
- Graceful startup/shutdown with model pre-loading
- Health probes for both API and worker functionality
- Horizontal scaling based on combined API and processing load
- Readiness probe should verify both API and background task health

## Development Approach
I'd like to implement this with well-structured, maintainable code that:
- Uses Pydantic models for all data structures
- Leverages FastAPI's dependency injection
- Has clear separation of concerns
- Implements structured JSON logging with context preservation
- Follows Python best practices
- Properly manages the application lifecycle (startup, background tasks, shutdown)
- Uses PostgreSQL effectively for the job queue
- Handles worker failures and job retries gracefully

## Development Environment
- Python 3.11.11
- ASDF version manager
- Poetry for dependency management
- Docker for containerization (do this _later_)
- GitHub Actions for CI/CD
  - Don't try to use GHA for anything that requires actual ML models; automated integration tests will be done with mock models
- We're developing first on Macs, so concentrate on CPU and Metal model implementations, and we'll come back later to CUDA and ROCm.

### Common Setup Issues

#### Poetry and Dependencies

When running scripts, ensure you're using Poetry to access project dependencies:

```bash
# Wrong: Running directly (dependencies won't be available)
./scripts/check-config.py

# Correct: Running with Poetry
poetry run python scripts/check-config.py

# Alternative: Using dotenvx with Poetry
dotenvx load --env-file=.env.development -- poetry run python scripts/check-config.py
```

Poetry manages project dependencies in its own virtual environment. Scripts run outside this environment can't access packages like pydantic, FastAPI, etc.

#### Module Import Issues

If you see errors like `ModuleNotFoundError: No module named 'app'`, check that:

1. Your directory structure matches your import statements
2. The project root is in your Python path
3. You're running the script from the correct directory

Python scripts in subdirectories (like `scripts/`) may need to explicitly add the project root to `sys.path`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add project root
```

#### Environment Variable Management

We use dotenvx for environment variable management:

```bash
# Load variables for a single command
dotenvx run -- your-command
```

Remember that `DATABASE__DSN` format maps to nested config objects in our app configuration.

#### Required Dev Tools

Make sure to run `./scripts/setup-dev.bash` to install all required developer tools:
- asdf for Python version management
- dotenvx for environment variable loading
- tilt for local development environment

#### Development Scripts

Instead of remembering complex commands, use our development scripts:
- `./scripts/svc-up.bash` - Start the development environment
- `./scripts/svc-down.bash` - Stop the development environment
- `./scripts/check-config.py` - Verify configuration loading

## Final Advice To Cody

Please help me design this system with detailed implementation suggestions. Focus on good architecture patterns for the ML service backend, proper API design, and testing strategies.

I want to understand every step as we go, so stop after semantically related steps and wait for me to prompt you to continue.