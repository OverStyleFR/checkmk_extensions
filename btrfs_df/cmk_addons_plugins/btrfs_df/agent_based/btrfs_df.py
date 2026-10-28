#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Server-side check plug-in for the "btrfs_df" agent section.
# ---------------------------------------------------------------------------
# Consumes the JSON emitted by the agent plug-in
# (cmk_addons_plugins/btrfs_df/agents/btrfs_df):
#
#   [{"device": ..., "mountpoint": ..., "size_kb": ..., "used_kb": ...,
#     "avail_kb": ..., "phys_size_kb": ..., "inodes_total": ..., "inodes_avail": ...}, ...]
#
# For redundant btrfs profiles (RAID1/5/6/10/dup), the agent sends
# size_kb = used + avail (so that used = real data), which makes Checkmk's
# standard formula (used = size - avail) report the real data usage instead of
# the inflated (size - avail) value caused by the redundancy ratio.
#
# Reuses cmk.plugins.lib.df.df_check_filesystem_single, so the service keeps
# the same features as the built-in "Filesystem" check: graph, trend,
# "full in X days", inodes.
# ---------------------------------------------------------------------------
import json

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    Service,
    Result,
    State,
    render,
    get_value_store,
)
from cmk.plugins.lib.df import df_check_filesystem_single, FILESYSTEM_DEFAULT_PARAMS


def parse_btrfs_df(string_table):
    if not string_table:
        return None
    try:
        data = json.loads(string_table[0][0])
    except (ValueError, IndexError):
        return None
    if not isinstance(data, list):
        return None
    return data


agent_section_btrfs_df = AgentSection(
    name="btrfs_df",
    parse_function=parse_btrfs_df,
)


def discover_btrfs_df(params, section):
    if not section:
        return
    for entry in section:
        mountpoint = entry.get("mountpoint")
        if mountpoint:
            yield Service(item=mountpoint)


def check_btrfs_df(item, params, section):
    entry = None
    for e in (section or []):
        if e.get("mountpoint") == item:
            entry = e
            break
    if entry is None:
        yield Result(state=State.UNKNOWN, summary="No data for this filesystem")
        return

    size_mb = entry["size_kb"] / 1024.0
    avail_mb = entry["avail_kb"] / 1024.0
    reserved_mb = 0.0
    inodes_total = entry.get("inodes_total")
    inodes_avail = entry.get("inodes_avail")

    value_store = get_value_store()
    yield from df_check_filesystem_single(
        value_store=value_store,
        mountpoint=item,
        filesystem_size=size_mb,
        free_space=avail_mb,
        reserved_space=reserved_mb,
        inodes_total=inodes_total,
        inodes_avail=inodes_avail,
        params=params,
    )

    phys = entry.get("phys_size_kb")
    if phys:
        yield Result(
            state=State.OK,
            notice="Physical size: %s (redundant btrfs profile)" % render.bytes(phys * 1024),
        )


check_plugin_btrfs_df = CheckPlugin(
    name="btrfs_df",
    service_name="Btrfs Filesystem %s",
    discovery_function=discover_btrfs_df,
    check_function=check_btrfs_df,
    check_default_parameters=FILESYSTEM_DEFAULT_PARAMS,
    check_ruleset_name="filesystem",
    discovery_default_parameters={},
    discovery_ruleset_name="inventory_df_rules",
)
