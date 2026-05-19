"""pytest-bdd test runner for shopsystem-devcontainer feature files."""
from pathlib import Path

import pytest
from pytest_bdd import scenarios

_FEATURES = Path(__file__).parent.parent / "features"

# Load all scenarios from the features directory.
scenarios(str(_FEATURES / "base_image.feature"))
scenarios(str(_FEATURES / "devcontainer_dockerfile.feature"))
