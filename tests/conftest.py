"""Step definitions for shopsystem-devcontainer BDD scenarios.

These step definitions exercise the BC's Dockerfile-based base image
by shelling out to docker build / docker run to verify the image builds
correctly and that the shopsystem packages are available inside the
container.

Scenarios 2 and 3 of the base_image feature require the shopsystem compose
network (attachable: true) and the postgres service to be reachable.  The
"compose network is running" step starts docker compose if the network is not
already present.

The devcontainer_dockerfile scenarios exercise the new Dockerfile that
installs shop-msg, shop-templates, shop-test-harness, and bd.

The ci_workflow scenarios exercise the GitHub Actions workflow file at
.github/workflows/publish-devcontainer.yml.
"""
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, then, when

# ---------------------------------------------------------------------------
# Where the BC root's docker-compose.yml lives (for network setup).
# ---------------------------------------------------------------------------
BC_ROOT = Path(__file__).parent.parent
COMPOSE_FILE = BC_ROOT / "docker-compose.yml"
DOCKERFILE = BC_ROOT / ".devcontainer" / "Dockerfile"

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


# ---------------------------------------------------------------------------
# devcontainer_dockerfile scenarios — session-scoped image build
# (image tag: shopsystem-devcontainer:test)
# ---------------------------------------------------------------------------

_DEVCONTAINER_IMAGE_TAG = "shopsystem-devcontainer:test"


