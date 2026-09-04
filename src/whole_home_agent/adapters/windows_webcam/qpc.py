"""High-precision QPC (QueryPerformanceCounter) time conversion.

Specification: WHA-WIN-CAPTURE-ROI-001 (Section 12)
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from typing import Tuple

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    _kernel32 = ctypes.windll.kernel32
    _qpc = _kernel32.QueryPerformanceCounter
    _qpf = _kernel32.QueryPerformanceFrequency

    _LARGE_INTEGER = ctypes.c_int64


def query_performance_frequency() -> int:
    """Returns the QPC clock frequency in ticks per second."""
    if not _IS_WINDOWS:
        return 1_000_000_000
    freq = _LARGE_INTEGER()
    if not _qpf(ctypes.byref(freq)):
        raise OSError("QueryPerformanceFrequency failed")
    return int(freq.value)


def query_performance_counter() -> int:
    """Returns the current QPC counter value."""
    if not _IS_WINDOWS:
        return time.monotonic_ns()
    count = _LARGE_INTEGER()
    if not _qpc(ctypes.byref(count)):
        raise OSError("QueryPerformanceCounter failed")
    return int(count.value)


def qpc_to_monotonic_ns(counter: int, frequency: int) -> int:
    """Converts QPC counter and frequency to monotonic nanoseconds without floating point arithmetic (Section 12).

    Formula:
        q = counter // frequency
        r = counter % frequency
        monotonic_ns = q * 1_000_000_000 + (r * 1_000_000_000) // frequency
    """
    if frequency <= 0:
        raise ValueError("Frequency must be a positive integer")
    if counter < 0:
        raise ValueError("Counter must be non-negative")

    q = counter // frequency
    r = counter % frequency
    return q * 1_000_000_000 + (r * 1_000_000_000) // frequency


def now_qpc_ns() -> int:
    """Convenience function returning the current QPC time in monotonic nanoseconds."""
    if not _IS_WINDOWS:
        return time.monotonic_ns()
    freq = query_performance_frequency()
    count = query_performance_counter()
    return qpc_to_monotonic_ns(count, freq)
