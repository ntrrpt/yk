#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import random
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import apprise
import psutil
import requests
import yt_dlp
from loguru import logger as log
from stopwatch import Stopwatch

import jc
import util

threads = []
unload = False

ytdlp_config = {
    'quiet': True,
    'playlist_items': 0,
    'noplaylist': True
}  # fmt: skip

_c_streamlink = [
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

_c_ytdlp = [
    "yt-dlp",
    "--verbose",
    "--ignore-config",
    "--merge-output-format", "mp4",
    "--retries", "30",
    "-N", "3"
]  # fmt: skip

_c_ytarchive = [
    "ytarchive",
    "--threads", "3",
    "--trace",
    "--no-frag-files",
    "--no-save-state",
    "--write-mux-file",
    "--no-merge",
    '--add-metadata'
]  # fmt: skip


def dump_stream(str_dict):
    global unload

    str_proxy = random.choice(args.proxy) if args.proxy else None

    if str_proxy:
        ytdlp_config['proxy'] = str_proxy

    if args.cookies.is_file():
        ytdlp_config['cookiefile'] = args.cookies

    if 'youtube' in str_dict['url'] and 'watch?v=' not in str_dict['url']:
        str_dict['url'] += '/live'

    with yt_dlp.YoutubeDL(ytdlp_config) as y:
        str_json = y.extract_info(str_dict['url'], download=False)

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

    if str_dict['regex']:
        regex = str_dict['regex'].lower()

        re_title = re.findall(regex, str_title.lower())
        re_desc = re.findall(regex, str_json['description'].lower())

        if not re_title and not re_desc:
            return

    str_name = f'[{util.dt_now()}] {str_user} - {str_title}'
    str_name = util.esc(str_name)

    str_dir = args.output / f'[live] {str_name}'
    str_dir.mkdir(parents=True, exist_ok=True)

    str_blank = str(str_dir / str_name)

    # dump preview image
    if 'youtube' in str_json['extractor']:
        util.yt_dump_thumb(
            path=str_blank + '.jpg',
            video_id=str_json['id'],
            proxy=str_proxy,
        )

    # saving stream info
    str_info = json.dumps(str_json, indent=5, ensure_ascii=False, sort_keys=True)
    with open(str_blank + '.info', 'w', encoding='utf-8') as f:
        f.write(str(str_info))

    apobj.notify(title=f'[ONLINE] {str_user}', body=str_title)

    log.success(f'[ONLINE] ({str_user} - {str_title})')

    c = _c_streamlink.copy()
    c += util.http_cookies(args.cookies)
    c += [
        '--url', str_dict['url'],
        '--output', str_blank + '.ts',
        '--default-stream', str_dict['quality']
    ]  # fmt: skip

    if str_proxy:
        c += ['--http-proxy', str_proxy]

    if args.dlp:
        c = _c_ytdlp.copy()
        c += ['-o', str_blank + '.mp4', str_dict['url']]

        if 'youtube' in str_json['extractor']:
            c.insert(1, '--live-from-start')

        if str_proxy:
            c.insert(1, '--proxy')
            c.insert(2, str_proxy)

        if args.cookies.is_file():
            c.insert(1, '--cookies')
            c.insert(2, str(args.cookies))

    if args.yta and 'youtube' in str_json['extractor']:
        c = _c_ytarchive.copy()
        c += [
            '--output', str_blank,
            str_dict['url'],
            str_dict['quality'],
        ]  # fmt: skip

        if str_proxy:
            c.insert(1, '--proxy')
            c.insert(2, str_proxy)

        if args.cookies.is_file():
            c.insert(1, '--cookies')
            c.insert(2, str(args.cookies))

        try:
            r = requests.get(args.bgutil + '/ping', timeout=10)
            r.raise_for_status()

            bg = r.json()
            if any(['server_uptime' not in bg, 'version' not in bg]):
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

            log.trace(f'potoken: {bg["poToken"]}')

            c.insert(1, '--potoken')
            c.insert(2, bg['poToken'])

        except Exception as ex:
            log.warning(f'bgutil | {str(ex)}')

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

    log.trace(' '.join(c))
    log.trace(' '.join(c_chat))

    # str process
    str_txt = open(str_blank + '.log', 'a')
    str_proc = subprocess.Popen(c, stdout=str_txt, stderr=str_txt, cwd=str_dir)
    str_pid = psutil.Process(str_proc.pid)

    # chat process
    chat_txt = open(str_blank + '.chat', 'w')
    chat_proc = subprocess.Popen(c_chat, stdout=chat_txt, stderr=chat_txt, cwd=str_dir)
    chat_pid = psutil.Process(chat_proc.pid)

    threads.append(str_dict['url'].removesuffix('/live'))

    sw = Stopwatch(2)
    sw.restart()

    while not unload:
        time.sleep(1)

        if not str_pid.is_running():
            break

        if str_pid.status() == psutil.STATUS_ZOMBIE:
            break

    total_time = datetime.timedelta(seconds=int(sw.duration))

    threads.remove(str_dict['url'].removesuffix('/live'))

    if str_pid.is_running():
        if unload:
            os.kill(str_proc.pid, signal.SIGTERM)
        else:
            os.waitpid(str_proc.pid, 0)
            apobj.notify(title=f'[offline] {str_user} ({total_time})', body=str_title)

        log.info(f'[offline] ({str_user} - {str_title}) ')

    # manual merging
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

        # merge video and audio
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

    if chat_pid.is_running():
        if chat_pid.status() == psutil.STATUS_ZOMBIE:
            os.waitpid(chat_proc.pid, 0)
        if chat_pid.is_running():
            os.kill(chat_proc.pid, signal.SIGTERM)

    chat_txt.close()
    str_txt.close()

    try:
        jc.main(str_blank + '.json')
    except Exception as ex:
        log.error(f'jc: {str(ex)}')

    str_dir.rename(args.output / str_name)


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


def get_channels(files):
    channels = []

    for file in files:
        if not Path(file).is_file():
            log.error(f'{file} not exists')
            continue

        with open(file) as f:
            for line in f:
                line = line.rstrip()
                if not line or line.startswith('#'):
                    continue

                split = line.split()

                url = split[0]
                regex = ''
                quality = 'best'
                delete = False

                if len(split) > 1:
                    quality = split[1]

                    g = [
                        args.yta,
                        quality not in util.yta_q,
                        'youtube' in url or 'youtu.be' in url,
                    ]

                    if all(g):
                        log.critical(f'{quality!r} not supported in ytarchive')
                        log.info(f'choose something from {", ".join(util.yta_q)!r}')

                        if not threads:
                            sys.exit(1)

                if len(split) > 2:
                    regex = split[2]

                if url.startswith('@'):
                    url = url.removeprefix('@')
                    delete = True

                ch = {'url': url, 'regex': regex, 'quality': quality, 'delete': delete}
                if ch not in channels:
                    channels.append(ch)

    return channels


def loop():
    global unload

    try:
        while True:
            files = util.get_files(args.src, exts=['.txt'])
            if not files:
                log.error('no files for monitoring')
                time.sleep(args.delay)

            channels = get_channels(files)
            mtimes = util.sum_mtime(files)

            for ch in channels:
                if util.sum_mtime(files) != mtimes:
                    log.info('list updated!')
                    break

                if ch['url'] not in threads and check_live(ch['url']):
                    if ch['delete']:
                        for src in files:
                            util.remove_all_exact(src, ch['url'])

                        log.info(f'removed {ch["url"]!r}')

                    T = threading.Thread(target=dump_stream, args=(ch,))
                    T.start()

                s = '%s / %s | %s is streaming.'
                log.trace(s % (channels.index(ch) + 1, len(channels), len(threads)))

                for i in range(args.delay):
                    if util.sum_mtime(files) == mtimes:
                        time.sleep(1)

    except KeyboardInterrupt:
        if threads:
            unload = True
            log.warning('Stopping...')
            while threading.active_count() > 1:
                time.sleep(1)

        sys.exit(0)


if __name__ == '__main__':
    apobj = apprise.Apprise()

    arg = argparse.ArgumentParser()
    add = arg.add_argument
    evg = os.environ.get

    # fmt: off
    add('-o', '--output', type=Path, default=Path(evg("YK_OUTPUT", '.')),   help='stream output folder')
    add('-l', '--log',    type=Path, default=Path(evg("YK_LOG", '.')), help='log output folder')
    add('-d', '--delay',  type=int,  default=int(evg("YK_DELAY", 15)),      help='streams check delay')

    add('-s', '--src',     nargs='+', default=[], help='files with channels/streams (list1.txt, /root/list2.txt)')
    add('-p', '--proxy',   nargs='+', default=[], help='proxies (socks5://user:pass@127.0.0.1:1080)')
    add('-a', '--apprise', nargs='+', default=[], help='apprise configs (.yml)')

    add('-c', '--cookies', type=Path, default=Path(evg("YK_COOKIES", '')),                    help='path to cookies.txt (netscape format)')
    add('-b', '--bgutil',  type=str,  default=str(evg("YK_BGUTIL", 'http://127.0.0.1:4416')), help='bgutil-ytdlp-pot-provider url')

    add('--dlp',           action='store_true', help='use yt-dlp instead of streamlink')
    add('--yta',           action='store_true', help='use ytarchive for youtube streams')
    add('-v', '--verbose', action='store_true', help='verbose output (traces)')
    # fmt: on

    args = arg.parse_args()
    args.output = args.output.resolve()  # subprocess pwd fix

    if args.log.is_dir():
        args.log = args.log / util.dt_now('%Y-%m-%d.log')
    elif args.log.suffix in ['.txt', '.log']:
        args.log = args.log

    log.remove()
    if args.verbose:
        log.add(sys.stderr, level='TRACE')
        log.add(args.log, level='TRACE', encoding='utf-8')
    else:
        guru_fmt = '<level>[{time:YYYY-MM-DD HH:mm:ss}]</level> {message}'
        log.add(sys.stderr, format=guru_fmt)
        log.add(args.log, format=guru_fmt, encoding='utf-8')

    for var, target in [
        ('YK_OUTPUT', args.output),
        ('YK_LOG', args.log),
        ('YK_DELAY', args.delay),
        ('YK_COOKIES', args.cookies),
        ('YK_BGUTIL', args.bgutil),
    ]:
        log.trace(f'{var}: {target}')

    for var, target in [
        ('YK_ARGS_STREAMLINK', _c_streamlink),
        ('YK_ARGS_YTDLP', _c_ytdlp),
        ('YK_ARGS_YTARCHIVE', _c_ytarchive),
        ('YK_SRC', args.src),
        ('YK_PROXIES', args.proxy),
        ('YK_APPRISE', args.apprise),
    ]:
        env = evg(var, '')
        if env:
            target += env.split()
        log.trace(f'{var}: {target}')

    if not args.src:
        util.die('no channel lists, add some with "--src" argument')

    if args.apprise:
        cfg = apprise.AppriseConfig()
        for file in util.get_files(args.apprise, exts=['.yml']):
            cfg.add(str(file))
        apobj.add(cfg)

    args.output.mkdir(parents=True, exist_ok=True)

    # for binaries in project folder
    pwdir = Path(__file__).resolve().parent
    os.environ['PATH'] = os.pathsep.join([str(pwdir), os.environ['PATH']])

    loop()
