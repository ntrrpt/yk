from loguru import logger as log
from http.cookiejar import MozillaCookieJar
from datetime import datetime
import pprint
from pathlib import Path
import sys
import re
import os
import requests
import unicodedata

hq_blank = 'https://i.ytimg.com/vi/%s/hqdefault.jpg'
max_blank = 'https://i.ytimg.com/vi/%s/maxresdefault.jpg'
yta_q = [
    'audio_only',
    '144p',
    '240p',
    '360p',
    '480p',
    '720p',
    '720p60',
    '1080p',
    '1080p60',
    '1440p',
    '1440p60',
    '2160p',
    '2160p60',
    'best',
]


def sum_mtime(files):
    return sum(Path(f).stat().st_mtime for f in files)


def str_cut(string: str, letters: int, postfix: str = '...'):
    return string[:letters] + (string[letters:] and postfix)


def dt_now(fmt: str = '%y-%m-%d %H_%M_%S'):
    now = datetime.now()
    return now.strftime(fmt)


def float_fmt(number: int, digits: int):
    return f'{number:.{digits}f}'


def esc(name: str, replacement: str = '_') -> str:
    allowed_brackets = '()[]{}'
    r = []

    for ch in name:
        cat = unicodedata.category(ch)

        if ch in '<>:"/\\|?*' or ch == '\x00':
            r.append(replacement)
        elif ch in allowed_brackets:
            r.append(ch)
        elif cat.startswith(('P', 'S', 'C')):
            r.append(replacement)
        else:
            r.append(ch)

    r = ''.join(r)
    r = r.rstrip(' .')
    r = re.sub(r'_+', '_', r)

    return r[:255]


def append(path: Path | str, data: str, end: str = '\n'):
    path = Path(path)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(data + end)


def write(path: Path | str, data: str, end: str = '\n'):
    path = Path(path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data + end)


def delete(path: Path | str):
    path = Path(path)
    rem_file = Path(path)
    rem_file.unlink(missing_ok=True)
    log.trace(f'{path} deleted')


def pw(path: Path | str, data: str, end: str = '\n'):
    path = Path(path)
    s = str(pprint.pformat(str(data)))
    write(path, s, end)
    log.trace(f'{path} pwd')


def pp(data: str):
    print(pprint.pformat(str(data)))


def pf(data: str):
    return str(pprint.pformat(str(data)))


def die(s: str = ''):
    if s:
        log.critical(str(s))
    sys.exit(1)


def remove_all_exact(path, target):
    path = Path(path)
    old_stat = path.stat()

    with open(path, 'r+', encoding='utf-8') as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate(0)
        for line in lines:
            if line.rstrip('\n') != target:
                f.write(line)

    os.utime(path, (old_stat.st_atime, old_stat.st_mtime))


def yt_dump_thumb(path: Path | str, video_id: str, proxy: str | None = None):
    path = Path(path)
    proxies = {'http': proxy, 'https': proxy} if proxy else None

    for blank in [max_blank, hq_blank]:
        url = blank % video_id
        try:
            with requests.get(url, stream=True, proxies=proxies) as request:
                if request.status_code == 200:
                    with open(path, 'wb') as file:
                        file.write(request.content)
        except requests.RequestException as ex:
            log.error(ex)
            continue

        if path.exists() and path.stat().st_size > 0:
            return url


def http_cookies(path: Path | str):
    path = Path(path)
    if not path.is_file():
        return []

    c_args = []

    # https://github.com/streamlink/streamlink/issues/3370#issuecomment-846261921
    pattern = re.compile(
        r'(?P<site>.*?)\t(TRUE|FALSE)\t/\t(TRUE|FALSE)\t([0-9]{1,})\t(?P<cookiename>.+)\t(?P<cookievalue>.+)'
    )

    with open(path, 'r') as f:
        lines = f.readlines()

    for line in lines[2:]:
        line = line.strip()
        match = pattern.match(line)
        if match:
            name = match.group('cookiename')
            value = match.group('cookievalue')
            if name and value:
                c_args += ['--http-cookie', f'{name}={value}']

    return c_args


def _http_cookies(path: Path | str):
    path = Path(path)
    if not path.is_file():
        return []

    c_args = []

    cj = MozillaCookieJar(path)
    cj.load()  # ignore_discard=True, ignore_expires=True
    cd = requests.utils.dict_from_cookiejar(cj)

    for name, value in cd.items():
        if name and value:
            c_args += ['--http-cookie', f'{name}={value}']

    return c_args
