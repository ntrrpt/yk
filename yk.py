#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import random
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path
from pprint import pformat as pf

import apprise
import psutil
import requests
import tomli_w
import yt_dlp
from loguru import logger as log
from stopwatch import Stopwatch
from tabulate import tabulate
from validators import url as is_url

import jc
import util

CONFIG = {}
ONLINE = []
UNLOAD = False

YTDLP_CONFIG = {
    'quiet': True,
    'playlist_items': 0,
    'noplaylist': True,
    'remote_components': ['ejs:github']
}  # fmt: skip

C_STREAMLINK = [
    "streamlink",
    "--fs-safe-rules", "Windows",
    "--twitch-disable-ads",
    "--hls-live-restart",
    "--http-timeout", "180",
    "--stream-segment-threads", "2",
    "--stream-segment-timeout", "180",
    "--stream-segment-attempts", "300",
    "--hls-segment-ignore-names", "preloading",
    "--hls-playlist-reload-attempts", "30",
    "--hls-live-edge", "5",
    "--stream-timeout", "120",
    "--ringbuffer-size", "64M",
    "--loglevel", "trace",
    "--twitch-disable-hosting"
]  # fmt: skip

C_YTDLP = [
    "yt-dlp",
    "--verbose",
    "--ignore-config",
    "--remote-components", "ejs:github",
    "--merge-output-format", "mp4",
    "--retries", "30",
    "-N", "3"
]  # fmt: skip

C_YTARCHIVE = [
    "ytarchive",
    "--threads", "3",
    "--trace",
    "--no-frag-files",
    "--no-save-state",
    "--write-mux-file",
    "--no-merge",
    '--add-metadata'
]  # fmt: skip


