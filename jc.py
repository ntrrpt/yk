#!/usr/bin/env python3
import json
import os
import sys
from datetime import timedelta

from tabulate import tabulate

import util

progress = False


def log(string, end='\n'):
    if progress:
        print(string, end=end)


def timedelta_pretty(td: timedelta, pad: bool = True) -> str:
    total_ms = int(td.total_seconds() * 1000)
    days, rem = divmod(total_ms, 24 * 3600 * 1000)
    hours, rem = divmod(rem, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    seconds, ms = divmod(rem, 1000)

    ms_digit = ms // 100

    if pad:
        if days:
            return f'{days}|{hours:02}:{minutes:02}:{seconds:02}.{ms_digit}'
        return f'{hours:02}:{minutes:02}:{seconds:02}.{ms_digit}'
    else:
        if days:
            return f'{days}|{hours:02}:{minutes}:{seconds}.{ms_digit}'
        return f'{hours:02}:{minutes}:{seconds}.{ms_digit}'


def conv(filepath):
    ##################################################################
    #  init

    SITE = ''
    LINK = ''
    CHAT = ''
    USERS = []
    URLS = []
    MESSAGES = []

    fn = os.path.splitext(filepath)[0] + '.conv'

    with open(filepath, 'r', encoding='utf-8') as file:
        CHAT = json.load(file)

    util.delete(fn)

    ##################################################################
    #  type of stream (youtube / twitch)

    types = []
    for msg in CHAT:
        types.append(msg['action_type'])

    types = list(set(types))

    if len(types) > 1:
        m = f'{fn}: new types: {types}'
        util.append(fn, m)
        log(m)
    if 'text_message' in types:
        SITE = 'tw'
        LINK = 'https://www.twitch.tv/'
    if 'add_chat_item' in types:
        SITE = 'yt'
        LINK = 'https://www.youtube.com/channel/'
    if not SITE:
        m = f'{fn}: yt/tw not found in json'
        util.append(fn, m)
        log(m)
        return

    ##################################################################
    #  adding messages and users

    delay_time = 0
    all_time = 0

    for i, msg in enumerate(CHAT, start=1):
        if 'message' not in msg:
            log(f'{i}: no message ')
            continue

        log(
            f'messages: {len(CHAT)}/{i}, users: {len(USERS)}',
            end='\r',
        )

        # badges (moderator, subscriber, etc.)
        icon = ''
        badges = ''
        if 'badges' in msg['author']:
            for b, badge in enumerate(msg['author']['badges']):
                badges += (', ' if b > 0 else '') + badge['title']

        # idk how handle locales
        if 'Verified' in badges or 'Подтверждено' in badges:
            icon = '✔'
        if 'Moderator' in badges or 'Модератор' in badges:
            icon = 'M'
        if 'Owner' in badges or 'Владелец' in badges:
            icon = 'O'

        username = (
            msg['author']['name'] if SITE == 'yt' else msg['author']['display_name']
        )

        # https://github.com/astanin/python-tabulate/issues/189
        if username in ('True', 'False'):
            username = f'__{username}__'
        if msg['message'] in ('True', 'False'):
            msg['message'] = f'__{msg["message"]}__'

        if not delay_time:
            delay_time = msg['timestamp']

        delta = msg['timestamp'] - delay_time
        all_time += delta
        delay_time = msg['timestamp']

        timestr = timedelta_pretty(timedelta(microseconds=int(all_time)))
        # datetime.datetime.fromtimestamp(history[i]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

        MESSAGES.append(
            [
                timestr,
                icon,
                str(username) or '__NULL__',
                str(msg['message']) or '__NULL__',
            ]
        )

        url = LINK + (msg['author']['id'] if SITE == 'yt' else msg['author']['name'])

        if url not in URLS:
            USERS.append([badges, username, url])
            URLS.append(url)

    ##################################################################
    #  writing

    util.append(
        fn,
        tabulate(
            [[len(CHAT), len(USERS)]],
            ['messages', 'users'],
            colalign=('center', 'center'),
            tablefmt='simple_outline',
        ),
    )

    util.append(
        fn,
        tabulate(
            USERS,
            ['Badges', 'Username', 'Link to channel (id)'],
            tablefmt='simple_outline',
        ),
    )

    # messages
    util.append(
        fn,
        tabulate(
            MESSAGES,
            maxcolwidths=[None, None, 40, 100],
            colalign=('left', 'right', 'right', 'left'),
        ),
    )

    log('')


if __name__ == '__main__':
    progress = True
    for i in range(1, len(sys.argv)):
        conv(sys.argv[i])
