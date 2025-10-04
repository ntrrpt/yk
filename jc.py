#!/usr/bin/env python3
import json
import sys
from datetime import timedelta
from pathlib import Path

from tabulate import tabulate

import util

progress = False


def log(string, end='\n'):
    if progress:
        print(string, end=end)


def conv(path):
    ##################################################################
    #  init

    SITE = ''
    LINK = ''
    CHAT = ''
    USERS = []
    URLS = []
    MESSAGES = []

    path = Path(path)
    fn = path.stem + '.conv'

    with open(path, 'r', encoding='utf-8') as file:
        CHAT = json.load(file)

    ##################################################################
    #  type of stream (youtube / twitch)

    types = list(set([x['action_type'] for x in CHAT]))

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
            f'm: {len(CHAT)}/{i}, u: {len(USERS)}',
            end='\r',
        )

        # badges (moderator, subscriber, etc.)
        icon = ''
        badges = ''
        if 'badges' in msg['author']:
            for b, badge in enumerate(msg['author']['badges']):
                badges += (', ' if b > 0 else '') + badge['title']

        # idk how handle locales
        for var, target in [
            (['Verified', 'Подтверждено'], '✔'),
            (['Moderator', 'Модератор'], 'M'),
            (['Owner', 'Владелец'], 'O'),
        ]:
            if util.con(var, badges):
                icon += target

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

        timestr = util.timedelta_pretty(timedelta(microseconds=int(all_time)))
        # datetime.datetime.fromtimestamp(history[i]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

        MESSAGES.append(
            [
                timestr,
                icon,
                util.str_cut(username, 20, '~') or '__NULL__',
                msg['message'] or '__NULL__',
            ]
        )

        url = LINK + (msg['author']['id'] if SITE == 'yt' else msg['author']['name'])

        if url in URLS:
            continue

        USERS.append([badges, username, url])
        URLS.append(url)

    log('')

    ##################################################################
    #  writing conv

    USERS = sorted(USERS, key=lambda x: x[1])
    for var in [
        (['sponsor', 'спонсор']),  # new
        (['Sponsor', 'Спонсор']),
        (['Verified', 'Подтверждено']),
        (['Moderator', 'Модератор']),
        (['Owner', 'Владелец']),
    ]:
        USERS = sorted(USERS, key=lambda x: 0 if util.con(var, x[0]) else 1)

    util.write(
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

    util.append(
        fn,
        tabulate(
            MESSAGES,
            maxcolwidths=[None, None, None, 100],
            colalign=('left', 'right', 'right', 'left'),
        ),
    )


if __name__ == '__main__':
    progress = True
    for i in range(1, len(sys.argv)):
        conv(sys.argv[i])
