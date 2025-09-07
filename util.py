from loguru import logger as log
from datetime import datetime
import pprint
import pathlib
import sys
import re


def str_cut(string, letters, postfix='...'):
    return string[:letters] + (string[letters:] and postfix)


def dt_now(fmt='%y-%m-%d %H_%M_%S'):
    now = datetime.now()
    return now.strftime(fmt)


def float_fmt(number, digits):
    return f'{number:.{digits}f}'


def str_esc(string):
    return str_cut(re.sub(r'[/\\?%*:{}【】|"<>]', '', string), 100, '')


def append(path, data, end='\n'):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(data + end)
    log.trace(f'{path} appended')


def write(path, data, end='\n'):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data + end)
    log.trace(f'{path} writed')


def delete(path):
    rem_file = pathlib.Path(path)
    rem_file.unlink(missing_ok=True)
    log.trace(f'{path} deleted')


def pw(path, data, end='\n'):
    s = str(pprint.pformat(str(data)))
    write(path, s, end)
    log.trace(f'{path} pwd')


def pp(data):
    s = pprint.pformat(str(data))
    print(s)


def pf(data):
    return str(pprint.pformat(str(data)))


def die(s=''):
    if s:
        log.critical(str(s))
    sys.exit()
