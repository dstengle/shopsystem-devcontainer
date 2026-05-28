Feature: GitHub Actions CI Workflow: Build and Publish Devcontainer

  @scenario_hash:800267e1a3ce322f @bc:shopsystem-devcontainer
  Scenario: GitHub Actions workflow file exists at the expected path
    Given the shopsystem-devcontainer BC repository
    When the repository file tree is inspected
    Then a file named .github/workflows/publish-devcontainer.yml exists at the repository root

  @scenario_hash:9519f1d17fea806e @bc:shopsystem-devcontainer
  Scenario: Workflow triggers on push to main when .devcontainer/Dockerfile changes
    Given the shopsystem-devcontainer BC repository
    When the content of .github/workflows/publish-devcontainer.yml is read
    Then the workflow on.push.branches list contains main
    And the workflow on.push.paths list contains .devcontainer/Dockerfile

  @scenario_hash:593e74221e3e1ac4 @bc:shopsystem-devcontainer
  Scenario: Workflow declares packages write permission for ghcr.io push
    Given the shopsystem-devcontainer BC repository
    When the content of .github/workflows/publish-devcontainer.yml is read
    Then the workflow top-level permissions block sets packages to write
    And the workflow top-level permissions block sets contents to read

  @scenario_hash:8aa19792b37014d8 @bc:shopsystem-devcontainer
  Scenario: Workflow build step references .devcontainer/Dockerfile
    Given the shopsystem-devcontainer BC repository
    When the content of .github/workflows/publish-devcontainer.yml is read
    Then a workflow step exists whose configuration sets file or context to .devcontainer/Dockerfile
    And that step uses an action or run command that performs a docker build

  @scenario_hash:ef954fdd701ff931 @bc:shopsystem-devcontainer
  Scenario: Workflow push step targets ghcr.io with the correct image name
    Given the shopsystem-devcontainer BC repository
    When the content of .github/workflows/publish-devcontainer.yml is read
    Then a workflow step exists whose configuration targets the registry ghcr.io
    And that step references the image name ghcr.io/dstengle/shopsystem-bc-base
    And that step uses an action or run command that performs a docker push or equivalent registry push

  @scenario_hash:7a89fb376e611e00 @bc:shopsystem-devcontainer
  Scenario: Workflow publishes both a latest tag and a git-SHA tag
    Given the shopsystem-devcontainer BC repository
    When the content of .github/workflows/publish-devcontainer.yml is read
    Then the tags configuration for the build-push step includes ghcr.io/dstengle/shopsystem-bc-base:latest
    And the tags configuration includes a git SHA-derived tag of the form ghcr.io/dstengle/shopsystem-bc-base:sha-<short-sha>
