#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Agent Bakery ruleset for the "unbound" agent plug-in.
# Decides whether the plug-in is deployed to Linux agents.

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
    """Normalise to {"deploy": bool}."""
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


def _form_spec_agent_config_unbound() -> Dictionary:
    return Dictionary(
        migrate=migrate_bakery_rule,
        help_text=Help(
            "This will deploy the agent plug-in <tt>unbound</tt> for monitoring "
            "the unbound caching/validating DNS resolver. It calls "
            "<tt>unbound-control stats_noreset</tt> (falling back to "
            "<tt>-c /var/unbound/unbound.conf</tt> or "
            "<tt>-c /usr/local/etc/unbound/unbound.conf</tt> on OPNsense/*BSD, "
            "where plain <tt>unbound-control</tt> fails without an explicit "
            "config path) and prints the raw output; "
            "it prints nothing on a host without unbound (or without a "
            "readable control socket), so no service is discovered there. "
            "Runs synchronously with each agent run (no caching).<br><br>"
            "For the full \"Unbound Answers\" breakdown by response code "
            "(NOERROR/SERVFAIL/NXDOMAIN/...), <tt>extended-statistics: yes</tt> "
            "must also be enabled in the monitored host's <tt>unbound.conf</tt> "
            "(on OPNsense: Services > Unbound DNS > Advanced > "
            "\"Enable extended statistics\") - otherwise only the "
            "\"Unbound Cache\" service is discovered.<br><br>"
            "This bakery rule only deploys to Linux hosts. The plug-in itself "
            "also works on *BSD (e.g. FreeBSD/OPNsense), but the Checkmk "
            "agent bakery cannot deploy to those platforms, so there you have "
            "to copy <tt>unbound</tt> into the agent's local plug-in "
            "directory manually."
        ),
        elements={
            "deploy": DictElement(
                required=True,
                parameter_form=BooleanChoice(
                    label=Label("Deploy the Unbound plug-in"),
                    prefill=DefaultValue(True),
                ),
            ),
        },
    )


rule_spec_agent_config_unbound = AgentConfig(
    title=Title("Unbound caching/validating DNS resolver (Linux)"),
    name="unbound",
    topic=Topic.OPERATING_SYSTEM,
    parameter_form=_form_spec_agent_config_unbound,
)