@pytest.fixture(scope="session")
def devcontainer_image_tag() -> str:
    """Build (or reuse) the shopsystem-devcontainer:test image once per session.

    Returns the image tag string.
    """
    result = subprocess.run(
        [
            "docker", "build",
            "-t", _DEVCONTAINER_IMAGE_TAG,
            "-f", str(DOCKERFILE),
            str(DOCKERFILE.parent),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"docker build of shopsystem-devcontainer:test failed "
            f"(exit {result.returncode}).\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return _DEVCONTAINER_IMAGE_TAG


# ---------------------------------------------------------------------------
# Scenario: src/Dockerfile exists in the shopsystem-devcontainer BC repo
# ---------------------------------------------------------------------------

@given("the shopsystem-devcontainer BC repository")
def bc_repository(context: dict) -> None:
    """Record the BC root path in the context."""
    context["bc_root"] = BC_ROOT


@when("the repository file tree is inspected")
def inspect_file_tree(context: dict) -> None:
    """Record the set of files relative to BC root for assertion steps."""
    context["bc_root_inspected"] = context["bc_root"]


@then("a file named .devcontainer/Dockerfile exists at the repository root")
def devcontainer_dockerfile_exists(context: dict) -> None:
    dockerfile_path = context["bc_root_inspected"] / ".devcontainer" / "Dockerfile"
    assert dockerfile_path.exists(), (
        f"Expected {dockerfile_path} to exist, but it does not."
    )


# ---------------------------------------------------------------------------
# Scenario: Building src/Dockerfile produces an image with exit code zero
# ---------------------------------------------------------------------------

@given(".devcontainer/Dockerfile extends mcr.microsoft.com/devcontainers/python:3-3.14-trixie as its base image")
def dockerfile_extends_devcontainers_python(context: dict) -> None:
    """Assert the FROM line in .devcontainer/Dockerfile references the new base image."""
    dockerfile_path = context["bc_root"] / ".devcontainer" / "Dockerfile"
    content = dockerfile_path.read_text()
    assert "FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie" in content, (
        f".devcontainer/Dockerfile does not contain the expected FROM line.\n"
        f"Dockerfile content:\n{content}"
    )


@when("docker build is run against .devcontainer/Dockerfile with no additional arguments")
def docker_build_devcontainer(devcontainer_image_tag: str, context: dict) -> None:
    """Build the devcontainer image and record the outcome."""
    result = subprocess.run(
        [
            "docker", "build",
            "-t", devcontainer_image_tag,
            "-f", str(DOCKERFILE),
            str(DOCKERFILE.parent),
        ],
        capture_output=True,
        text=True,
    )
    context["build_returncode"] = result.returncode
    context["build_stdout"] = result.stdout
    context["build_stderr"] = result.stderr
    context["built_image_tag"] = devcontainer_image_tag


@then("a local Docker image tagged shopsystem-devcontainer:test is produced")
def image_tagged_devcontainer_test_exists(context: dict) -> None:
    tag = _DEVCONTAINER_IMAGE_TAG
    result = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"Docker image {tag!r} does not exist after build."
    )


# ---------------------------------------------------------------------------
# Shared Given: an image built from src/Dockerfile in the BC repo
# ---------------------------------------------------------------------------

@given("an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo")
def image_built_from_devcontainer_dockerfile(devcontainer_image_tag: str, context: dict) -> None:
    """Ensure the devcontainer image is built and record the tag in context."""
    context["devcontainer_image_tag"] = devcontainer_image_tag


# ---------------------------------------------------------------------------
# Scenario: bd binary is installed via Dockerfile
# ---------------------------------------------------------------------------

@given(
    "the Dockerfile downloads the bd binary from github.com/steveyegge/beads "
    "releases and installs it to /usr/local/bin/bd"
)
def dockerfile_installs_bd_from_steveyegge(context: dict) -> None:
    """Assert that .devcontainer/Dockerfile references steveyegge/beads releases."""
    dockerfile_path = context.get("bc_root", BC_ROOT) / ".devcontainer" / "Dockerfile"
    content = dockerfile_path.read_text()
    assert "steveyegge/beads" in content, (
        f"src/Dockerfile does not reference 'steveyegge/beads'.\n"
        f"Dockerfile content:\n{content}"
    )
    assert "/usr/local/bin/bd" in content, (
        f"src/Dockerfile does not install bd to /usr/local/bin/bd.\n"
        f"Dockerfile content:\n{content}"
    )


# ---------------------------------------------------------------------------
# When steps for docker run --rm <image> <command> scenarios
# ---------------------------------------------------------------------------

@when("docker run --rm shopsystem-devcontainer:test which shop-msg is executed on the host")
def docker_run_which_shop_msg(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "which", "shop-msg"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


@when("docker run --rm shopsystem-devcontainer:test which shop-templates is executed on the host")
def docker_run_which_shop_templates(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "which", "shop-templates"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


@when("docker run --rm shopsystem-devcontainer:test which shop-test-harness is executed on the host")
def docker_run_which_shop_test_harness(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "which", "shop-test-harness"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


@when("docker run --rm shopsystem-devcontainer:test which bd is executed on the host")
def docker_run_which_bd(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "which", "bd"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


@when("docker run --rm shopsystem-devcontainer:test shop-msg --help is executed on the host")
def docker_run_shop_msg_help(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "shop-msg", "--help"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


@when("docker run --rm shopsystem-devcontainer:test shop-templates --help is executed on the host")
def docker_run_shop_templates_help(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "shop-templates", "--help"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


@when("docker run --rm shopsystem-devcontainer:test shop-test-harness --help is executed on the host")
def docker_run_shop_test_harness_help(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "shop-test-harness", "--help"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


@when("docker run --rm shopsystem-devcontainer:test bd --version is executed on the host")
def docker_run_bd_version(context: dict) -> None:
    image = context.get("devcontainer_image_tag", _DEVCONTAINER_IMAGE_TAG)
    result = subprocess.run(
        ["docker", "run", "--rm", image, "bd", "--version"],
        capture_output=True,
        text=True,
    )
    context["cmd_returncode"] = result.returncode
    context["cmd_stdout"] = result.stdout
    context["cmd_stderr"] = result.stderr


# ---------------------------------------------------------------------------
# Then steps shared by the devcontainer_dockerfile scenarios
# ---------------------------------------------------------------------------

@then("the command exits zero")
def cmd_exits_zero(context: dict) -> None:
    rc = context["cmd_returncode"]
    assert rc == 0, (
        f"Command exited {rc}.\n"
        f"STDOUT: {context.get('cmd_stdout', '')}\n"
        f"STDERR: {context.get('cmd_stderr', '')}"
    )


@then("stdout contains a path to the shop-msg executable")
def stdout_contains_shop_msg_path(context: dict) -> None:
    stdout = context.get("cmd_stdout", "")
    assert "shop-msg" in stdout, (
        f"Expected stdout to contain a path to shop-msg; got: {stdout!r}"
    )


@then("stdout contains a path to the shop-templates executable")
def stdout_contains_shop_templates_path(context: dict) -> None:
    stdout = context.get("cmd_stdout", "")
    assert "shop-templates" in stdout, (
        f"Expected stdout to contain a path to shop-templates; got: {stdout!r}"
    )


@then("stdout contains a path to the shop-test-harness executable")
def stdout_contains_shop_test_harness_path(context: dict) -> None:
    stdout = context.get("cmd_stdout", "")
    assert "shop-test-harness" in stdout, (
        f"Expected stdout to contain a path to shop-test-harness; got: {stdout!r}"
    )


@then("stdout contains /usr/local/bin/bd")
def stdout_contains_bd_path(context: dict) -> None:
    stdout = context.get("cmd_stdout", "")
    assert "/usr/local/bin/bd" in stdout, (
        f"Expected stdout to contain '/usr/local/bin/bd'; got: {stdout!r}"
    )


@then('stdout contains "bd version"')
def stdout_contains_bd_version(context: dict) -> None:
    stdout = context.get("cmd_stdout", "")
    assert "bd version" in stdout, (
        f"Expected stdout to contain 'bd version'; got: {stdout!r}"
    )


# ---------------------------------------------------------------------------
# Scenario: Dockerfile installs packages via pip from GitHub
# ---------------------------------------------------------------------------

@when("the .devcontainer/Dockerfile content is read")
def read_dockerfile_content(context: dict) -> None:
    dockerfile_path = context.get("bc_root", BC_ROOT) / ".devcontainer" / "Dockerfile"
    context["dockerfile_content"] = dockerfile_path.read_text()


@then(
    ".devcontainer/Dockerfile contains a RUN pip install step that installs "
    "shopsystem-messaging from git+https://github.com/dstengle/shopsystem-messaging"
)
def dockerfile_installs_shopsystem_messaging(context: dict) -> None:
    content = context["dockerfile_content"]
    assert "shopsystem-messaging" in content and "dstengle/shopsystem-messaging" in content, (
        f".devcontainer/Dockerfile does not install shopsystem-messaging from "
        f"git+https://github.com/dstengle/shopsystem-messaging.\n"
        f"Dockerfile content:\n{content}"
    )


@then(
    ".devcontainer/Dockerfile contains a RUN pip install step that installs "
    "shop-templates from git+https://github.com/dstengle/shopsystem-templates"
)
def dockerfile_installs_shop_templates(context: dict) -> None:
    content = context["dockerfile_content"]
    assert "shop-templates" in content and "dstengle/shopsystem-templates" in content, (
        f".devcontainer/Dockerfile does not install shop-templates from "
        f"git+https://github.com/dstengle/shopsystem-templates.\n"
        f"Dockerfile content:\n{content}"
    )


@then(
    ".devcontainer/Dockerfile contains a RUN pip install step that installs "
    "shopsystem-test-harness from git+https://github.com/dstengle/shopsystem-test-harness"
)
def dockerfile_installs_shopsystem_test_harness(context: dict) -> None:
    content = context["dockerfile_content"]
    assert "shopsystem-test-harness" in content and "dstengle/shopsystem-test-harness" in content, (
        f".devcontainer/Dockerfile does not install shopsystem-test-harness from "
        f"git+https://github.com/dstengle/shopsystem-test-harness.\n"
        f"Dockerfile content:\n{content}"
    )


# ---------------------------------------------------------------------------
# ci_workflow scenarios — GitHub Actions workflow file assertions
# ---------------------------------------------------------------------------

_WORKFLOW_PATH = BC_ROOT / ".github" / "workflows" / "publish-devcontainer.yml"


@then("a file named .github/workflows/publish-devcontainer.yml exists at the repository root")
def workflow_file_exists(context: dict) -> None:
    assert _WORKFLOW_PATH.exists(), (
        f"Expected {_WORKFLOW_PATH} to exist, but it does not."
    )


@when("the content of .github/workflows/publish-devcontainer.yml is read")
def read_workflow_content(context: dict) -> None:
    assert _WORKFLOW_PATH.exists(), (
        f"Workflow file {_WORKFLOW_PATH} does not exist."
    )
    raw = _WORKFLOW_PATH.read_text()
    context["workflow_raw"] = raw
    context["workflow_parsed"] = yaml.safe_load(raw)


def _get_workflow_on(wf: dict) -> dict:
    """Return the 'on' block from the parsed workflow.

    PyYAML parses the bare word 'on' as the boolean True, so we look for
    both the string key "on" and the boolean key True.
    """
    return wf.get("on") or wf.get(True) or {}


@then("the workflow on.push.branches list contains main")
def workflow_push_branches_contains_main(context: dict) -> None:
    wf = context["workflow_parsed"]
    on_block = _get_workflow_on(wf)
    branches = on_block.get("push", {}).get("branches", [])
    assert "main" in branches, (
        f"Expected 'main' in on.push.branches; got: {branches!r}"
    )


@then("the workflow on.push.paths list contains .devcontainer/Dockerfile")
def workflow_push_paths_contains_dockerfile(context: dict) -> None:
    wf = context["workflow_parsed"]
    on_block = _get_workflow_on(wf)
    paths = on_block.get("push", {}).get("paths", [])
    assert ".devcontainer/Dockerfile" in paths, (
        f"Expected '.devcontainer/Dockerfile' in on.push.paths; got: {paths!r}"
    )


@then("the workflow top-level permissions block sets packages to write")
def workflow_permissions_packages_write(context: dict) -> None:
    wf = context["workflow_parsed"]
    permissions = wf.get("permissions", {})
    assert permissions.get("packages") == "write", (
        f"Expected permissions.packages == 'write'; got: {permissions!r}"
    )


@then("the workflow top-level permissions block sets contents to read")
def workflow_permissions_contents_read(context: dict) -> None:
    wf = context["workflow_parsed"]
    permissions = wf.get("permissions", {})
    assert permissions.get("contents") == "read", (
        f"Expected permissions.contents == 'read'; got: {permissions!r}"
    )


def _get_all_steps(workflow_parsed: dict) -> list:
    """Return a flat list of all step dicts from all jobs in the workflow."""
    steps = []
    for job in workflow_parsed.get("jobs", {}).values():
        steps.extend(job.get("steps", []))
    return steps


@then("a workflow step exists whose configuration sets file or context to .devcontainer/Dockerfile")
def workflow_step_references_dockerfile(context: dict) -> None:
    wf = context["workflow_parsed"]
    raw = context["workflow_raw"]
    steps = _get_all_steps(wf)
    # Check for the dockerfile reference in any step's 'with' block or 'run' text,
    # or in the raw YAML text (handles multi-line run scripts and action 'with' blocks).
    found = False
    for step in steps:
        with_block = step.get("with", {}) or {}
        for key, val in with_block.items():
            if val and ".devcontainer/Dockerfile" in str(val):
                found = True
                break
        if found:
            break
        run_val = step.get("run", "")
        if run_val and ".devcontainer/Dockerfile" in run_val:
            found = True
            break
    # Fallback: search raw text for the path adjacent to file/context keywords
    if not found:
        found = ".devcontainer/Dockerfile" in raw
    assert found, (
        "No workflow step found whose configuration references .devcontainer/Dockerfile.\n"
        f"Steps: {steps}"
    )
    context["_build_steps"] = [
        s for s in steps
        if ".devcontainer/Dockerfile" in str(s.get("with", {}))
        or ".devcontainer/Dockerfile" in str(s.get("run", ""))
    ]


@then("that step uses an action or run command that performs a docker build")
def workflow_step_performs_docker_build(context: dict) -> None:
    wf = context["workflow_parsed"]
    steps = _get_all_steps(wf)
    # Look for a step that uses docker/build-push-action or has 'docker build' in 'run'
    found = False
    for step in steps:
        uses = step.get("uses", "")
        run = step.get("run", "")
        if "docker/build-push-action" in uses or "docker build" in run:
            found = True
            break
    assert found, (
        "No workflow step found that performs a docker build "
        "(expected docker/build-push-action or 'docker build' in a run step).\n"
        f"Steps: {steps}"
    )


@then("a workflow step exists whose configuration targets the registry ghcr.io")
def workflow_step_targets_ghcr(context: dict) -> None:
    wf = context["workflow_parsed"]
    raw = context["workflow_raw"]
    steps = _get_all_steps(wf)
    found = False
    for step in steps:
        with_block = step.get("with", {}) or {}
        for key, val in with_block.items():
            if val and "ghcr.io" in str(val):
                found = True
                break
        if found:
            break
        run_val = step.get("run", "")
        if run_val and "ghcr.io" in run_val:
            found = True
            break
    if not found:
        found = "ghcr.io" in raw
    assert found, (
        "No workflow step found whose configuration references ghcr.io.\n"
        f"Steps: {steps}"
    )


@then("that step references the image name ghcr.io/dstengle/shopsystem-devcontainer")
def workflow_step_references_image_name(context: dict) -> None:
    raw = context["workflow_raw"]
    image_name = "ghcr.io/dstengle/shopsystem-devcontainer"
    assert image_name in raw, (
        f"Expected workflow to reference image name {image_name!r}.\n"
        f"Workflow content:\n{raw}"
    )


@then(
    "that step uses an action or run command that performs a docker push "
    "or equivalent registry push"
)
def workflow_step_performs_docker_push(context: dict) -> None:
    wf = context["workflow_parsed"]
    steps = _get_all_steps(wf)
    # docker/build-push-action with push: true performs both build and push.
    # A 'docker push' run command also qualifies.
    found = False
    for step in steps:
        uses = step.get("uses", "")
        run = step.get("run", "")
        with_block = step.get("with", {}) or {}
        if "docker/build-push-action" in uses and with_block.get("push") is True:
            found = True
            break
        if "docker push" in run:
            found = True
            break
    assert found, (
        "No workflow step found that performs a docker push "
        "(expected docker/build-push-action with push:true, or 'docker push' in run).\n"
        f"Steps: {steps}"
    )


@then(
    "the tags configuration for the build-push step includes "
    "ghcr.io/dstengle/shopsystem-devcontainer:latest"
)
def workflow_tags_include_latest(context: dict) -> None:
    wf = context["workflow_parsed"]
    raw = context["workflow_raw"]
    image = "ghcr.io/dstengle/shopsystem-devcontainer"
    # The tags field may be a multiline string or a list in the parsed YAML.
    steps = _get_all_steps(wf)
    found = False
    for step in steps:
        with_block = step.get("with", {}) or {}
        tags_val = with_block.get("tags", "")
        if tags_val and f"{image}:latest" in str(tags_val):
            found = True
            break
    if not found:
        found = f"{image}:latest" in raw
    assert found, (
        f"Expected tags configuration to include '{image}:latest'.\n"
        f"Workflow content:\n{raw}"
    )


@then(
    "the tags configuration includes a git SHA-derived tag of the form "
    "ghcr.io/dstengle/shopsystem-devcontainer:sha-<short-sha>"
)
def workflow_tags_include_sha_tag(context: dict) -> None:
    raw = context["workflow_raw"]
    image = "ghcr.io/dstengle/shopsystem-devcontainer"
    # Accept any expression that produces a sha- prefixed tag:
    # e.g. sha-${{ github.sha }}, sha-$(git rev-parse --short HEAD), sha-${GITHUB_SHA::7}, etc.
    # We look for the image prefix followed by :sha- and some non-empty expression.
    pattern = re.escape(image) + r":sha-"
    assert re.search(pattern, raw), (
        f"Expected tags configuration to include a sha- prefixed tag pattern "
        f"matching '{image}:sha-...'.\n"
        f"Workflow content:\n{raw}"
    )
