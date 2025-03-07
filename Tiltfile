# Get environment variables
port_prefix = os.environ.get("TILT_PORT_PREFIX", "")
run_mode = os.environ.get("TILT_RUNMODE", "")

# Load k8s manifests
k8s_yaml('_dev-env/k8s/postgres.yaml')

# Set up port forwarding for PostgreSQL
postgres_port = port_prefix + "10"
k8s_resource(
    'postgres', 
    port_forwards=[postgres_port + ":5432"],
    labels=["svc"]
)

if run_mode == "dev-in-tilt":
    app_port = port_prefix + "00"
    # Run the application as a local_resource
    local_resource(
        'whisperserve',
        cmd="cd whisperserve && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port " + app_port,
        serve_cmd="cd whisperserve && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port " + app_port,
        links=["http://localhost:" + app_port],
        deps=["postgres"],
        allow_parallel=True,
        labels=["app"]
    )
else:
    # In other modes, we'd typically define a k8s deployment here
    # But per requirements, we're focusing on the dev-in-tilt mode
    print("Application not started. Set TILT_RUNMODE=dev-in-tilt to run the development server")

print("WhisperServe Development Environment")
print("PostgreSQL available at localhost:" + postgres_port)
if run_mode == "dev-in-tilt":
    print("Development server will start automatically")
    print("API will be available at http://localhost:" + app_port)
else:
    print("Set TILT_RUNMODE=dev-in-tilt to run the development server")
