#!/usr/bin/env python3
from contextlib import suppress
from pathlib import Path
import json
import shlex
import threading
import time
import os
import sys
import datetime
import subprocess
import signal
import re
import jc
import argparse
import random

from loguru import logger as log
import requests
import psutil
import yt_dlp
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
    "--live-from-start",
    "--merge-output-format", "mp4",
    "--retries", "30",
    "-N", "3"
]  # fmt: skip

_c_ytarchive = [
    "ytarchive",
    "--threads", "3",
    "--trace",
    "--verbose",
    "--no-frag-files",
    "--no-save-state",
    "--write-mux-file",
    "--no-merge",
    '--debug',
    '--thumbnail',
    '--add-metadata',
]  # fmt: skip


def ntfy(title, text, url=''):
    if not args.ntfy:  # https://ntfy.sh/docs
        return

    with suppress(Exception):
        requests.post(
            'https://ntfy.sh/' + args.ntfy_id,
            timeout=10,
            data=text.encode(encoding='utf-8'),
            headers={
                'title': title.encode(encoding='utf-8'),
                'click': url.encode(encoding='utf-8'),
            },
        )


def dump_stream(str_dict):
    start_time = time.time()

    with yt_dlp.YoutubeDL(ytdlp_config) as y:
        if args.proxy:
            ytdlp_config['proxy'] = random.choice(args.proxy)
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
            proxy=random.choice(args.proxy) if args.proxy else None,
        )

    # saving stream info
    str_info = json.dumps(str_json, indent=5, ensure_ascii=False, sort_keys=True)
    with open(str_blank + '.info', 'w', encoding='utf-8') as f:
        f.write(str(str_info))

    # notify
    ntfy(f'{str_user} is online.', str_title, str_json['webpage_url'])

    log.success(f'[online] ({str_user} - {str_title})')

    c_str = _c_streamlink.copy()
    c_str += [
        '--url', str_dict['url'],
        '--output', str_blank + '.ts',
        '--default-stream', str_dict['quality'],
    ]  # fmt: skip
    if args.proxy:
        c_str += ['--http-proxy', random.choice(args.proxy)]

    if args.dlp:
        c_str = _c_ytdlp.copy()
        c_str += ['-o', str_blank + '.mp4', str_dict['url']]

        if 'twitch' in str_json['extractor']:
            c_str.insert(1, '--no-live-from-start')

        if args.proxy:
            c_str.insert(1, '--proxy')
            c_str.insert(2, random.choice(args.proxy))

    if args.yta and 'youtube' in str_json['extractor']:
        c_str = _c_ytarchive.copy()
        c_str += [
            '--output', str_blank,
            str_dict['url'],
            str_dict['quality'],
        ]  # fmt: skip
        if args.proxy:
            c_str.insert(1, '--proxy')
            c_str.insert(2, random.choice(args.proxy))

    c_chat = [
        'chat_downloader', 
        '--output', str_blank + '.json',
        '--max_attempts', '99999999', 
        str_json['webpage_url']
    ]  # fmt: skip
    if args.proxy:
        c_chat.insert(1, '--proxy')
        c_chat.insert(2, random.choice(args.proxy))

    log.trace(c_str)

    # str process
    str_txt = open(str_blank + '.log', 'a')
    str_proc = subprocess.Popen(c_str, stdout=str_txt, stderr=str_txt)
    str_pid = psutil.Process(str_proc.pid)

    # chat process
    chat_txt = open(str_blank + '.chat', 'w')
    chat_proc = subprocess.Popen(c_chat, stdout=chat_txt, stderr=chat_txt)
    chat_pid = psutil.Process(chat_proc.pid)

    threads.append(str_dict['url'])

    while not unload:
        time.sleep(1)

        if not str_pid.is_running():
            break

        if not util.WINDOWS and str_pid.status() == psutil.STATUS_ZOMBIE:
            break

    end_time = datetime.timedelta(seconds=int(f'{time.time() - start_time:.{0}f}'))

    threads.remove(str_dict['url'])

    if str_pid.is_running():
        if unload:
            os.kill(str_proc.pid, signal.SIGTERM)
        else:
            os.waitpid(str_proc.pid, 0)
            ntfy(
                f'{str_user} is offline. [{end_time}]',
                str_title,
                str_json['webpage_url'],
            )

        log.info(f'[offline] ({str_user} - {str_title}) ({end_time})')

    # manual merging
    if args.yta and 'youtube' in str_json['extractor']:
        c_merge = 'echo =C'
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
        jc.conv(str_blank + '.json')
    except Exception as ex:
        log.error(f'jc error: {str(ex)}')

    str_dir.rename(args.output / str_name)


def check_live(url):
    c = ['streamlink', '--twitch-disable-hosting', '--url', url]
    if args.proxy:
        c += ['--http-proxy', random.choice(args.proxy)]

    with subprocess.Popen(c, stdout=subprocess.PIPE) as proc:
        while True:
            time.sleep(0.1)
            p = proc.poll()
            if p is not None:
                return p == 0


def dump_list(files):
    r = []

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

                if len(split) > 1:
                    quality = split[1]

                if len(split) > 2:
                    regex = split[2]

                if 'youtube' in url and 'watch?v=' not in url:
                    url += '/live'

                r.append({'url': url, 'regex': regex, 'quality': quality})

    # remove dubs
    return list({json.dumps(d, sort_keys=True): d for d in r}.values())


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    add = ap.add_argument

    # fmt: off
    add('-o', '--output', type=Path, default='.', help='stream output folder')
    add('-l', '--log', type=Path, default='.', help='log output folder')
    add('-d', '--delay', type=int, default=10, help='streams check delay')
    add('-s', '--src', nargs='+', default=['list.txt'], help='files with channels/streams (list1.txt, list2.txt)')
    add('-p', '--proxy', nargs='+', default=[], help='proxies (socks5://user:pass@127.0.0.1:1080)')
    add('--ntfy', type=str, help='ntfy.sh channel')
    add('--dlp', action='store_true', help='use yt-dlp instead of streamlink')
    add('--yta', action='store_true', help='use ytarchive for youtube streams')
    add('-v', '--verbose', action='store_true', help='verbose output (traces)')
    # fmt: on

    args = ap.parse_args()

    log_path = args.log / util.dt_now('%Y-%m-%d.log')
    log.add(log_path, encoding='utf-8')

    if args.verbose:
        log.remove()
        log.add(sys.stderr, level='TRACE')
        log.add(log_path, level='TRACE', encoding='utf-8')

    if not dump_list(args.src):
        util.die('no channels in files')

    args.output.mkdir(parents=True, exist_ok=True)

    # for binaries in project folder
    pwdir = Path(__file__).resolve().parent
    os.environ['PATH'] = os.pathsep.join([str(pwdir), os.environ['PATH']])

    try:
        while True:
            channels = dump_list(args.src)

            if not channels:
                log.error('no channels for monitoring')
                break

            for ch in channels:
                if ch['url'] not in threads and check_live(ch['url']):
                    T = threading.Thread(target=dump_stream, args=(ch,))
                    T.start()

                s = '%s / %s | %s is streaming.'
                log.trace(s % (channels.index(ch) + 1, len(channels), len(threads)))

                time.sleep(args.delay)

    except KeyboardInterrupt:
        if threads:
            unload = True
            log.warning('Stopping...')
            while threading.active_count() > 1:
                time.sleep(1)
