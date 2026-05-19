"""Step definitions for shopsystem-devcontainer BDD scenarios.

These step definitions exercise the BC's Dockerfile-based base image
by shelling out to docker build / docker run to verify the image builds
correctly and that the shopsystem packages are available inside the
container.

Scenarios 2 and 3 require the shopsystem compose network (attachable: true)
and the postgres service to be reachable.  The "compose network is running"
step starts docker compose if the network is not already present.
"""
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from pytest_bdd import given, then, when

# ---------------------------------------------------------------------------
# Where the BC root's docker-compose.yml lives (for network setup).
# ---------------------------------------------------------------------------
BC_ROOT = Path(__file__).parent.parent
COMPOSE_FILE = BC_ROOT / "docker-compose.yml"
DOCKERFILE = BC_ROOT / "src" / "Dockerfile"

# The network name that docker compose creates for our shopsystem network.
# docker compose prefixes the project name to the service network name.
_COMPOSE_PROJECT = "shopsystem-devcontainer"
_NETWORK_NAME = f"{_COMPOSE_PROJECT}_shopsystem"


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def context() -> dict:
    return {}


@pytest.fixture(scope="session")
def base_image_tag() -> str:
    """Build (or reuse) the base image once for the entire test session.

    Returns the image tag.  Scenarios 2 and 3 depend on this fixture
    rather than building the image themselves.
    """
    tag = "shopsystem-devcontainer-base:test"
    result = _build_base_image(tag)
    if result.returncode != 0:
        raise RuntimeError(
            f"docker build failed (exit {result.returncode}).\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return tag


@pytest.fixture
def image_tag(base_image_tag: str) -> str:
    """Per-test image tag fixture backed by the session-scoped build."""
    return base_image_tag


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _image_exists(tag: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True,
    )
    return result.returncode == 0


def _build_base_image(tag: str) -> subprocess.CompletedProcess:
    """Build the base image from src/Dockerfile."""
    return subprocess.run(
        ["docker", "build", "-t", tag, "-f", str(DOCKERFILE), str(DOCKERFILE.parent)],
        capture_output=True,
        text=True,
    )


def _network_exists_and_attachable(network_name: str) -> bool:
    """Return True iff the named network exists and has Attachable=true."""
    result = subprocess.run(
        ["docker", "network", "inspect", network_name,
         "--format", "{{.Attachable}}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _ensure_compose_network() -> None:
    """Bring up the compose project network (and postgres) if not running."""
    if not _network_exists_and_attachable(_NETWORK_NAME):
        subprocess.run(
            ["docker", "compose",
             "-p", _COMPOSE_PROJECT,
             "-f", str(COMPOSE_FILE),
             "up", "-d", "--wait"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Brief wait for postgres to become ready
        for _ in range(20):
            r = subprocess.run(
                ["docker", "exec",
                 f"{_COMPOSE_PROJECT}-postgres-1",
                 "pg_isready", "-U", "postgres"],
                capture_output=True,
            )
            if r.returncode == 0:
                break
            time.sleep(1)


def _get_shopsystem_network_name() -> str:
    """Return the real docker network name for the shopsystem compose network."""
    # First try our own compose project's network.
    if _network_exists_and_attachable(_NETWORK_NAME):
        return _NETWORK_NAME
    # Fall back: look for any attachable network with 'shopsystem' in the name.
    result = subprocess.run(
        ["docker", "network", "ls", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
    )
    for name in result.stdout.splitlines():
        if "shopsystem" in name and _network_exists_and_attachable(name):
            return name
    raise RuntimeError("No attachable shopsystem docker network found.")


# ---------------------------------------------------------------------------
# Scenario 1: Base image builds with shopsystem packages installed
# ---------------------------------------------------------------------------

@given("a Dockerfile that extends the shopsystem-devcontainer base image")
def dockerfile_extends_base(image_tag: str, context: dict) -> None:
    """The Dockerfile in src/ IS the base image; use it directly.

    The image will be built by the When step.  Here we just record the tag.
    """
    context["image_tag"] = image_tag


@when("the image is built with docker build")
def build_image(image_tag: str, context: dict) -> None:
    result = _build_base_image(image_tag)
    context["build_returncode"] = result.returncode
    context["build_stdout"] = result.stdout
    context["build_stderr"] = result.stderr


@then("the build exits zero")
def build_exits_zero(context: dict) -> None:
    rc = context["build_returncode"]
    assert rc == 0, (
        f"docker build exited {rc}.\nSTDOUT:\n{context.get('build_stdout', '')}"
        f"\nSTDERR:\n{context.get('build_stderr', '')}"
    )


@then('shopsystem-messaging is importable in the container (python -c "import shop_msg")')
def shop_msg_importable(image_tag: str, context: dict) -> None:
    result = subprocess.run(
        ["docker", "run", "--rm", image_tag,
         "python", "-c", "import shop_msg; print('shop_msg ok')"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"python -c 'import shop_msg' failed in container.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    assert "shop_msg ok" in result.stdout


@then("shop-msg appears on PATH in the container (which shop-msg exits zero)")
def shop_msg_on_path(image_tag: str, context: dict) -> None:
    result = subprocess.run(
        ["docker", "run", "--rm", image_tag, "which", "shop-msg"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"'which shop-msg' exited {result.returncode} in container.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Scenario 2: Container reaches postgres via DSN env var on attachable network
# ---------------------------------------------------------------------------

@given("the shopsystem compose network is running with attachable: true")
def shopsystem_compose_network_running(context: dict) -> None:
    _ensure_compose_network()
    network = _get_shopsystem_network_name()
    context["shopsystem_network"] = network


@given(
    "the SHOPMSG_DSN env var is set to postgresql://postgres:postgres@postgres:5432/shopsystem"
)
def shopmsg_dsn_set_postgres(context: dict) -> None:
    context["shopmsg_dsn"] = "postgresql://postgres:postgres@postgres:5432/shopsystem"


@when("a container built from the base image starts with --network shopsystem")
def container_starts_on_network(image_tag: str, context: dict) -> None:
    # Ensure image is built
    if not _image_exists(image_tag):
        result = _build_base_image(image_tag)
        assert result.returncode == 0, f"docker build failed: {result.stderr}"

    network = context["shopsystem_network"]
    dsn = context["shopmsg_dsn"]

    # Run a quick test: use psycopg inside the container to connect
    check_script = (
        "import psycopg, os; "
        "dsn = os.environ['SHOPMSG_DSN']; "
        "conn = psycopg.connect(dsn); "
        "conn.close(); "
        "print('connected ok')"
    )
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", network,
            "-e", f"SHOPMSG_DSN={dsn}",
            image_tag,
            "python", "-c", check_script,
        ],
        capture_output=True,
        text=True,
    )
    context["network_run_returncode"] = result.returncode
    context["network_run_stdout"] = result.stdout
    context["network_run_stderr"] = result.stderr


@then("psycopg.connect(SHOPMSG_DSN) succeeds and returns a live connection")
def psycopg_connect_succeeds(context: dict) -> None:
    rc = context["network_run_returncode"]
    assert rc == 0, (
        f"psycopg.connect failed in container (exit {rc}).\n"
        f"STDOUT: {context.get('network_run_stdout', '')}\n"
        f"STDERR: {context.get('network_run_stderr', '')}"
    )
    assert "connected ok" in context["network_run_stdout"]


@then("shop-msg pending inbox --bc-root . exits zero without a connection error")
def shop_msg_pending_inbox_exits_zero(image_tag: str, context: dict) -> None:
    network = context["shopsystem_network"]
    dsn = context["shopmsg_dsn"]
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", network,
            "-e", f"SHOPMSG_DSN={dsn}",
            "--workdir", "/workspace",
            image_tag,
            "shop-msg", "pending", "inbox", "--bc-root", ".",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"shop-msg pending inbox --bc-root . exited {result.returncode}.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    # Must not contain a connection error message
    assert "connection" not in result.stderr.lower() or "error" not in result.stderr.lower(), (
        f"Unexpected connection error in stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Scenario 3: shop-msg send dispatches a message from inside the container
# ---------------------------------------------------------------------------

@given("the SHOPMSG_DSN env var is set to the postgres service DSN")
def shopmsg_dsn_set_service(context: dict) -> None:
    context["shopmsg_dsn"] = "postgresql://postgres:postgres@postgres:5432/shopsystem"


@given("a container built from the base image is running on the shopsystem network")
def container_running_on_network(image_tag: str, context: dict) -> None:
    # Ensure image is built; the container will be started per-command (--rm)
    if not _image_exists(image_tag):
        result = _build_base_image(image_tag)
        assert result.returncode == 0, f"docker build failed: {result.stderr}"
    # Store image tag for use in subsequent steps
    context["run_image"] = image_tag


@when("shop-msg send request_maintenance is invoked inside the container with a valid work_id")
def shop_msg_send_from_container(context: dict) -> None:
    network = context["shopsystem_network"]
    dsn = context["shopmsg_dsn"]
    image_tag = context.get("run_image") or context.get("image_tag")
    work_id = f"test-{uuid.uuid4().hex[:8]}"
    context["sent_work_id"] = work_id
    # Use a lead-root/repos/<bc-name> structure so that
    # `shop-msg pending outbox --lead-root <lead-root>` can locate the entry.
    lead_root = "/workspace/lead-root"
    bc_root = f"{lead_root}/repos/target-bc"
    context["lead_root_in_container"] = lead_root
    context["target_bc_root_in_container"] = bc_root

    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", network,
            "-e", f"SHOPMSG_DSN={dsn}",
            image_tag,
            "shop-msg", "send", "request_maintenance",
            "--bc-root", bc_root,
            "--work-id", work_id,
            "--description", "Test maintenance request from inside container",
            "--acceptance-criterion", "The test message is visible in inbox",
        ],
        capture_output=True,
        text=True,
    )
    context["send_returncode"] = result.returncode
    context["send_stdout"] = result.stdout
    context["send_stderr"] = result.stderr
    context["bc_root_path"] = bc_root


@then("the message appears in shop-msg read inbox for the target BC")
def message_appears_in_inbox(context: dict) -> None:
    rc = context["send_returncode"]
    assert rc == 0, (
        f"shop-msg send failed (exit {rc}).\n"
        f"STDOUT: {context.get('send_stdout', '')}\n"
        f"STDERR: {context.get('send_stderr', '')}"
    )
    # Verify the message is in the DB by reading it back from Python
    # using the same DSN that the container used.
    # The bc_root inside the container was /workspace/target-bc — we
    # identify the row by the work_id; the bc identifier is derived from
    # the resolved path the CLI used.
    work_id = context["sent_work_id"]
    network = context["shopsystem_network"]
    dsn = context["shopmsg_dsn"]
    image_tag = context.get("run_image") or context.get("image_tag")
    bc_root = context["target_bc_root_in_container"]

    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", network,
            "-e", f"SHOPMSG_DSN={dsn}",
            image_tag,
            "shop-msg", "read", "inbox",
            "--bc-root", bc_root,
            "--work-id", work_id,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"shop-msg read inbox failed (exit {result.returncode}).\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    assert work_id in result.stdout, (
        f"Expected work_id {work_id!r} in shop-msg read output.\n"
        f"STDOUT: {result.stdout}"
    )


@then("shop-msg pending outbox reports the new work_id as pending for the lead shop")
def pending_outbox_reports_work_id(context: dict) -> None:
    # "pending for the lead shop" means a BC outbox (response) row exists
    # that the lead has not yet consumed.  We simulate this by having the
    # container emit a work_done response for the sent work_id, then
    # verifying it appears in `shop-msg pending outbox --lead-root <lead_root>`.
    #
    # The bc_root used here MUST be nested under <lead_root>/repos/ so that
    # query_pending_outbox can locate it via the repos/ prefix filter.
    work_id = context["sent_work_id"]
    network = context["shopsystem_network"]
    dsn = context["shopmsg_dsn"]
    image_tag = context.get("run_image") or context.get("image_tag")
    bc_root = context["target_bc_root_in_container"]
    lead_root = context["lead_root_in_container"]

    # Step 1: emit a work_done response from inside the container so an
    # outbox row exists for the work_id at the correct bc path.
    respond_result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", network,
            "-e", f"SHOPMSG_DSN={dsn}",
            image_tag,
            "shop-msg", "respond", "work_done",
            "--bc-root", bc_root,
            "--work-id", work_id,
            "--status", "complete",
            "--summary", "test fixture: simulated BC response for pending outbox check",
        ],
        capture_output=True,
        text=True,
    )
    assert respond_result.returncode == 0, (
        f"shop-msg respond work_done failed (exit {respond_result.returncode}).\n"
        f"STDOUT: {respond_result.stdout}\nSTDERR: {respond_result.stderr}"
    )

    # Step 2: invoke `shop-msg pending outbox --lead-root <lead_root>` and
    # verify the work_id appears in the output.
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", network,
            "-e", f"SHOPMSG_DSN={dsn}",
            image_tag,
            "shop-msg", "pending", "outbox",
            "--lead-root", lead_root,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"shop-msg pending outbox exited {result.returncode}.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    assert work_id in result.stdout, (
        f"Expected work_id {work_id!r} to appear in pending outbox output.\n"
        f"STDOUT: {result.stdout}"
    )
