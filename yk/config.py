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

from .util import YTA_Q, con, pf


def parse(i: list = [], args=None, cfg_to_del: dict = {}):
    o = []

    for file in i:
        toml = {}

        #########################
        ## toml validation

        try:
            if Path(file).is_file():
                with open(file, 'rb') as f:
                    toml = tomllib.load(f)
                    if not toml:
                        continue

            elif is_url(file):
                toml = {file: {}}

        except tomllib.TOMLDecodeError as ex:
            log.exception(f'toml decode error in {file!r}, {ex}')
            continue

        except FileNotFoundError as ex:
            log.exception(f"file {file!r} not found', {ex}")
            continue

        except AssertionError:
            log.exception(f'file {file!r} is empty')
            continue

        except Exception as ex:
            log.exception(f'file error in {file!r}, {ex}')
            continue

        # log.trace(f'stock {file}:\n' + pf(toml))

        for item in toml.copy().keys():
            if toml[item].get('url') or toml[item].get('u'):
                continue

            if is_url(item):
                # key is url
                toml[item]['url'] = item

            elif is_url(item.removeprefix('!')):
                # !url => removing
                toml[item]['delete'] = True
                toml[item]['url'] = item.removeprefix('!')

            elif is_url(item.removeprefix('@')):
                # @url => healthcheck
                toml[item]['health'] = True
                toml[item]['url'] = item.removeprefix('@')

        #########################
        ## parsing remaining values

        for item, cfg in toml.copy().items():
            # basic options
            toml[item]['url'] = cfg.get('url') or cfg.get('u') or ''
            toml[item]['quality'] = cfg.get('quality') or cfg.get('q') or 'best'
            toml[item]['output'] = cfg.get('output') or cfg.get('o') or args.output
            toml[item]['folder'] = cfg.get('folder') or cfg.get('f') or ''
            toml[item]['delete'] = bool(cfg.get('delete') or cfg.get('d') or False)
            toml[item]['health'] = bool(cfg.get('health') or cfg.get('h') or False)

            rgx = cfg.get('regex') or cfg.get('r') or ''
            toml[item]['regex_title'] = cfg.get('regex_title') or rgx
            toml[item]['regex_desc'] = cfg.get('regex_desc') or rgx

            toml[item]['proxy'] = cfg.get('proxy') or (
                random.choice(args.proxy) if args.proxy else ''
            )
            toml[item]['apprise'] = cfg.get('apprise') or args.apprise
            toml[item]['cookies'] = cfg.get('cookies') or args.cookies
            toml[item]['bgutil'] = cfg.get('bgutil') or args.bgutil

            # live-stream checking method
            toml[item]['checker'] = cfg.get('checker') or cfg.get('chk') or args.chk
            if toml[item]['checker'] not in ['str', 'dlp']:
                toml[item]['checker'] = args.chk

            # recording method
            toml[item]['recorder'] = cfg.get('recorder') or cfg.get('rec') or args.rec
            if toml[item]['recorder'] not in ['str', 'dlp', 'yta']:
                toml[item]['recorder'] = args.rec

            # check for ytarchive recorder for non-youtube streams
            if toml[item]['recorder'] == 'yta' and not con(
                ['youtube.com', 'youtu.be'], toml[item]['url']
            ):
                log.warning(
                    f'{file}: {item}: recording method is ytarchive, but non-youtube url detected ({toml[item]["url"]}), will fallback to yt-dlp',
                    item=toml[item],
                )
                toml[item]['recorder'] = 'dlp'

            # cli arguments for recorder
            toml[item]['arguments'] = (
                cfg.get('record_arguments') or cfg.get('rec_args') or None
            )

            # choosing specific cli args for recorder
            if not toml[item]['arguments']:
                match toml[item]['recorder']:
                    case 'str':
                        toml[item]['arguments'] = args.str_args

                    case 'dlp':
                        toml[item]['arguments'] = args.dlp_args

                    case 'yta':
                        toml[item]['arguments'] = args.yta_args

            # 'worst' not supported in ytarchive
            if (
                toml[item]['recorder'] == 'yta'
                and toml[item]['quality'] not in YTA_Q
                and ('youtube' in toml[item]['url'] or 'youtu.be' in toml[item]['url'])
            ):
                log.error(
                    f"{file}: {item}: {toml[item]['quality']!r} not supported in ytarchive, fallback to 'best' for now",
                    file=file,
                    item=item,
                )
                log.info(f'choose something from {", ".join(YTA_Q)!r}')
                toml[item]['quality'] = 'best'

            if not toml[item]['url']:
                # log.trace(f'{file}:{item}: empty url, skipping.')
                toml.pop(item)
                continue

            if not is_url(toml[item]['url']):
                log.warning(
                    f'{file}: {item}: {cfg["url"]!r} is not a valid url, skipping.',
                )
                toml.pop(item)
                continue

            try:
                out_path = Path(toml[item]['output'])
                out_path.mkdir(parents=True, exist_ok=True)
                toml[item]['output'] = str(out_path.resolve())  # subprocess pwd fix
            except:  # noqa: E722
                log.exception(
                    f'{file}:{item}: failed to create output dir: {toml[item]["output"]}'
                )
                continue

            for i in ('u', 'f', 'r', 'q', 'd', 'h', 'o'):
                if i in cfg:
                    del toml[item][i]

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

        log.trace(f'{file}:\n' + pf(toml))

        o.append(toml)

    if not o:
        return o

    # return merged dicts
    return reduce(lambda x, y: x | y, o)
