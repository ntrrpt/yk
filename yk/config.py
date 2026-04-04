#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import tomllib
from functools import reduce
from pathlib import Path

import tomli_w
from loguru import logger as log
from validators import url as is_url

from .util import YTA_Q, pf


def parse_configs(files: list = [], cfg_to_del: dict = {}, args=None):
    tomls = []

    for file in files:
        toml = {}

        #########################
        ## toml validation

        try:
            with open(file, 'rb') as f:
                toml = tomllib.load(f)

            assert toml  # empty check

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

        # log.trace(f'stock {file}:\n' + pf(toml))

        #########################
        ## finding single-use items via '@' prefix in key

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
            toml[item]['url'] = cfg.get('url') or cfg.get('u') or ''
            toml[item]['folder'] = cfg.get('folder') or cfg.get('f') or ''
            toml[item]['quality'] = cfg.get('quality') or cfg.get('q') or 'best'
            toml[item]['delete'] = bool(cfg.get('delete') or cfg.get('d') or False)
            toml[item]['health'] = bool(cfg.get('health') or False)

            rgx = cfg.get('regex') or cfg.get('r') or ''
            toml[item]['regex_title'] = cfg.get('regex_title', rgx)
            toml[item]['regex_desc'] = cfg.get('regex_desc', rgx)

            if not toml[item]['url']:
                log.trace(f'{file}:{item}: empty url, skipping.')
                toml.pop(item)
                continue

            if not is_url(toml[item]['url']):
                log.warning(
                    f'{file}:{item}: {cfg["url"]!r} is not a valid url, skipping.'
                )
                toml.pop(item)
                continue

            for i in ('u', 'f', 'r', 'q', 'd'):
                if i in cfg:
                    del toml[item][i]

            if (
                args.yta
                and toml[item]['quality'] not in YTA_Q
                and ('youtube' in toml[item]['url'] or 'youtu.be' in toml[item]['url'])
            ):
                log.error(
                    f"{toml[item]['quality']!r} not supported in ytarchive, fallback to 'best' for now",
                    file=file,
                    item=item,
                )
                log.info(f'choose something from {", ".join(YTA_Q)!r}')
                toml[item]['quality'] = 'best'

        #########################
        ## deleting single-use items

        if cfg_to_del:
            with open(file, 'rb') as f:
                toml_or = tomllib.load(f)

            for item, cfg in toml_or.copy().items():
                if toml[item]['delete'] and toml[item]['url'] == cfg_to_del.get('url'):
                    toml_or.pop(item)

                    path = Path(file)
                    fst = path.stat()

                    with open(file, 'wb') as f:
                        tomli_w.dump(toml_or, f)

                    os.utime(path, (fst.st_atime, fst.st_mtime))

                    log.warning(f'removed {item!r}')
                    break

        log.trace(f'{file}:\n' + pf(toml))

        tomls.append(toml)

    # return merged dicts
    return reduce(lambda x, y: x | y, tomls)
