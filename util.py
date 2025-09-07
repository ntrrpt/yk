from loguru import logger as log
from datetime import datetime
import pprint
from pathlib import Path
import sys
import re
import platform
import requests
import unicodedata

WINDOWS: any = (
    [int(x) for x in platform.version().split('.')]
    if platform.system() == 'Windows'
    else False
)


def str_cut(string: str, letters: int, postfix: str = '...'):
    return string[:letters] + (string[letters:] and postfix)


def dt_now(fmt: str = '%y-%m-%d %H_%M_%S'):
    now = datetime.now()
    return now.strftime(fmt)


def float_fmt(number: int, digits: int):
    return f'{number:.{digits}f}'


def esc(name: str, replacement: str = '_') -> str:
    allowed_brackets = '()[]{}'
    safe_chars = []

    for ch in name:
        cat = unicodedata.category(ch)

        if ch in '<>:"/\\|?*' or ch == '\x00':
            safe_chars.append(replacement)
        elif ch in allowed_brackets:
            safe_chars.append(ch)
        elif cat.startswith(('P', 'S', 'C')):
            safe_chars.append(replacement)
        else:
            safe_chars.append(ch)

    safe = ''.join(safe_chars)
    safe = safe.rstrip(' .')
    safe = re.sub(r'_+', '_', safe)

    return safe[:255]


def append(path: Path | str, data: str, end: str = '\n'):
    path = Path(path)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(data + end)
    log.trace(f'{path} appended')


def write(path: Path | str, data: str, end: str = '\n'):
    path = Path(path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data + end)
    log.trace(f'{path} writed')


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
    s = pprint.pformat(str(data))
    print(s)


def pf(data: str):
    return str(pprint.pformat(str(data)))


def die(s: str = ''):
    if s:
        log.critical(str(s))
    sys.exit()


def yt_dump_thumb(path: Path | str, video_id: str, proxy: str | None = None):
    path = Path(path)
    hq_blank = 'https://i.ytimg.com/vi/%s/hqdefault.jpg'
    max_blank = 'https://i.ytimg.com/vi/%s/maxresdefault.jpg'

    proxies = {'http': proxy, 'https': proxy} if proxy else None

    for blank in [max_blank, hq_blank]:
        try:
            with requests.get(
                blank % video_id, stream=True, proxies=proxies
            ) as request:
                if request.status_code == 200:
                    with open(path, 'wb') as file:
                        file.write(request.content)
        except requests.RequestException as ex:
            log.error(ex)
            continue

        if path.exists() and path.stat().st_size > 0:
            return
