#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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


def main(path):
    ##################################################################
    #  init

    SITE = ''
    LINK = ''
    CHAT = ''
    USERS = {}
    MESSAGES = []

    path = Path(path)
    conv = path.with_suffix('.conv')

    if not path.is_file():
        log(f'not exists: {path.as_posix()} ')
        return

    with open(path, 'r', encoding='utf-8') as file:
        CHAT = json.load(file)

    ##################################################################
    #  type of stream (youtube / twitch)

    types = list(set([x['action_type'] for x in CHAT]))

    if 'text_message' in types:
        SITE = 'tw'
        LINK = 'https://www.twitch.tv/'
    if 'add_chat_item' in types:
        SITE = 'yt'
        LINK = 'https://www.youtube.com/channel/'
    if not SITE:
        m = f'{conv}: yt/tw not found in json'
        util.append(conv, m)
        log(m)
        return

    util.write(conv, '')
    if len(types) > 1:
        m = f'{conv}: new types: {types}'
        util.append(conv, m)
        log(m)

    ##################################################################
    #  adding messages and users

    delay_time = 0
    all_time = 0

    for i, msg in enumerate(CHAT, start=1):
        if 'message' not in msg:
            log(f'{i}: no message ')
            continue

        log(f'm: {len(CHAT)}/{i}, u: {len(USERS)}', end='\r')

        # badges (moderator, subscriber, etc.)
        icon = ''
        badges = ''

        if 'badges' in msg['author']:
            badges = ', '.join(
                [
                    badge.get('title') or badge.get('name') or '__NULL__'
                    for badge in msg['author']['badges']
                ]
            )

        # idk how handle locales
        for var, target in [
            (['Verified', 'Подтверждено'], '✔'),
            (['Moderator', 'Модератор'], 'M'),
            (['Owner', 'Владелец'], 'O'),
        ]:
            if util.con(var, badges):
                icon += target

        if SITE == 'yt':
            username = msg['author'].get('name', '__NULL__').removeprefix('@')
        else:
            username = msg['author'].get('display_name', '__NULL__')

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

        timestr = util.timedelta_pretty(
            timedelta(microseconds=int(all_time)), ms_add=True
        )
        # datetime.datetime.fromtimestamp(history[i]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

        MESSAGES.append(
            [
                timestr,
                icon,
                util.str_cut(username, 20, '~1'),
                msg['message'] or '__NULL__',
            ]
        )

        uid = msg['author']['id'] if SITE == 'yt' else msg['author']['name']

        if uid not in USERS:
            USERS[uid] = {
                'badges': badges,
                'username': util.str_cut(username, 30, '~1'),
                'msg_count': 1,
            }
        else:
            USERS[uid]['msg_count'] += 1

    log('')

    ##################################################################
    #  writing conv

    # list for tabulate
    USERS_TAB = []

    for k, v in USERS.items():
        msg_count = v.get('msg_count', 0)

        USERS_TAB += [
            [
                v.get('badges', ''),
                v.get('username', ''),
                msg_count if msg_count > 1 else '',
                LINK + k,
            ]
        ]

    USERS_TAB = sorted(USERS_TAB, key=lambda x: x[1])
    for var in [
        (['sponsor', 'спонсор']),  # new
        (['Sponsor', 'Спонсор']),
        (['Verified', 'Подтверждено']),
        (['Moderator', 'Модератор']),
        (['Owner', 'Владелец']),
    ]:
        USERS_TAB = sorted(USERS_TAB, key=lambda x: 0 if util.con(var, x[0]) else 1)

    util.append(
        conv,
        tabulate(
            [[len(CHAT), len(USERS_TAB)]],
            ['messages', 'users'],
            colalign=('center', 'center'),
            tablefmt='simple_outline',
        ),
    )

    util.append(
        conv,
        tabulate(
            USERS_TAB,
            ['Badges', 'Username', 'len', 'Link to channel (id)'],
            colalign=('left', 'left', 'left', 'left'),
            tablefmt='simple_outline',
        ),
    )

    util.append(
        conv,
        tabulate(
            MESSAGES,
            maxcolwidths=[None, None, None, 100],
            colalign=('left', 'right', 'right', 'left'),
        ),
    )


if __name__ == '__main__':
    progress = True
    for i in range(1, len(sys.argv)):
        main(sys.argv[i])
