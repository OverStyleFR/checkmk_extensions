#!/usr/bin/env python3

# Copyright (C) 2022, Jan-Philipp Litza (PLUTEX) <jpl@plutex.de>.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


from typing import (
    Any,
    Mapping,
    Union,
)

from cmk.agent_based.v1 import check_levels
from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    get_rate,
    get_value_store,
    GetRateError,
    render,
    Service,
    StringTable,
)

UnboundSection = Mapping[str, Union[int, float, "UnboundSection"]]


def render_qps(x: float) -> str:
    return f"{x:.2f}/s"


def _legacy_levels(raw_levels: Any) -> tuple[float, float] | None:
    """Convert a SimpleLevels ruleset value into the legacy (warn, crit) tuple
    expected by cmk.agent_based.v1.check_levels, or None if no levels are set."""
    if raw_levels is None:
        return None
    mode, value = raw_levels
    if mode in ("no_levels", "cast"):
        return None
    if mode == "fixed":
        return value
    return None


def parse_unbound(string_table: StringTable) -> UnboundSection:
    section = {}
    for key, value in string_table:
        try:
            section[key] = int(value)
        except ValueError:
            section[key] = float(value)
    return section


agent_section_unbound = AgentSection(
    name="unbound",
    parse_function=parse_unbound,
)


def discover_unbound_cache(section: UnboundSection) -> DiscoveryResult:
    if "total.num.cachehits" in section and "total.num.cachemiss" in section:
        yield Service()


def check_unbound_cache(
    params: Mapping[str, Any],
    section: UnboundSection,
) -> CheckResult:
    cumulative_cache_hits = section.get("total.num.cachehits")
    cumulative_cache_miss = section.get("total.num.cachemiss")
    now = section.get("time.now")

    if None in (cumulative_cache_hits, cumulative_cache_miss, now):
        return

    cache_hits = get_rate(
        get_value_store(),
        "unbound_cache_hits",
        now,
        cumulative_cache_hits,
        raise_overflow=True,
    )
    cache_miss = get_rate(
        get_value_store(),
        "unbound_cache_miss",
        now,
        cumulative_cache_miss,
        raise_overflow=True,
    )
    total = cache_hits + cache_miss
    hit_perc = (cache_hits / float(total)) * 100.0 if total != 0 else 100.0

    yield from check_levels(
        value=cache_miss,
        metric_name="unbound_cache_misses_rate",
        levels_upper=_legacy_levels(params.get("cache_misses")),
        render_func=render_qps,
        label="Cache Misses",
        notice_only=True,
    )

    yield from check_levels(
        value=cache_hits,
        metric_name="unbound_cache_hit_rate",
        render_func=render_qps,
        label="Cache Hits",
        notice_only=True,
    )

    yield from check_levels(
        value=hit_perc,
        metric_name="cache_hit_ratio",
        levels_lower=_legacy_levels(params.get("cache_hits")),
        render_func=render.percent,
        label="Cache Hit Ratio",
    )


check_plugin_unbound_cache = CheckPlugin(
    name="unbound_cache",
    service_name="Unbound Cache",
    sections=["unbound"],
    discovery_function=discover_unbound_cache,
    check_function=check_unbound_cache,
    check_default_parameters={},
    check_ruleset_name="unbound_cache",
)


def discover_unbound_answers(section: UnboundSection) -> DiscoveryResult:
    if "time.now" in section and "num.answer.rcode.SERVFAIL" in section:
        yield Service()


def check_unbound_answers(params: Mapping, section: UnboundSection) -> CheckResult:
    key_prefix = "num.answer.rcode."
    if "time.now" not in section:
        return

    now = section["time.now"]

    total = sum(value for key, value in section.items() if key.startswith(key_prefix))

    for key, value in section.items():
        if not key.startswith(key_prefix):
            continue
        answer = key[len(key_prefix) :]

        try:
            rate = get_rate(
                get_value_store(),
                f"unbound_answers_{answer}",
                now,
                value,
                raise_overflow=True,
            )
        except GetRateError:
            pass
        else:
            raw_levels = params.get(f"levels_upper_{answer}")
            levels_upper = None
            if raw_levels is not None:
                mode, simple_levels = raw_levels
                warn_crit = _legacy_levels(simple_levels)
                if warn_crit is not None:
                    warn, crit = warn_crit
                    if mode == "ratio":
                        # levels on the ratio of answers, given in percent
                        levels_upper = (warn / 100.0 * total, crit / 100.0 * total)
                    else:
                        levels_upper = (warn, crit)
            yield from check_levels(
                value=rate,
                levels_upper=levels_upper,
                metric_name=f"unbound_answers_{answer}",
                render_func=render_qps,
                label=answer,
                notice_only=f"levels_upper_{answer}" not in params,
            )


check_plugin_unbound_answers = CheckPlugin(
    name="unbound_answers",
    service_name="Unbound Answers",
    sections=["unbound"],
    discovery_function=discover_unbound_answers,
    check_function=check_unbound_answers,
    check_default_parameters={
        "levels_upper_SERVFAIL": ("rate", ("fixed", (10.0, 100.0))),
        "levels_upper_REFUSED": ("rate", ("fixed", (10.0, 100.0))),
    },
    check_ruleset_name="unbound_answers",
)


def discover_unbound_unwanted_replies(section: UnboundSection) -> DiscoveryResult:
    if "time.now" in section and "unwanted.replies" in section:
        yield Service()


def check_unbound_unwanted_replies(
    params: Mapping[str, Any],
    section: UnboundSection,
) -> CheckResult:
    if "time.now" not in section or "unwanted.replies" not in section:
        return

    rate = get_rate(
        get_value_store(),
        "unbound_unwanted_replies",
        section["time.now"],
        section["unwanted.replies"],
        raise_overflow=True,
    )

    yield from check_levels(
        value=rate,
        levels_upper=_legacy_levels(params.get("levels_upper")),
        metric_name="unbound_unwanted_replies",
        render_func=render_qps,
        label="Unwanted Replies",
    )


check_plugin_unbound_unwanted_replies = CheckPlugin(
    name="unbound_unwanted_replies",
    service_name="Unbound Unwanted Replies",
    sections=["unbound"],
    discovery_function=discover_unbound_unwanted_replies,
    check_function=check_unbound_unwanted_replies,
    check_default_parameters={"levels_upper": ("fixed", (10.0, 100.0))},
    check_ruleset_name="unbound_unwanted_replies",
)