def dump_stream(cfg: dict):
    """
    cfg_example = {'delete': False,
                   'folder': '',
                   'quality': 'best',
                   'regex_desc': None,
                   'regex_title': None,
                   'url': 'https://www.twitch.tv/akirosenthal_hololive'}
    """

    global UNLOAD, YTDLP_CONFIG

    # getting random proxy for all 'dump_stream' func
    str_proxy = random.choice(args.proxy) if args.proxy else None

    if str_proxy:
        YTDLP_CONFIG['proxy'] = str_proxy

    if args.cookies.is_file():
        YTDLP_CONFIG['cookiefile'] = args.cookies

    if args.bgutil != 'http://127.0.0.1:4416':
        YTDLP_CONFIG['extractor_args'] = {
            'youtubepot-bgutilhttp': {'base_url': [args.bgutil]}
        }

    # += '/live' for channel links
    if 'youtube' in cfg['url'] and 'watch?v=' not in cfg['url']:
        cfg['url'] += '/live'

    # getting livestream info
    with yt_dlp.YoutubeDL(YTDLP_CONFIG) as y:
        str_json = y.extract_info(cfg['url'], download=False)

    # getting username and livestream title for files
    match str_json['extractor']:
        case 'youtube':
            str_title = str_json['title'][:-17]
            str_user = str_json['uploader']

        case 'twitch:stream':
            str_title = str_json['description']
            str_user = str_json['uploader']

        case 'wasdtv:stream':
            str_title = str_json['fulltitle']
            str_user = str_json['webpage_url_basename']

        case _:
            str_title = str_json['title']
            str_user = str_json['uploader']

    str_title = util.esc(str_title)
    str_user = util.esc(str_user)

    # regex filtering
    if cfg['regex_title']:
        if not re.findall(cfg['regex_title'].lower(), str_title.lower()):
            return

    if cfg['regex_desc'] and str_json.get('description'):
        if not re.findall(cfg['regex_desc'].lower(), str_json['description'].lower()):
            return

    # [YY_MM_DD hh_mm_ss] username - livestream title
    str_name = util.esc(f'[{util.dt_now()}] {str_user} - {str_title}')

    # folder for livestream
    str_dir = args.output / Path(util.esc(cfg['folder'])) / f'[live] {str_name}'
    str_dir.mkdir(parents=True, exist_ok=True)

    # template for livestream files (*.json, *.conv, *.log, ...)
    str_blank = str(str_dir / str_name)

    # download youtube thumb
    if 'youtube' in str_json['extractor']:
        util.yt_dump_thumb(
            path=str_blank + '.jpg',
            video_id=str_json['id'],
            proxy=str_proxy,
        )

    # saving stream info to json
    str_info = json.dumps(str_json, indent=5, ensure_ascii=False, sort_keys=True)
    with open(str_blank + '.info', 'w', encoding='utf-8') as f:
        f.write(str(str_info))

    # append 'online for HH:MM:SS' to notify
    since_str = ''
    rls_ts = str_json.get('release_timestamp')

    if rls_ts and (isinstance(rls_ts, int) or rls_ts.isdigit()):
        rls_dt = datetime.fromtimestamp(int(str_json['release_timestamp']))
        delta = datetime.now() - rls_dt
        since_str = f'\n(online for {util.timedelta_pretty(delta)})'

    # notify and log
    apobj.notify(title=f'[ONLINE] {str_user}', body=str_title + since_str)
    log.success(f'[ONLINE] ({str_user} - {str_title + since_str.replace("\n", " ")}')

    # streamlink cmd (default)
    c = C_STREAMLINK.copy() + util.http_cookies(args.cookies)
    c += [
        '--url', cfg['url'],
        '--output', str_blank + '.ts',
        '--default-stream', cfg['quality']
    ]  # fmt: skip

    if str_proxy:
        c += ['--http-proxy', str_proxy]

    # yt-dlp cmd
    if args.dlp:
        c = C_YTDLP.copy() + ['-o', str_blank + '.mp4', cfg['url']]

        if 'youtube' in str_json['extractor']:
            c.insert(1, '--live-from-start')

        if str_proxy:
            c.insert(1, '--proxy')
            c.insert(2, str_proxy)

        if args.cookies.is_file():
            c.insert(1, '--cookies')
            c.insert(2, str(args.cookies))

        if args.bgutil != 'http://127.0.0.1:4416':
            c.insert(1, '--extractor-args')
            c.insert(2, f'youtubepot-bgutilhttp:base_url={args.bgutil}')

    # ytarchive cmd
    if args.yta and 'youtube' in str_json['extractor']:
        c = C_YTARCHIVE.copy() + ['--output', str_blank, cfg['url'], cfg['quality']]  # fmt: skip

        if str_proxy:
            c.insert(1, '--proxy')
            c.insert(2, str_proxy)

        if args.cookies.is_file():
            c.insert(1, '--cookies')
            c.insert(2, str(args.cookies))

        # append potoken to ytarchive cmd
        # need 'https://github.com/Brainicism/bgutil-ytdlp-pot-provider/'
        try:
            r = requests.get(args.bgutil + '/ping', timeout=10)
            r.raise_for_status()

            bg = r.json()
            if 'server_uptime' not in bg or 'version' not in bg:
                raise Exception(f'invalid /ping: {bg}')

            r = requests.post(
                args.bgutil + '/get_pot',
                data={'proxy': str_proxy} if str_proxy else {},
                timeout=60,
            )
            r.raise_for_status()

            bg = r.json()
            if 'poToken' not in bg:
                raise Exception(f'invalid /get_pot: {bg}')

            log.debug(f'potoken: {bg["poToken"]}')

            c.insert(1, '--potoken')
            c.insert(2, bg['poToken'])

        except Exception as ex:
            log.warning(f'bgutil | {str(ex)}')

    # chat_downloader cmd
    c_chat = [
        'chat_downloader', 
        '--output', str_blank + '.json',
        '--max_attempts', '99999999', 
        str_json['webpage_url']
    ]  # fmt: skip

    if args.cookies.is_file():
        c_chat.insert(1, '--cookies')
        c_chat.insert(2, str(args.cookies))

    if str_proxy:
        c_chat.insert(1, '--proxy')
        c_chat.insert(2, str_proxy)

    log.debug(' '.join(c))
    log.debug(' '.join(c_chat))

    # video process
    str_txt = open(str_blank + '.log', 'a')
    str_proc = subprocess.Popen(c, stdout=str_txt, stderr=str_txt, cwd=str_dir)
    str_pid = psutil.Process(str_proc.pid)

    # chat process
    chat_txt = open(str_blank + '.chat', 'w')
    chat_proc = subprocess.Popen(c_chat, stdout=chat_txt, stderr=chat_txt, cwd=str_dir)
    chat_pid = psutil.Process(chat_proc.pid)

    # prevent same urls being processed
    ONLINE.append(cfg['url'].removesuffix('/live'))

    # measure livestream duration
    sw = Stopwatch(2)
    sw.restart()

    # looping until stream ended
    while not UNLOAD:
        time.sleep(1)

        if not str_pid.is_running():
            break

        if str_pid.status() == psutil.STATUS_ZOMBIE:
            break

    total_time = timedelta(seconds=int(sw.duration))

    ONLINE.remove(cfg['url'].removesuffix('/live'))

    # shutdown stream process
    if str_pid.is_running():
        if UNLOAD:
            os.kill(str_proc.pid, signal.SIGTERM)
        else:
            os.waitpid(str_proc.pid, 0)
            apobj.notify(title=f'[offline] {str_user} ({total_time})', body=str_title)

        log.info(f'[offline] ({str_user} - {str_title}) ')

    # manual ytarchive merging
    if args.yta and 'youtube' in str_json['extractor']:
        c_merge = '=C'
        files_to_delete = []

        for file in os.listdir(str_dir):
            if file.endswith('ffmpeg.txt'):
                file_path = str_dir / file
                file_content = open(file_path).read()
                c_merge = shlex.split(file_content)
                files_to_delete.append(file_path)

            if file.endswith('.ts'):
                file_path = str_dir / file
                files_to_delete.append(file_path)

        with subprocess.Popen(c_merge, stderr=str_txt) as proc:
            while True:
                time.sleep(1)
                p = proc.poll()

                if p == 0:
                    for file in files_to_delete:
                        util.delete(file)
                    break

                if p is not None:
                    log.error(f'merge error: {str_dir}')
                    break

    # shutdown chat process
    if chat_pid.is_running():
        if chat_pid.status() == psutil.STATUS_ZOMBIE:
            os.waitpid(chat_proc.pid, 0)
        if chat_pid.is_running():
            os.kill(chat_proc.pid, signal.SIGTERM)

    chat_txt.close()
    str_txt.close()

    # prettify chat .json
    try:
        jc.main(str_blank + '.json')
    except Exception as ex:
        log.error(f'jc error: {str(ex)}')

    # remove [live] prefix
    str_dir.rename(args.output / Path(util.esc(cfg['folder'])) / str_name)


