#!/usr/bin/env python3
import json, os, datetime, sys, pathlib
from prettytable import PrettyTable

fields = ["Badges", "Username", "Link to channel (id)" ]
progress = False

def fileDel(filename):
    rem_file = pathlib.Path(filename)
    rem_file.unlink(missing_ok=True)

def add(dir, bin):
    with open(dir, 'a', encoding='utf-8') as file:
        file.write(bin + '\n')

def str_cut(string, letters, postfix='...'):
    return string[:letters] + (string[letters:] and postfix)

def log(string, end='\n'):
    if progress:
        print(string, end=end)

def conv(filepath):
    def dict_append(timestamp, username, id, message, badge):
        history[len(history)] = {
            'timestamp': timestamp, 
            'username': username, 
            'message': message, 
            'badge': badge
        }

        for i in range(len(users)):
            if users[i]['id'] == id: 
                return

        users[len(users)] = {
            'username': username,
            'id': id, 
            'badge': badge
        }

    SITE = ''
    LINK = ''
    chat = ''
    users = {}
    history = {}
    users_table = PrettyTable()
    users_table.field_names = fields
    filename = os.path.splitext(filepath)[0] + '.conv'

    with open(filepath, 'r', encoding='utf-8') as file:
        chat = json.load(file)

    fileDel(filename)

    # type of stream (youtube / twitch)
    types = []
    for i, msg in enumerate(chat, start=1):
        log('[finding] messages: %s/%s' % (len(chat), i), end='\r')
        types.append(msg['action_type'])
    log('') # newline

    types = list(set(types))

    if len(types) > 1:
        m = '%s: new types: %s' % (filename, types)
        add(filename, m)
        log(m)
    if 'text_message' in types:
        SITE = 'twitch'
        LINK = 'https://www.twitch.tv/'
    if 'add_chat_item' in types:
        SITE = 'youtube'
        LINK = 'https://www.youtube.com/channel/'
    if not SITE:
        m = '%s: yt/tw not found in json' % filename
        add(filename, m)
        log(m)
        return

    # adding messages to dict
    for i, msg in enumerate(chat, start=1):
        if not 'message' in msg:
            log('%s: no message       ' % i)
            continue

        log('[sorting] messages: %s/%s, users: %s' % (len(chat), i, len(users)), end='\r')

        # badges (moderator, subscriber, etc.)
        badges = ''
        if 'badges' in msg['author']:
            for b, badge in enumerate(msg['author']['badges']):
                badges += (', ' if b > 0 else '') + badge['title']

        match SITE:
            case "youtube":
                dict_append(
                    msg['timestamp'], 
                    str_cut(msg['author']['name'], 20),
                    msg['author']['id'],
                    msg['message'], 
                    badges
                )

            case "twitch":
                dict_append(
                    msg['timestamp'], 
                    str_cut(msg['author']['display_name'], 20),
                    msg['author']['name'],
                    msg['message'], 
                    badges
                )
    log('')

    # adding users to prettytable
    for i in range(len(users)):
        users_table.add_row([
            users[i]['badge'], 
            users[i]["username"], 
            LINK + users[i]["id"]
        ])

    # writing msg count and table
    add(filename, 'messages: %s, users: %s' % (len(chat), len(users)))
    add(filename, users_table.get_string(sortby="Badges", reversesort=True))

    # writing messages
    delay_time = 0
    all_time = 0

    for i in range(len(history)):
        log('[writing] messages: %s/%s' % (len(chat), i+1),  end='\r')

        username = history[i]["username"]
        badge = history[i]['badge']
        timestamp = history[i]['timestamp']

        icon = '  |  '
        if badge:
            username += f' ({badge})'
            if 'Moderator' in badge:
                icon = ' [M] '
            if 'Owner' in badge:
                icon = ' [O] '

        if not delay_time:
            delay_time = timestamp
            
        delta = timestamp - delay_time
        all_time += delta
        delay_time = timestamp

        timestr = str(datetime.timedelta(microseconds=int(all_time))) # datetime.datetime.fromtimestamp(history[i]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        add(filename, f'{timestr[:-5]}{icon}{username}: {history[i]["message"]}')

    log('')

if __name__ == "__main__":
    progress = True
    for i in range(1, len(sys.argv)):
        conv(sys.argv[i])
