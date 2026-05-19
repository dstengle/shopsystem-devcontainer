"""pytest-bdd test runner for shopsystem-devcontainer feature files."""
from pathlib import Path

import pytest
from pytest_bdd import scenarios

# Load all scenarios from the features directory.
scenarios(str(Path(__file__).parent.parent / "features" / "base_image.feature"))
