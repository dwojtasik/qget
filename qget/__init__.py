#!/usr/bin/env python3

"""
qget
~~~~~~~~~~~~~
Async http downloader
:copyright: (c) 2022 by Dominik Wojtasik.
:license: Apache2, see LICENSE for more details.
"""
__version__ = "0.0.1"

from qget.qget_aio import ProgressState, qget, qget_coro

__all__ = ["qget", "qget_coro", "ProgressState"]
