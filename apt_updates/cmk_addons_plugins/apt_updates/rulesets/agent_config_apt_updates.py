#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Agent Bakery ruleset for the "apt_updates" agent plug-in.

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


def _form_spec_agent_config_apt_updates() -> Dictionary:
    return Dictionary(
        migrate=migrate_bakery_rule,
        help_text=Help(
            "This will deploy the agent plug-in <tt>apt_updates</tt> for "
            "monitoring the number of upgradable packages (all and security) "
            "on Debian hosts."
        ),
        elements={
            "deploy": DictElement(
                required=True,
                parameter_form=BooleanChoice(
                    label=Label("Deploy the apt_updates plug-in"),
                    prefill=DefaultValue(True),
                ),
            ),
        },
    )


rule_spec_agent_config_apt_updates = AgentConfig(
    title=Title("apt_updates"),
    name="apt_updates",
    topic=Topic.OPERATING_SYSTEM,
    parameter_form=_form_spec_agent_config_apt_updates(),
)
