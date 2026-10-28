#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Check parameters for "APT All Updates": warn/crit on number of
# upgradable packages (excluding held packages).

from collections.abc import Mapping

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    LevelDirection,
    SimpleLevels,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostCondition, Topic


def _migrate(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        return {"levels": ("fixed", (1, 9999))}
    lv = value.get("levels")
    if isinstance(lv, (tuple, list)) and len(lv) == 2 and lv[0] in ("fixed", "no_levels"):
        return {**value, "levels": tuple(lv)}
    if isinstance(lv, (tuple, list)) and len(lv) == 2 and all(
        isinstance(x, (int, float)) for x in lv
    ):
        return {**value, "levels": ("fixed", (int(lv[0]), int(lv[1])))}
    return {**value, "levels": ("no_levels", None)}


def _form_spec() -> Dictionary:
    return Dictionary(
        migrate=_migrate,
        elements={
            "levels": DictElement(
                required=True,
                parameter_form=SimpleLevels[int](
                    title=Title("Levels on number of upgradable packages"),
                    help_text=Help(
                        "Warning/critical levels on the number of upgradable "
                        "packages (held packages excluded). Choose 'No levels' "
                        "to always report OK."
                    ),
                    form_spec_template=Integer(),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((1, 9999)),
                ),
            ),
        },
    )


rule_spec_apt_all_updates = CheckParameters(
    title=Title("APT all updates"),
    name="apt_all_updates",
    topic=Topic.OPERATING_SYSTEM,
    parameter_form=_form_spec(),
    condition=HostCondition(),
)
