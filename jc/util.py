#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta
from pathlib import Path


def timedelta_pretty(td: timedelta, ms_add=False) -> str:
    total_ms = int(td.total_seconds() * 1000)
    days, rem = divmod(total_ms, 24 * 3600 * 1000)
    hours, rem = divmod(rem, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    seconds, ms = divmod(rem, 1000)

    ms_digit = ms // 100

    r = f'{hours:02}:{minutes:02}:{seconds:02}'
    if ms_add:
        r += f',{ms_digit}'
    if days:
        r = f'{days}|{r}'
    return r


def con(d, c):
    return any(k in str(c) for k in d)


def str_cut(string: str, letters: int, postfix: str = '...'):
    return string[:letters] + (string[letters:] and postfix)


def append(path: Path | str, data: str, end: str = '\n'):
    path = Path(path)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(data + end)


def write(path: Path | str, data: str, end: str = '\n'):
    path = Path(path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data + end)
