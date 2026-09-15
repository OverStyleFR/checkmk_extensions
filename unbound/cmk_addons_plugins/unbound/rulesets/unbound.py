#!/usr/bin/env python3
"""WATO check parameter rulesets for the Unbound DNS resolver checks."""

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    CascadingSingleChoice,
    CascadingSingleChoiceElement,
    DefaultValue,
    Dictionary,
    DictElement,
    Float,
    LevelDirection,
    Percentage,
    SimpleLevels,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostCondition, Topic


def _parameter_form_unbound_cache() -> Dictionary:
    return Dictionary(
        title=Title("Unbound: Cache"),
        elements={
            "cache_misses": DictElement(
                required=False,
                parameter_form=SimpleLevels(
                    title=Title("Levels on cache misses per second"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(),
                    prefill_fixed_levels=DefaultValue((10.0, 100.0)),
                ),
            ),
            "cache_hits": DictElement(
                required=False,
                parameter_form=SimpleLevels(
                    title=Title("Lower levels for hits in %"),
                    level_direction=LevelDirection.LOWER,
                    form_spec_template=Percentage(),
                    prefill_fixed_levels=DefaultValue((90.0, 80.0)),
                ),
            ),
        },
    )


rule_spec_unbound_cache = CheckParameters(
    name="unbound_cache",
    title=Title("Unbound Cache"),
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_unbound_cache,
    condition=HostCondition(),
)


_ANSWERS = (
    "NOERROR",
    "FORMERR",
    "SERVFAIL",
    "NXDOMAIN",
    "NOTIMPL",
    "REFUSED",
    "nodata",
)


def _levels_choice_for(answer: str) -> CascadingSingleChoice:
    return CascadingSingleChoice(
        title=Title("Upper levels for %s answers") % answer,
        prefill=DefaultValue("rate"),
        elements=[
            CascadingSingleChoiceElement(
                name="rate",
                title=Title("Upper levels for rate of %s answers") % answer,
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(unit_symbol="qps"),
                    prefill_fixed_levels=DefaultValue((10.0, 100.0)),
                ),
            ),
            CascadingSingleChoiceElement(
                name="ratio",
                title=Title("Upper levels for ratio of %s answers") % answer,
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Percentage(),
                    prefill_fixed_levels=DefaultValue((10.0, 100.0)),
                ),
            ),
        ],
    )


def _parameter_form_unbound_answers() -> Dictionary:
    return Dictionary(
        title=Title("Unbound Answers"),
        help_text=Help(
            "Upper levels either on the rate (queries per second) or on the "
            "ratio (percentage of all answers) of a given answer type."
        ),
        elements={
            f"levels_upper_{answer}": DictElement(
                required=False,
                parameter_form=_levels_choice_for(answer),
            )
            for answer in _ANSWERS
        },
    )


rule_spec_unbound_answers = CheckParameters(
    name="unbound_answers",
    title=Title("Unbound Answers"),
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_unbound_answers,
    condition=HostCondition(),
)


def _parameter_form_unbound_unwanted_replies() -> Dictionary:
    return Dictionary(
        title=Title("Unbound: Unwanted Replies"),
        help_text=Help(
            "Upper levels on the rate of replies unbound received that it "
            "did not request (no matching outstanding query). A sustained "
            "increase can indicate DNS cache poisoning/spoofing attempts "
            "against the resolver, but the sensible threshold strongly "
            "depends on the resolver's query volume."
        ),
        elements={
            "levels_upper": DictElement(
                required=False,
                parameter_form=SimpleLevels(
                    title=Title("Levels on unwanted replies per second"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(unit_symbol="qps"),
                    prefill_fixed_levels=DefaultValue((10.0, 100.0)),
                ),
            ),
        },
    )


rule_spec_unbound_unwanted_replies = CheckParameters(
    name="unbound_unwanted_replies",
    title=Title("Unbound Unwanted Replies"),
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_unbound_unwanted_replies,
    condition=HostCondition(),
)
