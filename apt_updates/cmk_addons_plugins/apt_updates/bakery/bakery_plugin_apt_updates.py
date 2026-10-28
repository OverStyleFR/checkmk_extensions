#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Agent Bakery plug-in (v2) for "apt_updates".

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from cmk.bakery.v2_unstable import BakeryPlugin, OS, Plugin


class AptUpdatesConfig(BaseModel):
    deploy: bool = True


def get_apt_updates_files(conf: AptUpdatesConfig) -> Iterable[Plugin]:
    if not conf.deploy:
        return

    yield Plugin(
        base_os=OS.LINUX,
        source=Path("apt_updates"),
    )


bakery_plugin_apt_updates = BakeryPlugin(
    name="apt_updates",
    parameter_parser=AptUpdatesConfig.model_validate,
    default_parameters=None,
    files_function=get_apt_updates_files,
)
