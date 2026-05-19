Feature: shopsystem-devcontainer base image

  @scenario_hash:5a396f5df5930d3b @bc:shopsystem-devcontainer
  Scenario: Base image builds with shopsystem packages installed
    Given a Dockerfile that extends the shopsystem-devcontainer base image
    When the image is built with docker build
    Then the build exits zero
    And shopsystem-messaging is importable in the container (python -c "import shop_msg")
    And shop-msg appears on PATH in the container (which shop-msg exits zero)

  @scenario_hash:e24be0bbf9c183a3 @bc:shopsystem-devcontainer
  Scenario: Container reaches postgres via DSN env var on the attachable network
    Given the shopsystem compose network is running with attachable: true
    And the SHOPMSG_DSN env var is set to postgresql://postgres:postgres@postgres:5432/shopsystem
    When a container built from the base image starts with --network shopsystem
    Then psycopg.connect(SHOPMSG_DSN) succeeds and returns a live connection
    And shop-msg pending inbox --bc-root . exits zero without a connection error

  @scenario_hash:2aa9acc22d468179 @bc:shopsystem-devcontainer
  Scenario: shop-msg send dispatches a message from inside the container
    Given the shopsystem compose network is running with attachable: true
    And the SHOPMSG_DSN env var is set to the postgres service DSN
    And a container built from the base image is running on the shopsystem network
    When shop-msg send request_maintenance is invoked inside the container with a valid work_id
    Then the message appears in shop-msg read inbox for the target BC
    And shop-msg pending outbox reports the new work_id as pending for the lead shop
