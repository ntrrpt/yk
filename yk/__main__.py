#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys
from pathlib import Path

from loguru import logger as log
from tabulate import tabulate

from . import util
from .serve import main as loop_main

try:
    import beautiful_traceback

    beautiful_traceback.install()
except ImportError:
    pass

r"""
todo:
    - web api
    - --enable-chat-downloader
    - remove stopwatch-py ??? !!!!!!!!!!!!!!!!
"""

#########################
## default rec_args

C_STREAMLINK = ' '.join([
    "--twitch-disable-ads",
    "--hls-live-restart",
    "--fs-safe-rules",                  "Windows",
    "--http-timeout",                   "180",
    "--stream-segment-threads",         "2",
    "--stream-segment-timeout",         "180",
    "--stream-segment-attempts",        "300",
    "--hls-segment-ignore-names",       "preloading",
    "--hls-playlist-reload-attempts",   "30",
    "--hls-live-edge",                  "5",
    "--stream-timeout",                 "120",
    "--ringbuffer-size",                "64M",
    "--loglevel",                       "trace"
])  # fmt: skip

C_YTDLP = ' '.join([
    "--verbose",
    "--ignore-config",
    "--remote-components",      "ejs:github",
    "--merge-output-format",    "mp4",
    "--concurrent-fragments",   "3",
    "--retries",                "30"
])  # fmt: skip

C_YTARCHIVE = ' '.join([
    "--trace",
    "--no-frag-files",
    "--no-save-state",
    "--write-mux-file",
    "--no-merge",
    '--add-metadata',
    "--threads",        "3"
])  # fmt: skip


def main():
    #########################
    ## args

    ap = argparse.ArgumentParser(
        'yk',
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(
            prog, max_help_position=35
        ),
    )
    ADD = ap.add_argument
    ENV = os.getenv

    def SENV(env, fallback=None, sp_char=' '):
        return ENV(env, fallback).split(sp_char)

    # fmt: off
    bg = "http://127.0.0.1:4416"

    ADD("urls", nargs="*", type=str)

    ADD('-i', '--input',   nargs='+', default=SENV('YK_INPUT', ''),      help='lists with channels (.toml)') 
    ADD('-o', '--output',  type=str,  default=ENV("YK_OUTPUT", ''),      help='output folder')
    ADD('-l', '--log',     type=str,  default=ENV("YK_LOG", 'DISABLED'), help='log to file (path to folder / file)')
    ADD('--debug',         action='store_true', help='verbose output')
    ADD('--trace',         action='store_true', help='verbosest output')

    g = ap.add_argument_group('external tools options')
    ADD = g.add_argument

    ADD("--chk",           type=str,  default='dlp', choices=["str", "dlp"],        help="live-checking method")
    ADD("--rec",           type=str,  default='dlp', choices=["str", "dlp", "yta"], help="recording method")

    ADD('--str-args',      type=str,  default=ENV("YK_ARGS_STREAMLINK", C_STREAMLINK), help='streamlink cli arguments')
    ADD('--dlp-args',      type=str,  default=ENV("YK_ARGS_YTDLP", C_YTDLP),           help='yt-dlp cli arguments')
    ADD('--yta-args',      type=str,  default=ENV("YK_ARGS_YTARCHIVE", C_YTARCHIVE),   help='ytarchive cli arguments')

    g = ap.add_argument_group('stream options')
    ADD = g.add_argument

    ADD('-q', '--quality', type=str,  default=ENV("YK_QUALITY", 'best'), help='recording quality (default: best)')
    ADD('-d', '--delay',   type=int,  default=ENV("YK_DELAY", 60),       help='delay beetwen checks (default: 60)')
    ADD('-p', '--proxy',   nargs='+', default=SENV('YK_PROXY', ''),      help='proxies')
    ADD('-a', '--apprise', type=str,  default=ENV("YK_APPRISE", ''),     help='apprise config (url or .yml file)')
    ADD('-c', '--cookies', type=str,  default=ENV("YK_COOKIES", ''),     help='path to cookies.txt (netscape format)')
    ADD('-b', '--bgutil',  type=str,  default=ENV("YK_BGUTIL", bg),      help='bgutil-ytdlp-pot-provider url')

    # fmt: on

    args = ap.parse_args()

    #########################
    ## logging

    log.remove()

    log_lvl = 'INFO'
    log_fmt = (
        '<light-black>{time:YY-MM-DD HH:mm:ss.SSS Z}</light-black>'
        ' <dim>[</dim><level>{level: <7}</level><dim>]</dim>'
        ' <light-white>{message: <30}</light-white>'
    )

    if args.debug:
        log_lvl = 'DEBUG'

    if args.trace:
        log_lvl = 'TRACE'
        log_fmt += (
            ' [<light-blue>{name}.{function}</light-blue>:<cyan>{line}</cyan>] {extra}'
        )

    log.add(sys.stderr, level=log_lvl, format=log_fmt)

    if args.log != 'DISABLED':
        log_path = Path(args.log)
        if log_path.is_dir():
            log_path = log_path / util.dt_now('%Y-%m-%d.log')

        log.add(log_path, level=log_lvl, format=log_fmt, encoding='utf-8')

    #########################
    ## envs

    env_tab = [
        ['YK_ARGS_STREAMLINK', args.str_args],
        ['YK_ARGS_YTDLP', args.dlp_args],
        ['YK_ARGS_YTARCHIVE', args.yta_args],
        ['------------------', ' '],
        ['YK_INPUT', args.input],
        ['YK_OUTPUT', args.output],
        ['YK_PROXY', args.proxy],
        ['YK_APPRISE', args.apprise],
        ['YK_LOG', args.log],
        ['YK_DELAY', args.delay],
        ['YK_COOKIES', args.cookies],
        ['YK_BGUTIL', args.bgutil],
    ]

    log.debug(
        'envs:\n'
        + tabulate(  # TODO: word wrapping
            env_tab,
            colalign=('right', 'left'),
            tablefmt='plain',
            maxcolwidths=[None, 100],
        ),
    )

    pwdir = Path(__file__).resolve().parent
    os.environ['PATH'] = os.pathsep.join([str(pwdir), os.environ['PATH']])

    log.trace(f'ret_code: {loop_main(args)}')


if __name__ == '__main__':
    main()