def check_live(url):
    if 'youtube' in url and 'watch?v=' not in url:
        url += '/live'

    c = ['streamlink', '--twitch-disable-hosting', '--url', url]
    c += util.http_cookies(args.cookies)

    if args.proxy:
        c += ['--http-proxy', random.choice(args.proxy)]

    with subprocess.Popen(c, stdout=subprocess.PIPE) as proc:
        while True:
            time.sleep(0.1)
            p = proc.poll()
            if p is not None:
                return p == 0


def parse_configs(files: list = [], cfg_to_del: dict = {}):
    tomls = []

    for file in files:
        toml = {}

        #########################
        ## toml validation

        try:
            with open(file, 'rb') as f:
                toml = tomllib.load(f)

            assert toml  # empty check

        except tomllib.TOMLDecodeError as ex:
            log.error(f'toml decode error in {file!r}, {ex}')
            continue

        except FileNotFoundError as ex:
            log.error(f"file {file!r} not found', {ex}")
            continue

        except AssertionError:
            log.error(f'file {file!r} is empty')
            continue

        except Exception as ex:
            log.error(f'file error in {file!r}, {ex}')
            continue

        # log.trace(f'stock {file}:\n' + pf(toml))

        #########################
        ## finding single-use items via '@' prefix in key

        for item in toml.copy().keys():
            if toml[item].get('url') or toml[item].get('u'):
                continue

            if is_url(item):
                # key is url
                toml[item]['url'] = item

            elif is_url(item.removeprefix('!')):
                # !url => removing
                toml[item]['delete'] = True
                toml[item]['url'] = item.removeprefix('!')

            elif is_url(item.removeprefix('@')):
                # @url => healthcheck
                toml[item]['health'] = True
                toml[item]['url'] = item.removeprefix('@')

        #########################
        ## parsing remaining values

        for item, cfg in toml.copy().items():
            toml[item]['url'] = cfg.get('url') or cfg.get('u') or ''
            toml[item]['folder'] = cfg.get('folder') or cfg.get('f') or ''
            toml[item]['quality'] = cfg.get('quality') or cfg.get('q') or 'best'
            toml[item]['delete'] = bool(cfg.get('delete') or cfg.get('d') or False)
            toml[item]['health'] = bool(cfg.get('health') or False)

            rgx = cfg.get('regex') or cfg.get('r') or ''
            toml[item]['regex_title'] = cfg.get('regex_title', rgx)
            toml[item]['regex_desc'] = cfg.get('regex_desc', rgx)

            if not toml[item]['url']:
                log.trace(f'{file}:{item}: empty url, skipping.')
                toml.pop(item)
                continue

            if not is_url(toml[item]['url']):
                log.warning(
                    f'{file}:{item}: {cfg["url"]!r} is not a valid url, skipping.'
                )
                toml.pop(item)
                continue

            for i in ('u', 'f', 'r', 'q', 'd'):
                if i in cfg:
                    del toml[item][i]

            if (
                args.yta
                and toml[item]['quality'] not in util.yta_q
                and ('youtube' in toml[item]['url'] or 'youtu.be' in toml[item]['url'])
            ):
                log.error(
                    f"{file}:{item}: {toml[item]['quality']!r} not supported in ytarchive, fallback to 'best' for now"
                )
                log.error(f'choose something from {", ".join(util.yta_q)!r}')
                toml[item]['quality'] = 'best'

        #########################
        ## deleting single-use items

        if cfg_to_del:
            with open(file, 'rb') as f:
                toml_or = tomllib.load(f)

            for item, cfg in toml_or.copy().items():
                if toml[item]['delete'] and toml[item]['url'] == cfg_to_del.get('url'):
                    toml_or.pop(item)

                    path = Path(file)
                    fst = path.stat()

                    with open(file, 'wb') as f:
                        tomli_w.dump(toml_or, f)

                    os.utime(path, (fst.st_atime, fst.st_mtime))

                    log.warning(f'removed {item!r}')
                    break

        log.trace(f'{file}:\n' + pf(toml))

        tomls.append(toml)

    # return merged dicts
    return reduce(lambda x, y: x | y, tomls)


