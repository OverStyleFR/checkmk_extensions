#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Agent Bakery plug-in (v2) for "unbound".
# Turns the AgentConfig ruleset value into the deployed agent plug-in file.
# The plug-in is deployed to run synchronously (no caching) -- calling
# unbound-control once per agent run is cheap.

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from cmk.bakery.v2_unstable import BakeryPlugin, OS, Plugin


class UnboundConfig(BaseModel):
    deploy: bool


def get_unbound_files(conf: UnboundConfig) -> Iterable[Plugin]:
    if not conf.deploy:
        return

    yield Plugin(
        base_os=OS.LINUX,
        source=Path("unbound"),
    )


bakery_plugin_unbound = BakeryPlugin(
    name="unbound",
    parameter_parser=UnboundConfig.model_validate,
    default_parameters=None,
    files_function=get_unbound_files,
)
