"""Pytest configuration and deterministic fixtures."""

import os
import random
import pytest


@pytest.fixture(autouse=True)
def set_deterministic_seed():
    """Sets a deterministic seed for every test run to ensure strict reproducibility."""
    seed = 42
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