def loop():
    global UNLOAD

    try:
        while True:
            files = util.get_files(args.src, exts=['.toml'])

            if not files:
                log.error('no files for monitoring')
                time.sleep(args.delay)

            channels = parse_configs(files)
            mtimes = util.sum_mtime(files)

            for i, (ch, cfg) in enumerate(channels.items(), start=1):
                if util.sum_mtime(files) != mtimes:
                    log.info('list updated!')
                    break

                if cfg['health']:
                    if not check_live(cfg['url']):
                        log.error(f'HEALTHCHECK FAILED: {cfg["url"]}')
                        apobj.notify(title='[HEALTHCHECK FAILED]', body=cfg['url'])
                    else:
                        log.debug(f'health ok: {ch}')

                elif cfg['url'] not in ONLINE and check_live(cfg['url']):
                    log.debug(f'{ch!r} is online:\n{pf(cfg)}')

                    if cfg['delete']:
                        parse_configs(files, cfg)

                    t = threading.Thread(target=dump_stream, args=(cfg,))
                    t.start()

                log.trace(
                    '%s / %s | %s is streaming.' % (i, len(channels), len(ONLINE))
                )

                for i in range(args.delay):
                    if util.sum_mtime(files) == mtimes:
                        time.sleep(1)

    except KeyboardInterrupt:
        if ONLINE:
            UNLOAD = True
            log.warning('Stopping...')
            while threading.active_count() > 1:
                time.sleep(1)

        sys.exit(0)


