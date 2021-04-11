"""Poezio type stuff"""

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

__all__ = ['TypedDict']
