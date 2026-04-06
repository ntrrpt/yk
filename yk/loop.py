#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import shutil
import subprocess as sp
import sys
import threading
import time
from pathlib import Path

from loguru import logger as log

from . import config, util
from .record import record

first_launch = True
unload = threading.Event()


def get_threads(raw: bool = False):
    threads = [x for x in threading.enumerate() if x.name != 'MainThread']

    if raw:
        return threads

    return [x.name for x in threads]


def is_running(name: str = ''):
    threads = get_threads()

    if name in threads:
        log.trace('thread running', name=name, threads=threads)
        return True

    log.trace('thread not running', name=name, threads=threads)
    return False


def dlp_is_live(url, proxy_url: str = '', cookies_txt: str = ''):
    if 'youtube' in url and 'watch?v=' not in url:
        url += '/live'

    cmd = [
        '--verbose',
        '--dump-json', 
        '--no-playlist',
        '--playlist-items', "1",
        '--remote-components', 'ejs:github'
    ]  # fmt: skip

    if proxy_url:
        cmd += ['--proxy', proxy_url]

    if Path(cookies_txt).is_file():
        cmd += ['--cookies', cookies_txt]

    with sp.Popen(
        ['yt-dlp'] + cmd + [url],
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    ) as proc:
        stdout, stderr = proc.communicate()
        online = False

        if proc.poll() == 0:
            try:
                c_json = json.loads(stdout)
                online = c_json.get('is_live') or False
            except:  # noqa: E722
                log.exception(
                    f'failed to convert json info\n{util.fesc(stdout + stderr)}',
                    cfg=url,
                    cmd=cmd,
                )

        log.trace(
            f'dlp_is_live: {online}\n{util.fesc(stderr)}',
            url=url,
            proxy=proxy_url,
            cookies_txt=cookies_txt,
        )

        return online


def str_is_live(url, proxy_url: str = '', cookies_txt: str = ''):
    if 'youtube' in url and 'watch?v=' not in url:
        url += '/live'

    cmd = ['--loglevel', 'trace', '--url', url]

    if proxy_url:
        cmd += ['--http-proxy', proxy_url]

    if Path(cookies_txt).is_file():
        cmd += ['--http-cookies-file', cookies_txt]

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
    global first_launch

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

    log.info('started!')

    try:
        while True:
            mtimes = util.sum_mtime(args.input)

            def _sleep():
                # sleeping, but checking for toml changes
                for i in range(args.delay):
                    if util.sum_mtime(args.input) == mtimes:
                        time.sleep(1)

            channels = config.parse(i=args.urls + args.input, args=args)
            if not channels:
                log.error('no channels for monitoring', input=args.input)
                if first_launch:
                    sys.exit(1)

                _sleep()
                continue

            log.error(util.pf(channels))

            for i, (ch, cfg) in enumerate(channels.items(), start=1):
                if util.sum_mtime(args.input) != mtimes:
                    log.info(
                        'list updated!', old=mtimes, new=util.sum_mtime(args.input)
                    )
                    break

                if is_running(cfg['url']):
                    continue

                stream = None

                match cfg['checker']:
                    case 'str':
                        stream = str_is_live(cfg['url'], cfg['proxy'], cfg['cookies'])

                    case 'dlp':
                        stream = dlp_is_live(cfg['url'], cfg['proxy'], cfg['cookies'])

                    case _:
                        log.error(f'invalid checker: {cfg["checker"]}', cfg=cfg)
                        continue

                if cfg['health']:
                    if not stream:
                        log.error(f'HEALTHCHECK FAILED: {cfg["url"]}')

                        apobj = util.get_apobj(cfg['apprise'])
                        apobj.notify(title='[HEALTHCHECK FAILED]', body=cfg['url'])
                    else:
                        log.debug(f'health ok: {ch}')

                elif stream:
                    log.debug(f'start recording: {ch}', cfg=cfg)

                    if cfg['delete']:
                        config.parse(
                            i=args.urls + args.input, args=args, cfg_to_del=cfg
                        )

                    cfg['event'] = unload
                    t = threading.Thread(
                        target=record,
                        name=cfg['url'],
                        kwargs=cfg,
                    )
                    t.start()

                log.debug(
                    '%s / %s | %s is streaming.'
                    % (i, len(channels), threading.active_count() - 1),
                    threads=get_threads(),
                )

                _sleep()

                if len(channels) == 1:
                    _sleep()  # rate-limit for single-item config

            first_launch = False

    except KeyboardInterrupt:
        unload.set()

        if threading.active_count():
            log.warning('stopping...')
            while threading.active_count() > 1:
                time.sleep(1)
                log.trace('stopping...', threads=get_threads())

        sys.exit(0)