if __name__ == '__main__':
    #########################
    ## args

    arg = argparse.ArgumentParser()
    add = arg.add_argument
    evg = os.environ.get

    # fmt: off
    add('-o', '--output', type=Path, default=Path(evg("YK_OUTPUT", '.')), help='stream output folder')
    add('-l', '--log',    type=Path, default=Path(evg("YK_LOG", '.')),    help='log output folder')
    add('-d', '--delay',  type=int,  default=int(evg("YK_DELAY", 15)),    help='streams check delay')

    add('-s', '--src',     nargs='+', default=[], help='files with channels/streams (list1.toml, /root/list2.toml)')
    add('-p', '--proxy',   nargs='+', default=[], help='proxies (socks5://user:pass@127.0.0.1:1080)')
    add('-a', '--apprise', nargs='+', default=[], help='apprise configs (.yml)')

    add('-c', '--cookies', type=Path, default=Path(evg("YK_COOKIES", '')),                    help='path to cookies.txt (netscape format)')
    add('-b', '--bgutil',  type=str,  default=str(evg("YK_BGUTIL", 'http://127.0.0.1:4416')), help='bgutil-ytdlp-pot-provider url')

    add('--dlp', action='store_true', help='use yt-dlp instead of streamlink')
    add('--yta', action='store_true', help='use ytarchive for youtube streams')

    add('-v', '--debug', action='store_true', help='verbose output')
    add('--trace',       action='store_true', help='verbosest output')
    # fmt: on

    args = arg.parse_args()
    args.output = args.output.resolve()  # subprocess pwd fix

    #########################
    ## logging

    # logging in dir/%Y-%m-%d.log if --log=<dir>
    if args.log.is_dir():
        args.log = args.log / util.dt_now('%Y-%m-%d.log')

    log.remove()

    if args.debug or args.trace:
        lvl = 'TRACE' if args.trace else 'DEBUG'
        log.add(sys.stderr, level=lvl)
        log.add(args.log, level=lvl, encoding='utf-8')
    else:
        fmt = '<level>[{time:YYYY-MM-DD HH:mm:ss}]</level> {message}'
        log.add(sys.stderr, level='INFO', format=fmt)
        log.add(args.log, level='INFO', format=fmt, encoding='utf-8')

    #########################
    ## envs

    for var, target in [
        ('YK_ARGS_STREAMLINK', C_STREAMLINK),
        ('YK_ARGS_YTDLP', C_YTDLP),
        ('YK_ARGS_YTARCHIVE', C_YTARCHIVE),
        ('YK_SRC', args.src),
        ('YK_PROXIES', args.proxy),
        ('YK_APPRISE', args.apprise),
    ]:
        env = evg(var, '')
        if env:
            target += env.split()

    env_tab = [
        ['YK_ARGS_STREAMLINK', ' '.join(C_STREAMLINK)],
        ['YK_ARGS_YTDLP', ' '.join(C_YTDLP)],
        ['YK_ARGS_YTARCHIVE', ' '.join(C_YTARCHIVE)],
        ['------------------', ' '],
        ['YK_SRC', args.src],
        ['YK_PROXIES', args.proxy],
        ['YK_APPRISE', args.apprise],
        ['------------------', ' '],
        ['YK_OUTPUT', args.output],
        ['YK_LOG', args.log],
        ['YK_DELAY', args.delay],
        ['YK_COOKIES', args.cookies],
        ['YK_BGUTIL', args.bgutil],
    ]

    log.debug(
        'envs:\n'
        + tabulate(
            env_tab,
            colalign=('right', 'left'),
            tablefmt='plain',
            maxcolwidths=[None, 100],
        )
    )

    #########################
    ## apprise

    apobj = apprise.Apprise()

    if args.apprise:
        cfg = apprise.AppriseConfig()
        for file in util.get_files(args.apprise, exts=['.yml']):
            cfg.add(str(file))
        apobj.add(cfg)

    #########################
    ## binaries in project folder

    pwdir = Path(__file__).resolve().parent
    os.environ['PATH'] = os.pathsep.join([str(pwdir), os.environ['PATH']])

    if args.yta and not shutil.which('ytarchive'):
        log.warning('ytarchive not found, fallback to yt-dlp')
        args.yta = False
        args.dlp = True

    if (args.yta or args.dlp) and not shutil.which('ffmpeg'):
        log.warning('ffmpeg not found, fallback to streamlink')
        args.yta = False
        args.dlp = False

    #########################
    ## main loop

    if not args.src:
        util.die('no channel lists, add some with "--src" argument')

    gf = util.get_files(args.src, exts=['.toml'])
    if not gf:
        util.die('no .toml files')

    pc = parse_configs(gf)
    if not pc:
        util.die('no channels in configs')

    log.debug('conf:\n' + pf(pc))

    loop()
