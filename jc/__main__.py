#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import sys

from .conv import conv

try:
    import beautiful_traceback

    beautiful_traceback.install()
except ImportError:
    pass


def main():
    ap = argparse.ArgumentParser(
        'jc',
        description="convert the 'chat-downloader' JSON files into a human-readable format",
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(
            prog, max_help_position=35
        ),
    )

    ADD = ap.add_argument

    ADD('files', nargs='*', type=str)
    ADD('-o', '--offset', type=int, default=0, help='time offset in seconds')
    ADD('-v', '--verbose', action='store_true', default=True, help='verbose output')

    args = ap.parse_args()

    if not args.files:
        ap.print_help()
        sys.exit(1)

    for file in args.files:
        conv(file, logging=args.verbose, time_offset=args.offset)


if __name__ == '__main__':
    main()
