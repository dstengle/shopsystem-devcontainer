Feature: Devcontainer Dockerfile with shopsystem CLI tools on PATH

  @scenario_hash:051d75f76e5aef2e @bc:shopsystem-devcontainer
  Scenario: .devcontainer/Dockerfile exists in the shopsystem-devcontainer BC repo
    Given the shopsystem-devcontainer BC repository
    When the repository file tree is inspected
    Then a file named .devcontainer/Dockerfile exists at the repository root

  @scenario_hash:a469ea69dd20a28f @bc:shopsystem-devcontainer
  Scenario: Building .devcontainer/Dockerfile produces an image with exit code zero
    Given the shopsystem-devcontainer BC repository
    And .devcontainer/Dockerfile extends mcr.microsoft.com/devcontainers/python:3-3.14-trixie as its base image
    When docker build is run against .devcontainer/Dockerfile with no additional arguments
    Then the build exits zero
    And a local Docker image tagged shopsystem-devcontainer:test is produced

  @scenario_hash:f1114d50decba9d4 @bc:shopsystem-devcontainer
  Scenario: shop-msg is on PATH inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test which shop-msg is executed on the host
    Then the command exits zero
    And stdout contains a path to the shop-msg executable

  @scenario_hash:1469dd54595fd9b1 @bc:shopsystem-devcontainer
  Scenario: shop-templates is on PATH inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test which shop-templates is executed on the host
    Then the command exits zero
    And stdout contains a path to the shop-templates executable

  @scenario_hash:f17559824d69867f @bc:shopsystem-devcontainer
  Scenario: shop-test-harness is on PATH inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test which shop-test-harness is executed on the host
    Then the command exits zero
    And stdout contains a path to the shop-test-harness executable

  @scenario_hash:678bfe61e80fa14b @bc:shopsystem-devcontainer
  Scenario: bd is on PATH inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    And the Dockerfile downloads the bd binary from github.com/steveyegge/beads releases and installs it to /usr/local/bin/bd
    When docker run --rm shopsystem-devcontainer:test which bd is executed on the host
    Then the command exits zero
    And stdout contains /usr/local/bin/bd

  @scenario_hash:a46d8088794e12a0 @bc:shopsystem-devcontainer
  Scenario: shop-msg --help exits zero inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test shop-msg --help is executed on the host
    Then the command exits zero

  @scenario_hash:0d822de1ab69d073 @bc:shopsystem-devcontainer
  Scenario: shop-templates --help exits zero inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test shop-templates --help is executed on the host
    Then the command exits zero

  @scenario_hash:a391c527a4fd7a83 @bc:shopsystem-devcontainer
  Scenario: shop-test-harness --help exits zero inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test shop-test-harness --help is executed on the host
    Then the command exits zero

  @scenario_hash:327d6ad526917f63 @bc:shopsystem-devcontainer
  Scenario: bd --version exits zero inside the built image
    Given an image built from .devcontainer/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test bd --version is executed on the host
    Then the command exits zero
    And stdout contains "bd version"

  @scenario_hash:0b40d52bc3887cec @bc:shopsystem-devcontainer
  Scenario: Dockerfile installs shop-msg shop-templates and shop-test-harness via pip from GitHub
    Given the shopsystem-devcontainer BC repository
    When the .devcontainer/Dockerfile content is read
    Then .devcontainer/Dockerfile contains a RUN pip install step that installs shopsystem-messaging from git+https://github.com/dstengle/shopsystem-messaging
    And .devcontainer/Dockerfile contains a RUN pip install step that installs shop-templates from git+https://github.com/dstengle/shopsystem-templates
    And .devcontainer/Dockerfile contains a RUN pip install step that installs shopsystem-test-harness from git+https://github.com/dstengle/shopsystem-test-harness
