# Get environment variables
port_prefix = os.environ.get("TILT_PORT_PREFIX", "")
run_mode = os.environ.get("TILT_RUNMODE", "")
testdata_port = os.environ.get("TEST__TESTDATA_PORT", "")
namespace = os.environ.get("TILT_NAMESPACE", "")


load('ext://namespace', 'namespace_create', 'namespace_inject')
namespace_create(namespace)

# temporal builder
docker_build('whisperserve-dev/temporal-dev',
            context='./_dev-env/k8s/temporal',
            dockerfile='./_dev-env/k8s/temporal/Dockerfile')

k8s_yaml(namespace_inject(read_file('_dev-env/k8s/postgres/postgres.yaml'), namespace))
k8s_yaml(namespace_inject(read_file('_dev-env/k8s/temporal/temporal.yaml'), namespace))
k8s_yaml(namespace_inject(read_file('_dev-env/k8s/minio/minio.yaml'), namespace))
docker_compose('./_dev-env/docker-compose.testdata.yml', project_name=namespace)

postgres_port = port_prefix + "10"
k8s_resource(
    'whisperserve-dev-postgres', 
    port_forwards=[port_prefix + "10:5432"],
    labels=["98-svc"]
)
temporal_ui_port = port_prefix + "31"
k8s_resource('whisperserve-dev-temporal', port_forwards=[port_prefix + '30:7233', temporal_ui_port + ':8233'], labels=["98-svc"])
k8s_resource('whisperserve-dev-minio', port_forwards=[port_prefix + '40:9000', port_prefix + '41:9001'], labels=["98-svc"])
dc_resource('whisperserve-dev-testdata', labels=["98-svc"])


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
    allow_parallel=True,
    labels=["99-meta"])

local_resource("wait-and-ensure-minio",
    allow_parallel=True,
    cmd="bash ./_dev-env/ensure-minio.bash",
    resource_deps=["whisperserve-dev-minio"],
    labels=["99-meta"])

def setup_services():
    app_port = port_prefix + "00"
    
    local_resource(
        'api',
        serve_cmd="./scripts/run-dev.bash api",
        links=[
            link("http://localhost:" + app_port, "API"),
            link("http://localhost:" + app_port + "/docs", "API Docs")
        ],
        deps=["wait-for-dependencies"],
        allow_parallel=True,
        labels=["00-app"]
    )

    local_resource(
        'worker',
        serve_cmd="./scripts/run-dev.bash worker",
        links=[link("http://localhost:" + temporal_ui_port, "Temporal UI")]
    ,
        deps=["wait-for-dependencies"],
        allow_parallel=True,
        labels=["00-app"]
    )
    
    return ["api", "worker"]

if run_mode == "dev-in-tilt":
    setup_services()
    
elif run_mode == "integration-test":
    service_deps = setup_services()
    
    local_resource(
        'wait-for-api',
        cmd="./scripts/wait-for-api.bash",
        resource_deps=["wait-for-dependencies", "api"],
        allow_parallel=True,
        labels=["01-test"]
    )   

    local_resource(
        'prepare-integration-test',
        cmd="./scripts/prepare-integration-test.bash",
        resource_deps=["wait-for-api"],
        allow_parallel=True,
        labels=["01-test"]
    )

    local_resource(
        'run-integration-test',
        cmd="./scripts/run-integration-test.bash",
        resource_deps=["prepare-integration-test", "worker"],
        allow_parallel=True,
        labels=["01-test"]
    )
else:
    # In other modes, we'd typically define a k8s deployment here
    print("Application not started. Set TILT_RUNMODE=dev-in-tilt to run the development server")