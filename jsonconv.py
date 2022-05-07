#!/usr/bin/env python3
import json, os, datetime, sys
from prettytable import PrettyTable

def str_cut(string, letters, postfix='...'):
    return string[:letters] + (string[letters:] and postfix)

def json2txt(filepath):
    def dict_append(timestamp, username, id, message, badge):
        history[len(history)] = {'timestamp': timestamp // 1000000, 'username': username, 'message': message, 'badge': badge}
        for i in range(len(users)):
            if users[i]['id'] == id: return
        users[len(users)] = {'username': username, 'id': id, 'badge': badge}

    type = ''
    filename = f'{os.path.splitext(filepath)[0]}.conv'
    users = {}
    history = {}

    users_table = PrettyTable()
    users_table.field_names = ["Badges", "Username", "Link to channel (id)"]

    with open(filepath, 'r', encoding='utf-8') as file:
        chat = json.load(file)
        for i, msg in enumerate(chat, start=1):
            print(f'[sorting] m: {i}/{len(chat)}, u: {len(users)}', end='\r')
            
            if not 'message' in msg:
                continue
            
            badges = ''
            if 'badges' in msg['author']:
                for b, badge in enumerate(msg['author']['badges']):
                    badges += (', ' if b != 0 else '') + badge['title']

            timestamp = msg['timestamp']
            message = msg['message']

            # twitch                      
            if 'action_type' not in msg or msg['action_type'] == 'text_message':
                if not type: type = 'tw' 
                name = str_cut(msg['author']['display_name'], 20)
                id = msg['author']['name']

            # youtube 
            elif msg['action_type'] == 'add_chat_item':
                if not type: type = 'yt' 
                name = str_cut(msg['author']['name'], 20)
                id = msg['author']['id']

            dict_append(timestamp, name, id, message, badges)

    for i in range(len(users)):
        print(f'[sorting] m: {len(chat)}/{len(chat)}, u: {i+1}/{len(users)}', end='\r')
        if type == 'yt':
            link = f'https://www.youtube.com/channel/{users[i]["id"]}'
        if type == 'tw':
            link = f'https://www.twitch.tv/{users[i]["id"]}'
        users_table.add_row([users[i]['badge'], users[i]["username"], link])

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
        message = history[i]["message"]

        arrow = ' | '
        if badge != '':
            username += f' ({badge})'
        if 'Moderator' in badge:
            arrow = '[M]'
        if 'Owner' in badge:
            arrow = '[O]'

        if not delay_time:
            delay_time = timestamp
        delta = timestamp - delay_time
        all_time += delta
        delay_time = timestamp
        timestr = datetime.timedelta(seconds=int(all_time))
        #timestr = datetime.datetime.fromtimestamp(history[i]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

        with open(filename, 'a') as file:
            file.write(f'{timestr}{arrow}{username}: {message}\n')
            
    print('')

if __name__ == "__main__":
    for i in range(1, len(sys.argv)):
        json2txt(sys.argv[i])