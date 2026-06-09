"""Smoke-тест каркаса: пакет импортируется и слои на месте."""

import importlib

import arena


def test_version_is_set():
    assert arena.__version__ == "0.1.0"


def test_all_layers_importable():
    layers = [
        "arena.config",
        "arena.providers",
        "arena.core",
        "arena.prompts",
        "arena.arena",
        "arena.engine",
        "arena.analysis",
        "arena.storage",
        "arena.report",
        "arena.web",
        "arena.models",
        "arena.cli",
    ]
    for name in layers:
        assert importlib.import_module(name) is not None
