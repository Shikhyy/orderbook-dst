# tests/test_scaffold.py
# Gate G0: This test verifies the scaffold is in place.
# It passes when the package tree exists and Python 3.11+ is running.
import importlib
import sys


def test_python_version():
    """The engine requires Python 3.11 or later."""
    assert sys.version_info >= (3, 11), (
        f"Python 3.11+ is required; found {sys.version}"
    )


def test_exchange_core_importable():
    """exchange_core must be importable as a package."""
    importlib.import_module("exchange_core")


def test_graders_importable():
    """graders must be importable as a package."""
    importlib.import_module("graders")


def test_harness_importable():
    """harness must be importable as a package."""
    importlib.import_module("harness")
