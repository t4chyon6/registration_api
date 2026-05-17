"""Activation-code generation helpers."""

import random

_MIN_CODE = 0
_MAX_CODE = 9999
_CODE_WIDTH = 4
_random = random.SystemRandom()


def generate_activation_code() -> str:
    """Return a random four-digit activation code."""
    return f"{_random.randint(_MIN_CODE, _MAX_CODE):0{_CODE_WIDTH}d}"
