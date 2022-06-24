#!/usr/bin/env python3
import json, os, datetime, sys
from prettytable import PrettyTable

def str_cut(string, letters, postfix='...'):
    return string[:letters] + (string[letters:] and postfix)

def json2txt(filepath):
    def dict_append(timestamp, username, id, message, badge):
        history[len(history)] = {
            'timestamp': timestamp // int(1e6), 
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

    _type = ''
    users = {}
    history = {}
    filename = os.path.splitext(filepath)[0] + '.conv'

    users_table = PrettyTable()
    users_table.field_names = [
        "Badges", 
        "Username",
        "Link to channel (id)"
    ]

    with open(filepath, 'r', encoding='utf-8') as file:
        chat = json.load(file)
        for i, msg in enumerate(chat, start=1):
            if not 'message' in msg:
                continue

            print(f'[sorting] m: {i}/{len(chat)}, u: {len(users)}', end='\r')

            badges = ''
            if 'badges' in msg['author']:
                for b, badge in enumerate(msg['author']['badges']):
                    badges += (', ' if b > 0 else '') + badge['title']

            # twitch
            if 'action_type' not in msg or msg['action_type'] == 'text_message':
                if not _type: 
                    _type = 'tw' 

                dict_append(
                    msg['timestamp'], 
                    str_cut(msg['author']['display_name'], 20), 
                    msg['author']['name'], 
                    msg['message'], 
                    badges
                )

            # youtube 
            elif msg['action_type'] == 'add_chat_item':
                if not _type: 
                    _type = 'yt' 

                dict_append(
                    msg['timestamp'], 
                    str_cut(msg['author']['name'], 20), 
                    msg['author']['id'], 
                    msg['message'], 
                    badges
                )

    for i in range(len(users)):
        print(f'[sorting] m: {len(chat)}/{len(chat)}, u: {i+1}/{len(users)}', end='\r')

        yt_link = 'https://www.youtube.com/channel/' 
        tw_link = 'https://www.twitch.tv/'

        users_table.add_row([
            users[i]['badge'], 
            users[i]["username"], 
            (tw_link if _type == 'tw' else yt_link) + users[i]["id"]
        ])

    print(f'[writing] m: {" " * len(str(len(chat)))}', end='\r')

    if os.path.exists(filename): 
        os.remove(filename)

    with open(filename, 'a') as file:
        file.write(f'messages: {len(chat)}, users: {len(users)}\n')
        file.write(f'{users_table.get_string(sortby="Badges", reversesort=True)}\n')

    delay_time = 0
    all_time = 0

    for i in range(len(history)):
        print(f'[writing] m: {i+1}', end='\r')
        username = history[i]["username"]
        badge = history[i]['badge']
        timestamp = history[i]['timestamp']

        icon = '  |  '
        if badge != '':
            username += f' ({badge})'
        if 'Moderator' in badge:
            icon = '[M]'
        if 'Owner' in badge:
            icon = '[O]'

        if not delay_time:
            delay_time = timestamp
            
        delta = timestamp - delay_time
        all_time += delta
        delay_time = timestamp
        timestr = datetime.timedelta(seconds=int(all_time))
        #timestr = datetime.datetime.fromtimestamp(history[i]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

        with open(filename, 'a') as file:
            file.write(f'{timestr}{icon}{username}: {history[i]["message"]}\n')
            
    print('')

if __name__ == "__main__":
    for i in range(1, len(sys.argv)):
        json2txt(sys.argv[i])
