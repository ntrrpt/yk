#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import shutil
import subprocess as sp
import sys
import threading
import time
from pathlib import Path

from loguru import logger as log

from . import config, util
from .record import record

unload = threading.Event()


def get_threads(raw=False):
    threads = [x for x in threading.enumerate() if x.name != 'MainThread']

    if raw:
        return threads

    return [x.name for x in threads]


def is_running(name):
    threads = get_threads()

    if name in threads:
        log.trace('thread running', name=name, threads=threads)
        return True

    log.trace('thread not running', name=name, threads=threads)
    return False


def is_live(url, proxy: str = '', cookies: Path = Path()):
    if 'youtube' in url and 'watch?v=' not in url:
        url += '/live'

    c = ['streamlink', '--loglevel', 'trace', '--url', url]

    if proxy:
        c += ['--http-proxy', proxy]

    if cookies.is_file():
        c += ['--http-cookies-file', str(cookies)]

    with sp.Popen(c, stdout=sp.PIPE, stderr=sp.PIPE, text=True) as proc:
        stdout, stderr = proc.communicate()

        online = proc.poll() == 0

        # loguru '{}' escaping bug
        output = str(stdout + stderr).replace('{', '{{').replace('}', '}}')

        log.trace(f'is live: {online}\n{output}', url=url, proxy=proxy, cookies=cookies)
        return online


def main(args):
    if args.yta and not shutil.which('ytarchive'):
        log.warning('ytarchive not found, fallback to yt-dlp')
        args.yta = False
        args.dlp = True

    if args.dlp and not shutil.which('yt-dlp'):
        log.warning('yt-dlp not found, fallback to streamlink')
        args.yta = False
        args.dlp = False

    if (args.yta or args.dlp) and not shutil.which('ffmpeg'):
        log.warning('ffmpeg not found, fallback to streamlink')
        args.yta = False
        args.dlp = False

    if not shutil.which('streamlink'):
        log.critical('streamlink not found, cannot continue')
        sys.exit(1)

    if not args.input:
        log.critical('no channel lists, add some with "--input" argument')
        sys.exit(1)

    gf = util.get_files(args.input, exts=['.toml'])
    if not gf:
        log.critical('no .toml files')
        sys.exit(1)

    pc = config.parse_configs(gf, args=args)
    if not pc:
        log.critical('no channels in configs')
        sys.exit(1)

    try:
        while True:
            files = util.get_files(args.input, exts=['.toml'])

            if not files:
                log.error('no files for monitoring')
                time.sleep(args.delay)

            channels = config.parse_configs(files, args=args)

            mtimes = util.sum_mtime(files)

            for i, (ch, cfg) in enumerate(channels.items(), start=1):
                if util.sum_mtime(files) != mtimes:
                    log.info('list updated!')
                    break

                if is_running(cfg['url']):
                    continue

                proxy = random.choice(args.proxy) if args.proxy else None
                stream = is_live(cfg['url'], proxy, args.cookies)

                if cfg['health']:
                    if not stream:
                        log.error(f'HEALTHCHECK FAILED: {cfg["url"]}')

                        apobj = util.get_apobj(args.apprise)
                        apobj.notify(title='[HEALTHCHECK FAILED]', body=cfg['url'])
                    else:
                        log.debug(f'health ok: {ch}')

                elif stream:
                    log.debug(f'start recording: {ch}', cfg=cfg)

                    if cfg['delete']:
                        config.parse_configs(files, cfg, args=args)

                    rec_args = {
                        'cfg': cfg,
                        'stop_event': unload,
                        'output_dir': args.output,
                        'proxy_url': proxy,
                        'cookies_txt': args.cookies,
                        'bgutil_url': args.bgutil,
                        'apprise_obj': util.get_apobj(args.apprise),
                        #
                        'yta': args.yta,
                        'dlp': args.dlp,
                        #
                        'str_args': args.str_args,
                        'dlp_args': args.dlp_args,
                        'yta_args': args.yta_args,
                    }

                    t = threading.Thread(
                        target=record,
                        name=cfg['url'],
                        kwargs=rec_args,
                    )
                    t.start()

                log.trace(
                    '%s / %s | %s is streaming.'
                    % (i, len(channels), threading.active_count() - 1),
                    threads=get_threads(),
                )

                for i in range(args.delay):
                    if util.sum_mtime(files) == mtimes:
                        time.sleep(1)

    except KeyboardInterrupt:
        unload.set()

        if threading.active_count():
            log.warning('stopping...')
            while threading.active_count() > 1:
                time.sleep(1)
                log.trace('stopping...', threads=get_threads())

        sys.exit(0)
