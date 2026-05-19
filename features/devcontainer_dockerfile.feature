Feature: Devcontainer Dockerfile with shopsystem CLI tools on PATH

  @scenario_hash:d71470131e7a703b @bc:shopsystem-devcontainer
  Scenario: src/Dockerfile exists in the shopsystem-devcontainer BC repo
    Given the shopsystem-devcontainer BC repository
    When the repository file tree is inspected
    Then a file named src/Dockerfile exists at the repository root

  @scenario_hash:a28d8195c2f12ba7 @bc:shopsystem-devcontainer
  Scenario: Building src/Dockerfile produces an image with exit code zero
    Given the shopsystem-devcontainer BC repository
    And src/Dockerfile extends python:3.12-slim as its base image
    When docker build is run against src/Dockerfile with no additional arguments
    Then the build exits zero
    And a local Docker image tagged shopsystem-devcontainer:test is produced

  @scenario_hash:ee4d9bba97882fec @bc:shopsystem-devcontainer
  Scenario: shop-msg is on PATH inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test which shop-msg is executed on the host
    Then the command exits zero
    And stdout contains a path to the shop-msg executable

  @scenario_hash:097ddaa22e3d6c16 @bc:shopsystem-devcontainer
  Scenario: shop-templates is on PATH inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test which shop-templates is executed on the host
    Then the command exits zero
    And stdout contains a path to the shop-templates executable

  @scenario_hash:33412d7611b38bf7 @bc:shopsystem-devcontainer
  Scenario: shop-test-harness is on PATH inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test which shop-test-harness is executed on the host
    Then the command exits zero
    And stdout contains a path to the shop-test-harness executable

  @scenario_hash:3c64da13cceddf30 @bc:shopsystem-devcontainer
  Scenario: bd is on PATH inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    And the Dockerfile downloads the bd binary from github.com/steveyegge/beads releases and installs it to /usr/local/bin/bd
    When docker run --rm shopsystem-devcontainer:test which bd is executed on the host
    Then the command exits zero
    And stdout contains /usr/local/bin/bd

  @scenario_hash:02bbbca46cbd6899 @bc:shopsystem-devcontainer
  Scenario: shop-msg --help exits zero inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test shop-msg --help is executed on the host
    Then the command exits zero

  @scenario_hash:192ae5da24284960 @bc:shopsystem-devcontainer
  Scenario: shop-templates --help exits zero inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test shop-templates --help is executed on the host
    Then the command exits zero

  @scenario_hash:06e050f3995a5ff5 @bc:shopsystem-devcontainer
  Scenario: shop-test-harness --help exits zero inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test shop-test-harness --help is executed on the host
    Then the command exits zero

  @scenario_hash:17e18a8d24ae344e @bc:shopsystem-devcontainer
  Scenario: bd --version exits zero inside the built image
    Given an image built from src/Dockerfile in the shopsystem-devcontainer BC repo
    When docker run --rm shopsystem-devcontainer:test bd --version is executed on the host
    Then the command exits zero
    And stdout contains "bd version"

  @scenario_hash:2cb9349ca47247ab @bc:shopsystem-devcontainer
  Scenario: Dockerfile installs shop-msg shop-templates and shop-test-harness via pip from GitHub
    Given the shopsystem-devcontainer BC repository
    When the src/Dockerfile content is read
    Then src/Dockerfile contains a RUN pip install step that installs shopsystem-messaging from git+https://github.com/dstengle/shopsystem-messaging
    And src/Dockerfile contains a RUN pip install step that installs shop-templates from git+https://github.com/dstengle/shopsystem-templates
    And src/Dockerfile contains a RUN pip install step that installs shopsystem-test-harness from git+https://github.com/dstengle/shopsystem-test-harness
