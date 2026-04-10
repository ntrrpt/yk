#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

from .conv import conv

try:
    import beautiful_traceback

    beautiful_traceback.install()
except ImportError:
    pass

if __name__ == '__main__':  # TODO: argparse
    for i in range(1, len(sys.argv)):
        conv(sys.argv[i], logging=True)
