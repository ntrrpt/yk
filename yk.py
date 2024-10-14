#!/usr/bin/env python3
from contextlib import suppress
from loguru import logger
import json
import shlex
import threading
import requests
import time
import os
import sys
import datetime
import subprocess
import shutil
import psutil
import signal
import re
import yt_dlp
import jc
import optparse
import pathlib
import codecs
threads = []
unload = False

ytdlp_config = {
    'quiet': True,
    'playlist_items': 0,
    'noplaylist': True
}

_comm_streamlink = [
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
]

_comm_ytdlp = [
    "yt-dlp",
    "--verbose",
    "--ignore-config",
    "--live-from-start",
    "--merge-output-format", "mp4",
    "--retries", "30",
    "-N", "3"
]

_comm_ytarchive = [
    "ytarchive",
    "--threads", "3",
    "--trace",
    "--verbose",
    "--no-frag-files",
    "--write-mux-file",
    "--no-merge"
]

def date_time(format):
    return datetime.datetime.now().strftime(format)

def fileDel(filename):
    rem_file = pathlib.Path(filename)
    rem_file.unlink(missing_ok=True)

def ntfy(title, text, url = ''):
    if not options.ntfy_id: # https://ntfy.sh/docs
        return

    with suppress(Exception):
        requests.post(
            "https://ntfy.sh/" + options.ntfy_id, timeout=10,
                data = text.encode(encoding='utf-8'),
                headers = {
                    "title": title.encode(encoding='utf-8'),
                    "click": url.encode(encoding='utf-8')
                }
        )

def date_time(format):
    return datetime.datetime.now().strftime(format)

def str_cut(string, letters, postfix='...'):
    return string[:letters] + (string[letters:] and postfix)

def str_fix(string):
    return str_cut(re.sub(r'[/\\?%*:{}【】|"<>]', '', string), 100, '')

def dump_stream(input_dict):
    def dump_stream_json(url):
        with yt_dlp.YoutubeDL(ytdlp_config) as ydlp:
            return ydlp.extract_info(url, download=False)

    def dump_thumb(dir, video_id):
        hq_blank = "https://i.ytimg.com/vi/%s/hqdefault.jpg"
        max_blank = "https://i.ytimg.com/vi/%s/maxresdefault.jpg"

        for blank in [hq_blank, max_blank]:
            with requests.get(blank % video_id, stream=True) as request:
                if request:
                    with open(dir, 'wb') as file:
                        file.write(request.content)

    start_time = time.time()
    stream_json = dump_stream_json(input_dict['url'])

    match stream_json['extractor']:
        case "youtube":
            url_title = str_fix(stream_json['title'][:-17])
            url_name = str_fix(stream_json['uploader'])

        case "twitch:stream":
            url_title = str_fix(stream_json['description'])
            url_name = str_fix(stream_json['uploader'])

        case "wasdtv:stream":
            url_title = str_fix(stream_json['fulltitle'])
            url_name = str_fix(stream_json['webpage_url_basename'])

        case _:
            url_title = str_fix(stream_json['title'])
            url_name = str_fix(stream_json['uploader'])

    if input_dict['regex']:
        regex = input_dict['regex'].lower()

        re_title = re.findall(regex, url_title.lower())
        re_desc = re.findall(regex, stream_json['description'].lower())

        if not re_title and not re_desc:
            return

    file_title = f'[{date_time("%y-%m-%d %H_%M_%S")}] {url_name} - {url_title}'
    file_dir = f"{options.output}/[live] {file_title.rstrip()}"
    dirtitle = "%s/%s" % (file_dir, file_title)

    os.makedirs(file_dir, exist_ok=True)

    # dump preview image
    if 'youtube' in stream_json['extractor']:
        dump_thumb(dirtitle + ".jpg", stream_json['id'])

    # saving stream info
    with codecs.open(dirtitle + ".info", 'w', "utf-8") as info:
        info.write( 
            json.dumps
            (
                stream_json, 
                indent=10, 
                ensure_ascii=False, 
                sort_keys=True
            )
        )

    # notify
    ntfy(f'{url_name} is online.', url_title, stream_json['webpage_url'])
    logger.success(f'[online] ({url_name} - {url_title})')

    # choosing record method
    comm_stream = _comm_streamlink.copy()
    comm_add = [
        "--url", input_dict['url'],
        "--output", dirtitle + ".ts",
        "--default-stream", input_dict['quality']
    ]

    if options.ytdlp:
        comm_stream = _comm_ytdlp.copy()
        comm_add = [
            "-o", dirtitle,
            input_dict['url']
        ]

    if options.ytarchive and 'youtube' in stream_json['extractor']:
        comm_stream = _comm_ytarchive.copy()
        comm_add = [
            "--output", dirtitle,
            input_dict['url'],
            input_dict['quality']
        ]

    for i in comm_add:
        comm_stream.append(i)

    _comm_chat = [
        'chat_downloader',
        stream_json['webpage_url'],
        "--output", dirtitle + ".json",
        "--inactivity_timeout", "99999999"
    ]

    # ext stream dump process
    txt_stream = open(dirtitle + ".log", "a")
    process_stream = subprocess.Popen(comm_stream, stdout=txt_stream, stderr=txt_stream)
    pid_stream = psutil.Process(process_stream.pid)

    # chat saving
    txt_chat = open(dirtitle + ".chat", "w")
    process_chat = subprocess.Popen(_comm_chat, stdout=txt_chat, stderr=txt_chat)
    pid_chat = psutil.Process(process_chat.pid)

    # thread loop until stream ending
    threads.append(input_dict['url'])

    while not unload:
        time.sleep(1)

        st_zombie = pid_stream.status() == psutil.STATUS_ZOMBIE
        st_running = pid_stream.is_running()

        if st_zombie or not st_running:
            break

    end_time = datetime.timedelta(seconds=int(f'{time.time() - start_time:.{0}f}'))
    threads.remove(input_dict['url'])

    if pid_stream.is_running():
        if unload:
            os.kill(process_stream.pid, signal.SIGTERM)
        else:
            os.waitpid(process_stream.pid, 0)
            ntfy(f'{url_name} is offline. [{end_time}]', url_title, stream_json['webpage_url'])

        logger.info(f'[offline] ({url_name} - {url_title}) ({end_time})')

    # manual merging
    if options.ytarchive:
        _comm_merge = 'test'
        files_to_delete = []

        for file in os.listdir(file_dir):
            if file.endswith('ffmpeg.txt'):
                fp = "%s/%s" % (file_dir, file)
                _comm_merge = shlex.split(open(fp).read())
                files_to_delete.append(file)

            if file.endswith('.ts'):
                files_to_delete.append(file)

        # merge video and audio
        with subprocess.Popen(_comm_merge, stderr=txt_stream) as proc:
            while True:
                time.sleep(1)
                p = proc.poll()

                if p == 0:
                    for file in files_to_delete:
                        fp = "%s/%s" % (file_dir, file)
                        fileDel(fp)
                    break

                if p is not None:
                    logger.error(f"merge error: {file_dir}")
                    break

    if pid_chat.is_running():
        if pid_chat.status() == psutil.STATUS_ZOMBIE:
            os.waitpid(process_chat.pid, 0)
        if pid_chat.is_running():
            os.kill(process_chat.pid, signal.SIGTERM)

    txt_chat.close()
    txt_stream.close()

    with suppress(Exception):
        jc.conv(dirtitle + ".json")

    os.rename(file_dir, f"{options.output}/{file_title.rstrip()}")

