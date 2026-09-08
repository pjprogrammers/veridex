"""Shared pytest fixtures/markers for the VERIDEX AI test suite.

Heavy real-model integration tests are behind the ``real_models`` marker so the
deterministic unit tests run anywhere. Mark with `--run-real-models` to execute
the live PaddleOCR / InsightFace paths (requires models in ``data/models``).
"""
from __future__ import annotations

import numpy as np
import py.path  # noqa: F401  (pytest ships this; kept for compat)
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-models",
        action="store_true",
        default=False,
        help="Run tests that exercise real PaddleOCR / InsightFace models.",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-models"):
        return
    skip = pytest.mark.skip(reason="requires --run-real-models (real AI weights)")
    for item in items:
        if "real_models" in item.keywords:
            item.add_marker(skip)


@pytest.fixture()
def blank_image() -> np.ndarray:
    """A neutral BGR canvas with a central 'face' blob."""
    img = np.full((160, 160, 3), 180, dtype=np.uint8)
    img[55:110, 55:105] = 150
    return img
