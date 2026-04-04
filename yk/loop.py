#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
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


def dlp_is_live(url, proxy_url: str = '', cookies_txt: Path = Path()):
    if 'youtube' in url and 'watch?v=' not in url:
        url += '/live'

    cmd = [
        '--dump-json', 
        '--no-playlist',
        '--playlist-items', "1",
        '--remote-components', 'ejs:github'
    ]  # fmt: skip

    if proxy_url:
        cmd += ['--proxy', proxy_url]

    if cookies_txt.is_file():
        cmd += ['--cookies', str(cookies_txt)]

    cmd += [url]

    with sp.Popen(
        ['yt-dlp'] + cmd,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    ) as proc:
        stdout, stderr = proc.communicate()
        output = util.fesc(stdout + stderr)
        online = False

        if proc.poll() == 0:
            try:
                c_json = json.loads(stdout)
                online = c_json.get('is_live') or False
            except:  # noqa: E722
                log.exception(
                    f'failed to convert json info\n{output}', cfg=url, cmd=cmd
                )

        log.trace(
            f'dlp_is_live: {online}\n{output}',
            url=url,
            proxy=proxy_url,
            cookies_txt=cookies_txt,
        )

        return online


def str_is_live(url, proxy_url: str = '', cookies_txt: Path = Path()):
    if 'youtube' in url and 'watch?v=' not in url:
        url += '/live'

    cmd = ['--loglevel', 'trace', '--url', url]

    if proxy_url:
        cmd += ['--http-proxy', proxy_url]

    if cookies_txt.is_file():
        cmd += ['--http-cookies-file', str(cookies_txt)]

    with sp.Popen(
        ['streamlink'] + cmd,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    ) as proc:
        stdout, stderr = proc.communicate()

        online = proc.poll() == 0

        output = util.fesc(stdout + stderr)

        log.trace(
            f'str_is_live: {online}\n{output}',
            url=url,
            proxy=proxy_url,
            cookies_txt=cookies_txt,
            cmd=cmd,
        )
        return online


def main(args):
    if args.rec == 'yta' and not shutil.which('ytarchive'):
        log.warning('ytarchive not found, fallback to yt-dlp')
        args.rec == 'dlp'

    if (args.rec == 'dlp' or args.chk == 'dlp') and not shutil.which('yt-dlp'):
        log.warning('yt-dlp not found, fallback to streamlink')
        args.rec == 'str'

    if args.rec == 'dlp' and not shutil.which('ffmpeg'):
        log.warning('ffmpeg not found, fallback to streamlink')
        args.rec == 'str'

    if (args.rec == 'str' or args.chk == 'str') and not shutil.which('streamlink'):
        log.critical('streamlink not found, cannot continue')
        sys.exit(1)

    if not args.input:
        log.critical('no channel lists, add some with "-i" argument')
        sys.exit(1)

    gf = util.get_files(args.input, exts=['.toml'])
    if not gf:
        log.critical('no .toml files found', dir=args.input)
        sys.exit(1)

    pc = config.parse_configs(gf, args=args)
    if not pc:
        log.critical('empty config files')
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
                stream = None

                match cfg['check']:
                    case 'str':
                        stream = str_is_live(cfg['url'], proxy, args.cookies)

                    case 'dlp':
                        stream = dlp_is_live(cfg['url'], proxy, args.cookies)

                    case _:
                        log.error(f'invalid chk: {cfg["check"]}')
                        continue

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
                    }

                    t = threading.Thread(
                        target=record,
                        name=cfg['url'],
                        kwargs=rec_args,
                    )
                    t.start()

                log.debug(
                    '%s / %s | %s is streaming.'
                    % (i, len(channels), threading.active_count() - 1),
                    threads=get_threads(),
                )

                def sleep():
                    for i in range(args.delay):
                        if util.sum_mtime(files) == mtimes:
                            time.sleep(1)

                sleep()

                if len(channels) == 1:  # rate-limit for single-item config
                    sleep()

    except KeyboardInterrupt:
        unload.set()

        if threading.active_count():
            log.warning('stopping...')
            while threading.active_count() > 1:
                time.sleep(1)
                log.trace('stopping...', threads=get_threads())

        sys.exit(0)