def check_live(url):
    with subprocess.Popen(['streamlink', '--twitch-disable-hosting', "--url", url], stdout=subprocess.PIPE) as proc:
        while True:
            time.sleep(0.1)
            p = proc.poll()
            if p is not None:
                return (True if p == 0 else False)

def dump_list(input):
    lst = {}
    with open(input) as file:
        for line in file:
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue

            split = line.split()

            url = split[0]
            regex = ""
            quality = "best"

            if len(split) > 1:
                quality = split[1]

            if len(split) > 2:
                regex = split[2]

            if 'youtube' in url and 'watch?v=' not in url:
                url += '/live'

            lst[len(lst)] = {
                'url': url,
                'regex': regex,
                'quality': quality
            }

    return lst

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-o', '--output', dest='output', default='.', help='Streams output')
    parser.add_option('-l', '--log', dest='log_name', default='', help='Log output')
    parser.add_option('-d', '--delay', dest='delay_check', type=int, default='10', help='Streams check delay')
    parser.add_option('-s', '--src', dest='src_name', default='list.txt', help='File with channels/streams')
    parser.add_option('--ntfy', dest='ntfy_id', help='ntfy.sh channel')
    parser.add_option('--dlp', dest='ytdlp', action='store_true', help='Use yt-dlp instead of streamlink')
    parser.add_option('--yta', dest='ytarchive', action='store_true', help='Use ytarchive for youtube streams')
    options, arguments = parser.parse_args()

    if options.output != '.':
        os.makedirs(options.output, exist_ok=True)

    if not options.log_name:
        options.log_name = "%s/%s.txt" % (options.output, date_time('%Y-%m-%d'))

    logger.remove(0)
    logger.add(sys.stderr, format = "<level>[{time:DD-MMM-YYYY HH:mm:ss}]</level> {message}", backtrace = True, diagnose = True,  colorize = True, level = 5)
    logger.add(options.log_name, format = "[{time:DD-MMM-YYYY HH:mm:ss}] {message}", backtrace = True, diagnose = True,  colorize = True, level = 5)

    # for binaries in project folder
    pwdir = os.path.dirname(os.path.realpath(__file__))
    os.environ["PATH"] = os.pathsep.join([
        pwdir,
        os.environ["PATH"]
    ])

    try:
        while True:
            urls = dump_list(options.src_name)

            for i in range(len(urls)):
                if urls[i]['url'] not in threads and check_live(urls[i]['url']):
                    threading.Thread(target=dump_stream, args=(urls[i], )).start()
                else:
                    print(f'({i + 1} / {len(urls)}) {len(threads)} is streaming.', end='\r')

                time.sleep(options.delay_check)

    except KeyboardInterrupt:
        if threads:
            unload = True
            logger.info('Stopping...')
            while threading.active_count() > 1:
                time.sleep(0.1)
