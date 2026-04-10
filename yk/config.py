#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import random
import tomllib
from functools import reduce
from pathlib import Path

import tomli_w
from loguru import logger as log
from validators import url as is_url

from . import util


def parse(i: list = [], args=None, cfg_to_del: dict = {}):
    o = []

    for file in filter(None, i):
        toml = {}

        #########################
        ## toml validation

        try:
            if Path(file).is_file():
                with open(file, 'rb') as f:
                    toml = tomllib.load(f)
                    assert toml

            elif is_url(file):
                toml = {file: {}}

            else:
                log.warning(f'skipping invalid item: {file}', i=i)
                continue

        except tomllib.TOMLDecodeError as ex:
            log.error(f'toml decode error in {file!r}, {ex}')
            continue

        except FileNotFoundError as ex:
            log.error(f"file {file!r} not found', {ex}")
            continue

        except AssertionError:
            log.error(f'file {file!r} is empty')
            continue

        except Exception as ex:
            log.error(f'file error in {file!r}, {ex}')
            continue

        abbrs = ['u', 'f', 'r', 'q', 'd', 'h', 'o', 'chk', 'rec']

        # defaults
        _quality = args.quality
        _output = args.output
        _folder = ''
        _health = False
        _regex = ''  # TODO: args
        _regex_title = None
        _regex_desc = None
        _apprise = args.apprise
        _cookies = args.cookies
        _bgutil = args.bgutil
        _proxy = random.choice(args.proxy) if args.proxy else ''

        _checker = args.chk
        _recorder = args.rec
        _arguments = None

        for k, v in toml.copy().items():
            if not isinstance(v, dict):
                # global vars
                match k:
                    case 'checker' | 'chk':
                        if v in ['str', 'dlp']:
                            _checker = v
                    case 'recorder' | 'rec':
                        if v in ['str', 'dlp', 'yta']:
                            _recorder = v
                    case 'quality' | 'q':
                        _quality = str(v)
                    case 'output' | 'o':
                        _output = str(v)
                    case 'folder' | 'f':
                        _folder = str(v)
                    case 'health' | 'h':
                        _health = bool(v)
                    case 'regex' | 'r':
                        _regex = str(v)  # TODO
                    case 'regex_title':
                        _regex_title = str(v)  # TODO
                    case 'regex_desc':
                        _regex_desc = str(v)  # TODO
                    case 'apprise':
                        _apprise = str(v)
                    case 'cookies':
                        _cookies = str(v)
                    case 'bgutil':
                        _bgutil = str(v)
                    case 'proxy':
                        _proxy = str(v)
                    case 'arguments' | 'args':
                        _arguments = str(v)
                    case _:
                        log.warning(f'{file}: invalid global value: {k} = {v}')

                del toml[k]
                continue

            if v.get('url') or v.get('u'):
                continue

            if is_url(k):
                # key is url
                toml[k]['url'] = k

            elif is_url(k.removeprefix('!')):
                # !url => remove == True
                toml[k]['delete'] = True
                toml[k]['url'] = k.removeprefix('!')

            elif is_url(k.removeprefix('@')):
                # @url => health == True
                toml[k]['health'] = True
                toml[k]['url'] = k.removeprefix('@')

        #########################
        ## parsing remaining values

        for k, v in toml.copy().items():  # item, cfg
            # basic options
            toml[k]['url'] = v.get('url') or v.get('u') or ''

            toml[k]['quality'] = v.get('quality') or v.get('q') or _quality
            toml[k]['output'] = v.get('output') or v.get('o') or _output
            toml[k]['folder'] = v.get('folder') or v.get('f') or _folder
            toml[k]['delete'] = bool(v.get('delete') or v.get('d') or False)
            toml[k]['health'] = bool(v.get('health') or v.get('h') or _health)

            rgx = v.get('regex') or v.get('r') or _regex
            toml[k]['regex_title'] = v.get('regex_title') or _regex_title or rgx
            toml[k]['regex_desc'] = v.get('regex_desc') or _regex_desc or rgx

            toml[k]['apprise'] = v.get('apprise') or _apprise
            toml[k]['cookies'] = v.get('cookies') or _cookies
            toml[k]['bgutil'] = v.get('bgutil') or _bgutil
            toml[k]['proxy'] = v.get('proxy') or _proxy

            # live-stream checking method
            toml[k]['checker'] = v.get('checker') or v.get('chk') or ''
            if toml[k]['checker'] not in ['str', 'dlp']:
                toml[k]['checker'] = _checker

            # recording method
            toml[k]['recorder'] = v.get('recorder') or v.get('rec') or ''
            if toml[k]['recorder'] not in ['str', 'dlp', 'yta']:
                toml[k]['recorder'] = _recorder

            if not toml[k]['url']:
                # log.trace(f'{file}:{item}: empty url, skipping.')
                toml.pop(k)
                continue

            if not is_url(toml[k]['url']):
                log.warning(
                    f'{file}: {k}: {toml[k]["url"]!r} is not a valid url, skipping.',
                )
                toml.pop(k)
                continue

            is_yt = util.con(['youtube.com', 'youtu.be'], toml[k]['url'])

            # check for ytarchive recorder in non-youtube streams
            if toml[k]['recorder'] == 'yta' and not is_yt:
                log.warning(
                    f'{file}: {k}: recording method is ytarchive, but non-youtube url detected ({toml[k]["url"]}), will fallback to yt-dlp',
                    item=toml[k],
                )
                toml[k]['recorder'] = 'dlp'

            # cli arguments for recorder
            toml[k]['arguments'] = v.get('arguments') or v.get('args') or _arguments

            # choosing specific cli args for recorder
            if not toml[k]['arguments']:
                match toml[k]['recorder']:
                    case 'str':
                        toml[k]['arguments'] = args.str_args

                    case 'dlp':
                        toml[k]['arguments'] = args.dlp_args

                    case 'yta':
                        toml[k]['arguments'] = args.yta_args

            # 'worst' not supported in ytarchive
            if (
                toml[k]['recorder'] == 'yta'
                and toml[k]['quality'] not in util.YTA_Q
                and is_yt
            ):
                log.error(
                    f"{file}: {k}: {toml[k]['quality']!r} not supported in ytarchive, fallback to 'best' for now",
                    file=file,
                    item=k,
                )
                log.info(f'choose something from {", ".join(util.YTA_Q)!r}')
                toml[k]['quality'] = 'best'

            try:
                out_path = Path(toml[k]['output'])
                out_path.mkdir(parents=True, exist_ok=True)
                toml[k]['output'] = str(out_path.resolve())  # subprocess pwd fix
            except:  # noqa: E722
                log.exception(
                    f'{file}: {k}: failed to create output dir: {toml[k]["output"]}'
                )
                continue

            for i in abbrs:
                if i in v:
                    del toml[k][i]

            toml[k] = dict(sorted(toml[k].items()))

        #########################
        ## deleting single-use items

        if cfg_to_del:
            with open(file, 'rb') as f:
                toml_or = tomllib.load(f)

            for item, cfg in toml_or.copy().items():
                if toml[item]['delete'] and toml[item]['url'] == cfg_to_del.get('url'):
                    toml_or.pop(item)

                    path = Path(file)
                    if not path.is_file():
                        continue

                    fst = path.stat()

                    with open(file, 'wb') as f:
                        tomli_w.dump(toml_or, f)

                    os.utime(path, (fst.st_atime, fst.st_mtime))

                    log.warning(f'removed {item!r}')
                    break

        log.trace(f'{file}:\n' + util.pf(toml))

        o.append(toml)

    if not o:
        return o

    # merge dicts
    return reduce(lambda x, y: x | y, o)
