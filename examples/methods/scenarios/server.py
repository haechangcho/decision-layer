"""Explicit local bootstrap for reviewed tutorial Methods, using the canonical API."""
from decision_layer.api.app import create_app as product_app
from decision_layer.methods import registry
from examples.methods.scenarios.methods import AUTHORED


def create_app():
    for implementation in AUTHORED:
        registry.register(implementation)
    return product_app()
