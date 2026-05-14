#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import re
import shutil
import subprocess as sp
import threading
import time
from pathlib import Path

from loguru import logger as log

from . import config, record, util

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
        log.trace('thread RUNNING', name=name, threads=threads)
        return True

    log.trace('thread not running', name=name, threads=threads)
    return False


def is_live(
    url,
    chk_method: str = 'dlp',
    proxy_url: str = '',
    cookies_txt: str = '',
    regex_title: str = '',
    regex_desc: str = '',
):
    if 'youtube' in url and 'watch?v=' not in url:
        url += '/live'

    match chk_method:
        case 'dlp':
            cmd = [
                'yt-dlp',
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

            cmd += [url]

        case 'str':
            cmd = [
                'streamlink', 
                '--loglevel', 'trace', 
                '--url', url
            ]  # fmt: skip

            if proxy_url:
                cmd += ['--http-proxy', proxy_url]

            if Path(cookies_txt).is_file():
                cmd += ['--http-cookies-file', cookies_txt]

            if regex_title or regex_desc:
                cmd += ['--json']

        case _:
            log.error(
                f'is_live: invalid checker ({chk_method})',
                url=url,
                proxy=proxy_url,
                cookies_txt=cookies_txt,
            )
            return False

    with sp.Popen(
        cmd,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    ) as proc:
        stdout, stderr = proc.communicate()
        online = proc.poll() == 0
        output = util.fesc(stdout + stderr)

        if online and chk_method == 'dlp':
            try:
                c_json = json.loads(stdout)
                online = c_json.get('is_live') or False
            except:  # noqa: E722
                log.exception(
                    f'dlp_is_live: failed to convert json info\n{output}',
                    cfg=url,
                    cmd=cmd,
                )
                return False

        log.trace(
            f'{chk_method}: {online}\n{output}',
            url=url,
            proxy=proxy_url,
            cookies_txt=cookies_txt,
            cmd=cmd,
        )

        if online and (regex_title or regex_desc):
            try:
                c_json = json.loads(stdout)
            except:  # noqa: E722
                log.exception(
                    f'regex: failed to convert json info\n{output}',
                    cfg=url,
                    cmd=cmd,
                )
                return False

            title = c_json.get('metadata', {}).get('title') or c_json.get('title')
            desc = c_json.get('metadata', {}).get('title') or c_json.get('description')

            if chk_method == 'dlp' and c_json.get('extractor') == 'twitch:stream':
                title = desc

            if regex_title and title and re.findall(regex_title.lower(), title.lower()):
                log.trace(
                    f'title matched the regex: {url}',
                    regex_title=regex_title.lower(),
                    title=title.lower(),
                )
                return True

            if regex_desc and desc and re.findall(regex_desc.lower(), desc.lower()):
                log.trace(
                    f'desc matched the regex: {url}',
                    regex_desc=regex_desc.lower(),
                    desc=desc.lower(),
                )
                return True

            log.trace(
                f'does not match the regex: {url}',
                regex_title=regex_title.lower(),
                title=title.lower(),
                regex_desc=regex_desc.lower(),
                desc=desc.lower(),
            )
            return False

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
        return 1

    if not args.input and not args.urls:
        log.critical('no channel lists, add some with "-i" argument')
        return 1

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
                    return 1

                _sleep()
                continue

            for i, (ch, cfg) in enumerate(channels.items(), start=1):
                if util.sum_mtime(args.input) != mtimes:
                    log.info(
                        'list updated!', old=mtimes, new=util.sum_mtime(args.input)
                    )
                    break

                if is_running(cfg['url']):
                    if len(channels) == threading.active_count() - 1:
                        log.debug(
                            'everything is online',
                            threads=get_threads(),
                        )
                        _sleep()
                    continue

                stream = is_live(
                    url=cfg['url'],
                    chk_method=cfg['checker'],
                    proxy_url=cfg['proxy'],
                    cookies_txt=cfg['cookies'],
                    regex_title=cfg['regex_title'],
                    regex_desc=cfg['regex_desc'],
                )

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

                    t = threading.Thread(
                        target=record.main,
                        name=cfg['url'],
                        kwargs={
                            # cfg args
                            'url': cfg['url'],
                            'quality': cfg['quality'],
                            'output': cfg['output'],
                            'folder': cfg['folder'],
                            'proxy': cfg['proxy'],
                            'apprise': cfg['apprise'],
                            'cookies': cfg['cookies'],
                            'bgutil': cfg['bgutil'],
                            'recorder': cfg['recorder'],
                            'arguments': cfg['arguments'],
                            # non-cfg args
                            'event': unload,
                        },
                    )
                    t.start()

                log.debug(
                    '%s / %s | %s is streaming.'
                    % (i, len(channels), threading.active_count() - 1),
                    threads=get_threads(),
                )

                if os.environ.get('YK_DBG_COOKIES') and Path(cfg['cookies']).is_file():
                    import hashlib

                    md5 = hashlib.md5()

                    with open(cfg['cookies'], 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b''):
                            md5.update(chunk)

                    log.warning(f'{cfg["cookies"]}: {md5.hexdigest()}')

                _sleep()

                # rate-limit for single-item config
                # if len(channels) == 1:
                #    _sleep()

            first_launch = False

    except KeyboardInterrupt:
        unload.set()
        log.warning('stopping...')

        while threading.active_count() > 1:
            time.sleep(1)
            log.trace('stopping...', threads=get_threads())

        return 0
