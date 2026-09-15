#!/usr/bin/env python3
"""Graphing plug-in for the Unbound DNS resolver checks.

Requires the cmk.graphing.v1 API -> Checkmk 2.3.0 or newer.
"""
from cmk.graphing.v1 import Title, graphs, metrics

_UNIT_QPS = metrics.Unit(metrics.DecimalNotation("/s"))

metric_unbound_answers_NOERROR = metrics.Metric(
    name="unbound_answers_NOERROR",
    title=Title("Rate of NOERROR answers"),
    unit=_UNIT_QPS,
    color=metrics.Color.LIGHT_GREEN,
)

metric_unbound_answers_FORMERR = metrics.Metric(
    name="unbound_answers_FORMERR",
    title=Title("Rate of FORMERR answers"),
    unit=_UNIT_QPS,
    color=metrics.Color.ORANGE,
)

metric_unbound_answers_SERVFAIL = metrics.Metric(
    name="unbound_answers_SERVFAIL",
    title=Title("Rate of SERVFAIL answers"),
    unit=_UNIT_QPS,
    color=metrics.Color.RED,
)

metric_unbound_answers_NXDOMAIN = metrics.Metric(
    name="unbound_answers_NXDOMAIN",
    title=Title("Rate of NXDOMAIN answers"),
    unit=_UNIT_QPS,
    color=metrics.Color.PURPLE,
)

metric_unbound_answers_NOTIMPL = metrics.Metric(
    name="unbound_answers_NOTIMPL",
    title=Title("Rate of NOTIMPL answers"),
    unit=_UNIT_QPS,
    color=metrics.Color.DARK_ORANGE,
)

metric_unbound_answers_REFUSED = metrics.Metric(
    name="unbound_answers_REFUSED",
    title=Title("Rate of REFUSED answers"),
    unit=_UNIT_QPS,
    color=metrics.Color.DARK_RED,
)

metric_unbound_answers_nodata = metrics.Metric(
    name="unbound_answers_nodata",
    title=Title("Rate of answers without data"),
    unit=_UNIT_QPS,
    color=metrics.Color.GRAY,
)

graph_unbound_answers = graphs.Graph(
    name="unbound_answers",
    title=Title("Rate of answers"),
    simple_lines=[
        "unbound_answers_NOERROR",
        "unbound_answers_FORMERR",
        "unbound_answers_SERVFAIL",
        "unbound_answers_NXDOMAIN",
        "unbound_answers_NOTIMPL",
        "unbound_answers_REFUSED",
        "unbound_answers_nodata",
    ],
)

metric_unbound_cache_hit_rate = metrics.Metric(
    name="unbound_cache_hit_rate",
    title=Title("Cache hits per second"),
    unit=_UNIT_QPS,
    color=metrics.Color.DARK_GREEN,
)

metric_unbound_cache_misses_rate = metrics.Metric(
    name="unbound_cache_misses_rate",
    title=Title("Cache misses per second"),
    unit=_UNIT_QPS,
    color=metrics.Color.DARK_RED,
)

graph_unbound_cache_hit_misses = graphs.Graph(
    name="unbound_cache_hit_misses",
    title=Title("Cache hits and misses"),
    simple_lines=[
        "unbound_cache_hit_rate",
        "unbound_cache_misses_rate",
    ],
)
