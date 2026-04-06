#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys
from pathlib import Path

from loguru import logger as log
from tabulate import tabulate

from .util import dt_now

try:
    import beautiful_traceback

    beautiful_traceback.install()
except ImportError:
    pass


r"""
todo:
    - web api
    - fix twitch chat
    - delay when all streams is recording
    - todo default chk / rec
    - remove stopwatch-py ??? !!!!!!!!!!!!!!!!
    - argparse groups !!!!!!!!!!!!
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

    arg = argparse.ArgumentParser()
    ADD = arg.add_argument
    ENV = os.getenv

    def SENV(env, fallback=None, sp_char=' '):
        return ENV(env, fallback).split(sp_char)

    # fmt: off
    bgutil_def_addr = 'http://127.0.0.1:4416'

    ADD("urls", nargs="*", type=str)

    ADD('-i', '--input',   nargs='+', default=SENV('YK_INPUT', ''),      help='dirs / files with channels (list.toml, /tomls)') 
    ADD('-o', '--output',  type=str,  default=ENV("YK_OUTPUT", ''),      help='stream output folder')
    ADD('-l', '--log',     type=str,  default=ENV("YK_LOG", 'DISABLED'), help='log output folder / file')

    ADD('-d', '--delay',   type=int,  default=ENV("YK_DELAY", 15),               help='streams check delay')
    ADD('-p', '--proxy',   nargs='+', default=SENV('YK_PROXIES', ''),            help='proxies')
    ADD('-a', '--apprise', type=str,  default=ENV("YK_APPRISE", ''),             help='apprise config (url or .yml)')
    ADD('-c', '--cookies', type=str,  default=ENV("YK_COOKIES", ''),             help='path to cookies.txt (netscape format)')
    ADD('-b', '--bgutil',  type=str,  default=ENV("YK_BGUTIL", bgutil_def_addr), help='bgutil-ytdlp-pot-provider url')

    ADD('--str-args',      type=str,  default=ENV("YK_ARGS_STREAMLINK", C_STREAMLINK), help='streamlink cli arguments')
    ADD('--dlp-args',      type=str,  default=ENV("YK_ARGS_YTDLP", C_YTDLP),           help='yt-dlp cli arguments')
    ADD('--yta-args',      type=str,  default=ENV("YK_ARGS_YTARCHIVE", C_YTARCHIVE),   help='ytarchive cli arguments')

    ADD("--chk",           type=str,  choices=["dlp", "str"],        help="live-checking method")
    ADD("--rec",           type=str,  choices=["str", "yta", "dlp"], help="recording method")

    ADD('--debug',         action='store_true', help='verbose output')
    ADD('--trace',         action='store_true', help='verbosest output')
    # fmt: on

    args = arg.parse_args()
    # print(args.urls)
    # sys.exit()

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
            log_path = log_path / dt_now('%Y-%m-%d.log')

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
        ['YK_PROXIES', args.proxy],
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

    # TODO: select custom dir
    pwdir = Path(__file__).resolve().parent
    os.environ['PATH'] = os.pathsep.join([str(pwdir), os.environ['PATH']])

    from .loop import main as loop_main

    loop_main(args)


if __name__ == '__main__':
    main()
