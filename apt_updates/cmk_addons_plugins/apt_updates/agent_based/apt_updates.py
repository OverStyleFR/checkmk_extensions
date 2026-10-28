#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Server-side check plug-ins for the "apt_updates" agent section.
# ---------------------------------------------------------------------------
# Consumes the JSON emitted by the agent plug-in
# (cmk_addons_plugins/apt_updates/agents/apt_updates):
#
#   {"critical": <int>, "total": <int>}
#
# Produces two services:
#   * "APT Critical Updates" - number of upgradable security packages
#   * "APT All Updates"      - number of all upgradable packages (excl. holds)
#
# Thresholds are configurable per host via the WATO rulesets
# "apt_critical_updates" and "apt_all_updates".
# ---------------------------------------------------------------------------
import json

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    Service,
    Result,
    State,
    Metric,
    render,
)
from cmk.rulesets.v1.form_specs import SimpleLevels


def parse_apt_updates(string_table):
    if not string_table:
        return None
    try:
        data = json.loads(string_table[0][0])
    except (ValueError, IndexError):
        return None
    if not isinstance(data, dict):
        return None
    return data


agent_section_apt_updates = AgentSection(
    name="apt_updates",
    parse_function=parse_apt_updates,
)


def discover_apt_critical_updates(section):
    if section is not None:
        yield Service()


def discover_apt_all_updates(section):
    if section is not None:
        yield Service()


def _levels(params):
    lv = params.get("levels", ("fixed", (1, 9999)))
    if isinstance(lv, (tuple, list)) and len(lv) == 2 and lv[0] in ("fixed", "no_levels"):
        lv = tuple(lv)
    else:
        lv = ("fixed", (1, 9999))
    if lv[0] == "no_levels":
        return None
    return (float(lv[1][0]), float(lv[1][1]))


def check_apt_critical_updates(params, section):
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No data")
        return
    count = int(section.get("critical", 0) or 0)
    levels = _levels(params)
    state = State.OK
    if levels:
        warn, crit = levels
        if count >= crit:
            state = State.CRIT
        elif count >= warn:
            state = State.WARN
    yield Result(
        state=state,
        summary="%d security package(s) to update" % count,
    )
    yield Metric(
        "packages", count,
        levels=levels if levels else None,
        boundaries=(0, None),
    )


def check_apt_all_updates(params, section):
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No data")
        return
    count = int(section.get("total", 0) or 0)
    levels = _levels(params)
    state = State.OK
    if levels:
        warn, crit = levels
        if count >= crit:
            state = State.CRIT
        elif count >= warn:
            state = State.WARN
    yield Result(
        state=state,
        summary="%d package(s) to update" % count,
    )
    yield Metric(
        "packages", count,
        levels=levels if levels else None,
        boundaries=(0, None),
    )


check_plugin_apt_critical_updates = CheckPlugin(
    name="apt_critical_updates",
    service_name="APT Critical Updates",
    sections=["apt_updates"],
    discovery_function=discover_apt_critical_updates,
    check_function=check_apt_critical_updates,
    check_default_parameters={"levels": ("fixed", (1, 9999))},
    check_ruleset_name="apt_critical_updates",
)

check_plugin_apt_all_updates = CheckPlugin(
    name="apt_all_updates",
    service_name="APT All Updates",
    sections=["apt_updates"],
    discovery_function=discover_apt_all_updates,
    check_function=check_apt_all_updates,
    check_default_parameters={"levels": ("fixed", (1, 9999))},
    check_ruleset_name="apt_all_updates",
)
