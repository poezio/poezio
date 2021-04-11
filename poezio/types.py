"""Poezio type stuff"""

try:
    from typing import TypedDict, Literal
except ImportError:
    from typing_extensions import TypedDict, Literal

__all__ = ['TypedDict', 'Literal']
