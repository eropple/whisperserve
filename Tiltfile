# Get environment variables
port_prefix = os.environ.get("TILT_PORT_PREFIX", "")
run_mode = os.environ.get("TILT_RUNMODE", "")

# temporal builder
docker_build('whisperserve-dev/temporal-dev',
            context='./_dev-env/k8s/temporal',
            dockerfile='./_dev-env/k8s/temporal/Dockerfile')

k8s_yaml('_dev-env/k8s/postgres/postgres.yaml')
k8s_yaml('_dev-env/k8s/temporal/temporal.yaml')
k8s_yaml('_dev-env/k8s/minio/minio.yaml')

postgres_port = port_prefix + "10"
k8s_resource(
    'whisperserve-dev-postgres', 
    port_forwards=[port_prefix + "10:5432"],
    labels=["98-svc"]
)
k8s_resource('whisperserve-dev-temporal', port_forwards=[port_prefix + '30:7233', port_prefix + '31:8233'], labels=["98-svc"])
k8s_resource('whisperserve-dev-minio', port_forwards=[port_prefix + '40:9000', port_prefix + '41:9001'], labels=["98-svc"])



local_resource("wait-for-postgres",
    allow_parallel=True,
    cmd="bash ./_dev-env/wait-for-postgres.bash",
    resource_deps=["whisperserve-dev-postgres"],
    labels=["99-meta"])

local_resource("wait-for-temporal",
    allow_parallel=True,
    cmd="bash ./_dev-env/wait-for-temporal.bash",
    resource_deps=["whisperserve-dev-temporal"],
    labels=["99-meta"])

local_resource("wait-for-dependencies",
    cmd="echo 'Dependencies OK'",
    resource_deps=[
        "wait-for-postgres",
        "wait-for-temporal",
    ],
    labels=["99-meta"])

local_resource("wait-and-ensure-minio",
    allow_parallel=True,
    cmd="bash ./_dev-env/ensure-minio.bash",
    resource_deps=["whisperserve-dev-minio"],
    labels=["99-meta"])

if run_mode == "dev-in-tilt":
    app_port = port_prefix + "00"
    # Run the application as a local_resource
    local_resource(
        'api',
        serve_cmd="./scripts/run-dev.bash api",
        links=["http://localhost:" + app_port],
        deps=["wait-for-dependencies"],
        allow_parallel=True,
        labels=["00-app"]
    )

    local_resource(
        'worker',
        serve_cmd="./scripts/run-dev.bash worker",
        links=["http://localhost:" + app_port],
        deps=["wait-for-dependencies"],
        allow_parallel=True,
        labels=["00-app"]
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
