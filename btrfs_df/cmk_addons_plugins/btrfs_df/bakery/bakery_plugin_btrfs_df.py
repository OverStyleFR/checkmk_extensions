#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Agent Bakery plug-in (v2) for "btrfs_df".
# Deploys the agent plug-in to monitored hosts when enabled.

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from cmk.bakery.v2_unstable import BakeryPlugin, OS, Plugin


class BtrfsDfConfig(BaseModel):
    deploy: bool = True


def get_btrfs_df_files(conf: BtrfsDfConfig) -> Iterable[Plugin]:
    if not conf.deploy:
        return

    yield Plugin(
        base_os=OS.LINUX,
        source=Path("btrfs_df"),
    )


bakery_plugin_btrfs_df = BakeryPlugin(
    name="btrfs_df",
    parameter_parser=BtrfsDfConfig.model_validate,
    default_parameters=None,
    files_function=get_btrfs_df_files,
)
""" path=/home/tomv/Work/checkmk_extensions/btrfs_df/cmk_addons_plugins/btrfs_df/bakery/bakery_plugin_btrfs_df.py