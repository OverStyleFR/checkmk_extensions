#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Agent Bakery ruleset for the "btrfs_df" agent plug-in.

from collections.abc import Mapping

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
)
from cmk.rulesets.v1.rule_specs import AgentConfig, Topic


def migrate_bakery_rule(value: object) -> Mapping[str, object]:
    match value:
        case bool(deploy):
            return {"deploy": deploy}
        case None:
            return {"deploy": False}
        case dict() as d if "deploy" in d:
            return {"deploy": bool(d["deploy"])}
        case dict():
            return {"deploy": True}
    raise ValueError(value)


def _form_spec_agent_config_btrfs_df() -> Dictionary:
    return Dictionary(
        migrate=migrate_bakery_rule,
        help_text=Help(
            "This will deploy the agent plug-in <tt>btrfs_df</tt> for "
            "monitoring redundant btrfs volumes (RAID1/5/6/10/dup) with "
            "corrected disk usage (real data instead of size - avail)."
        ),
        elements={
            "deploy": DictElement(
                required=True,
                parameter_form=BooleanChoice(
                    label=Label("Deploy the btrfs_df plug-in"),
                    prefill=DefaultValue(True),
                ),
            ),
        },
    )


rule_spec_agent_config_btrfs_df = AgentConfig(
    title=Title("btrfs_df"),
    name="btrfs_df",
    topic=Topic.OPERATING_SYSTEM,
    parameter_form=_form_spec_agent_config_btrfs_df(),
)
""" path=/home/tomv/Work/checkmk_extensions/btrfs_df/cmk_addons_plugins/btrfs_df/rulesets/agent_config_btrfs_df.py