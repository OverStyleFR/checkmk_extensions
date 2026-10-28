#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Graphing plug-in for the "btrfs_df" check.
#
# The check emits fs_used / fs_size / fs_free in MiB (as df_check_filesystem_single
# does). The built-in fs_used metric is defined in bytes, so without this
# translation the graph would show MiB values as bytes (factor 1e6 too small).
# Scale by 1 MiB to recover correct byte values.

from cmk.graphing.v1.translations import PassiveCheck, ScaleBy, Translation

MIB = 1024.0**2

translation_btrfs_df = Translation(
    name="btrfs_df",
    check_commands=[PassiveCheck("btrfs_df")],
    translations={
        "fs_used": ScaleBy(MIB),
        "fs_size": ScaleBy(MIB),
        "fs_free": ScaleBy(MIB),
        "growth": ScaleBy(MIB),
        "trend": ScaleBy(MIB),
        "trend_hoursleft": ScaleBy(3600),
        "reserved": ScaleBy(MIB),
    },
)
