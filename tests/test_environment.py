"""Smoke test: the analysis libraries are installed and importable."""

import importlib

import pytest


@pytest.mark.parametrize("module_name", ["pandas", "matplotlib", "plotly", "src"])
def test_module_is_importable(module_name):
    assert importlib.import_module(module_name) is not None
