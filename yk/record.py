#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import re
import shlex
import signal
import subprocess as sp
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil
import requests
from loguru import logger as log
from stopwatch import Stopwatch

from jc.conv import conv as jc_conv

from .util import delete, dt_now, esc, fesc, timedelta_pretty, yt_dw_thumb


def record(
    cfg: dict,  # stream info
    stop_event: threading.Event,  # for graceful shutdown
    output_dir: str = '.',  # out
    proxy_url: str = '',  # TODO: strip '5h' for ytarchive
    cookies_txt: Path = Path(),  # cookie file in netscape format
    bgutil_url: str = 'http://127.0.0.1:4416',  # potoken provider (https://github.com/Brainicism/bgutil-ytdlp-pot-provider/)
    apprise_obj=None,  # apprise object (see util.get_apobj) # TODO: switch to ymls
):
    """
    cfg_example = {
        "url": "https://www.twitch.tv/ironmouse",
        "folder": "sick",
        "quality": "best",
        "delete": false,
        "health": false,
        "regex_title": "",
        "regex_desc": ""
    }
    """

    # += '/live' for channel links
    if 'youtube' in cfg['url'] and 'watch?v=' not in cfg['url']:
        cfg['url'] += '/live'

    c_info = [
        '--dump-json', 
        '--no-playlist',
        '--playlist-items', "1",
        '--remote-components', 'ejs:github'
    ]  # fmt: skip

    if proxy_url:
        c_info += ['--proxy', proxy_url]

    if cookies_txt.is_file():
        c_info += ['--cookies', str(cookies_txt)]

    if bgutil_url != 'http://127.0.0.1:4416':
        c_info += [
            '--extractor-args',
            f'youtubepot-bgutilhttp:base_url={bgutil_url}',
        ]

    c_info += [cfg['url']]
    str_raw = ''

    try:
        p = sp.run(
            ['yt-dlp'] + c_info,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        str_raw, _ = p.stdout, p.stderr
    except sp.CalledProcessError:
        cmd = ' '.join(c_info)
        out = fesc(p.stdout + p.stderr)

        log.error(f'failed to get info\n{out}', cfg=cfg, cmd=cmd)
        sys.exit(1)

    try:
        str_json = json.loads(str_raw)
    except:  # noqa: E722
        log.exception(
            f'failed to convert json info\n{str_raw}', cfg=cfg, cmd=cmd, raw=str_raw
        )
        sys.exit(1)

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

    str_title = esc(str_title)
    str_user = esc(str_user)

    # regex filtering
    if cfg['regex_title']:
        if not re.findall(cfg['regex_title'].lower(), str_title.lower()):
            sys.exit(0)

    if cfg['regex_desc'] and str_json.get('description'):
        if not re.findall(cfg['regex_desc'].lower(), str_json['description'].lower()):
            sys.exit(0)

    # [YY_MM_DD hh_mm_ss] username - livestream title
    str_name = esc(f'[{dt_now()}] {str_user} - {str_title}')

    # folder for livestream
    str_dir = output_dir / Path(esc(cfg['folder'])) / f'[live] {str_name}'
    str_dir.mkdir(parents=True, exist_ok=True)

    # template for livestream files (*.json, *.conv, *.log, ...)
    str_blank = str(str_dir / str_name)

    # saving stream info to json
    str_info = json.dumps(str_json, indent=5, ensure_ascii=False, sort_keys=True)
    with open(str_blank + '.info', 'w', encoding='utf-8') as f:
        f.write(str(str_info))

    # download youtube thumb
    if 'youtube' in str_json['extractor']:
        yt_dw_thumb(
            path=str_blank + '.jpg',
            video_id=str_json['id'],
            proxy=proxy_url,
        )

    # append 'online for HH:MM:SS' to notify
    since_str = ''
    rls_ts = str_json.get('release_timestamp')

    if rls_ts and (isinstance(rls_ts, int) or rls_ts.isdigit()):  # TODO: TZ
        rls_dt = datetime.fromtimestamp(int(str_json['release_timestamp']))
        delta = datetime.now() - rls_dt
        since_str = f'\n(online for {timedelta_pretty(delta)})'

    # notify and log
    apprise_obj.notify(title=f'[ONLINE] {str_user}', body=str_title + since_str)
    log.success(
        f'[ONLINE] ({str_user} - {str_title + since_str.replace("\n", " ")}', cfg=cfg
    )

    match cfg['record']:
        case 'str':
            # streamlink cmd (default)
            c = ['streamlink'] + shlex.split(cfg['arguments']) + [
                '--url', cfg['url'],
                '--output', str_blank + '.ts',
                '--default-stream', cfg['quality']
            ]  # fmt: skip

            if proxy_url:
                c += ['--http-proxy', proxy_url]

            if cookies_txt.is_file():
                c += ['--http-cookies-file', str(cookies_txt)]

        case 'dlp':
            c = ['yt-dlp'] + shlex.split(cfg['arguments'])

            if 'youtube' in str_json['extractor']:
                c += ['--live-from-start']

            if proxy_url:
                c += ['--proxy', proxy_url]

            if cookies_txt.is_file():
                c += ['--cookies', str(cookies_txt)]

            if bgutil_url != 'http://127.0.0.1:4416':
                c += [
                    '--extractor-args',
                    f'youtubepot-bgutilhttp:base_url={bgutil_url}',
                ]

            c += ['-o', str_blank + '.mp4', cfg['url']]
        case 'yta':
            c = ['ytarchive'] + shlex.split(cfg['arguments'])  # fmt: skip

            if proxy_url:
                c += ['--proxy', proxy_url]

            if cookies_txt.is_file():
                c += ['--cookies', str(cookies_txt)]

            # appends potoken to ytarchive cmd
            # need 'https://github.com/Brainicism/bgutil-ytdlp-pot-provider/'
            # disabled due to 'https://github.com/dreammu/ytarchive' fork
            if os.environ.get('YK_FORCE_YTARCHIVE_POTOKEN'):
                try:
                    r = requests.get(bgutil_url + '/ping', timeout=10)
                    r.raise_for_status()

                    bg = r.json()
                    if 'server_uptime' not in bg or 'version' not in bg:
                        raise Exception(f'invalid /ping: {bg}')

                    r = requests.post(
                        bgutil_url + '/get_pot',
                        data={'proxy': proxy_url} if proxy_url else {},
                        timeout=60,
                    )
                    r.raise_for_status()

                    bg = r.json()
                    if 'poToken' not in bg:
                        raise Exception(f'invalid /get_pot: {bg}')

                    log.debug('get potoken from bgutil', token=bg['poToken'])

                    c += ['--potoken', bg['poToken']]

                except Exception as ex:
                    log.exception(f'bgutil - {str(ex)}')

            if bgutil_url != 'http://127.0.0.1:4416':
                c += [
                    '--ytdlp-opts',
                    f'--extractor-args youtubepot-bgutilhttp:base_url={bgutil_url}',
                ]

            c += ['--output', str_blank, cfg['url'], cfg['quality']]
        case _:
            log.error(f'invalid rec_method: {cfg["record"]}')

    # chat_downloader cmd
    c_chat = [
        '--output', str_blank + '.json',
        '--max_attempts', '99999999', 
    ]  # fmt: skip

    if proxy_url:
        c_chat += ['--proxy', proxy_url]

    if cookies_txt.is_file():
        c_chat += ['--cookies', str(cookies_txt)]

    c_chat = ['chat_downloader'] + c_chat + [str_json['webpage_url']]

    log.debug(f'{cfg["record"]}: {" ".join(c)}')
    log.debug(f'chat: {" ".join(c_chat)}')

    # video process
    str_txt = open(str_blank + '.log', 'a')
    str_proc = sp.Popen(c, stdout=str_txt, stderr=str_txt, cwd=str_dir)
    str_pid = psutil.Process(str_proc.pid)

    # chat process
    chat_txt = open(str_blank + '.chat', 'w')
    chat_proc = sp.Popen(c_chat, stdout=chat_txt, stderr=chat_txt, cwd=str_dir)
    chat_pid = psutil.Process(chat_proc.pid)

    # measure livestream duration
    sw = Stopwatch(2)
    sw.restart()

    # looping until stream ended
    while not stop_event.is_set():
        time.sleep(1)

        if not str_pid.is_running():
            break

        if str_pid.status() == psutil.STATUS_ZOMBIE:
            break

    total_time = timedelta(seconds=int(sw.duration))

    # shutdown stream process
    if str_pid.is_running():
        if stop_event.is_set():
            os.kill(str_proc.pid, signal.SIGTERM)
        else:
            os.waitpid(str_proc.pid, 0)
            apprise_obj.notify(
                title=f'[offline] {str_user} ({total_time})', body=str_title
            )

        log.info(f'[offline] ({str_user} - {str_title}) ', cfg=cfg)

    # manual ytarchive merging
    if (
        cfg['record'] == 'yta'
        and 'youtube' in str_json['extractor']
        and not stop_event.is_set()
    ):
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

        if c_merge == '=C':
            log.error(f"can't find *ffmpeg.txt in {str_dir!r}", cfg=cfg)
        else:
            with sp.Popen(c_merge, stderr=str_txt) as proc:
                while True:
                    time.sleep(1)
                    p = proc.poll()

                    if p == 0:
                        for file in files_to_delete:
                            delete(file)
                        break

                    if p is not None:
                        log.error(f'merge error: {str_dir}', cfg=cfg)
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
        jc_conv(str_blank + '.json')
    except Exception as ex:
        log.exception(f'jc error: {str(ex)}')

    # remove [live] prefix
    str_dir.rename(output_dir / Path(esc(cfg['folder'])) / str_name)
