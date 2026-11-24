"""nPM1300 LDO1/LDO2 used as load switches (LSIN -> LSOUT).

MultiSensors Battery: load switch 1 (LSIN1 = +3V3, LSOUT1 = P3V3_SW) powers the
LD2410S radar on J4. The output is off at PMIC power-up; restore_mode decides
what the firmware does at boot.
"""

import esphome.codegen as cg
from esphome.components import switch
import esphome.config_validation as cv
from esphome.const import CONF_CHANNEL
from esphome.core import CORE

from . import CONF_NPM1300_ID, Npm1300Component, npm1300_ns

DEPENDENCIES = ["npm1300"]

Npm1300LoadSwitch = npm1300_ns.class_("Npm1300LoadSwitch", switch.Switch, cg.Component)


def _claim_channel(config):
    used = CORE.data.setdefault("npm1300", {}).setdefault("load_switches", set())
    if config[CONF_CHANNEL] in used:
        raise cv.Invalid(f"load switch {config[CONF_CHANNEL]} is already configured")
    used.add(config[CONF_CHANNEL])
    return config


CONFIG_SCHEMA = cv.All(
    switch.switch_schema(
        Npm1300LoadSwitch, icon="mdi:power-plug", default_restore_mode="ALWAYS_OFF"
    )
    .extend(
        {
            cv.GenerateID(CONF_NPM1300_ID): cv.use_id(Npm1300Component),
            cv.Required(CONF_CHANNEL): cv.one_of(1, 2, int=True),
        }
    )
    .extend(cv.COMPONENT_SCHEMA),
    _claim_channel,
)


async def to_code(config):
    await cg.get_variable(config[CONF_NPM1300_ID])
    var = await switch.new_switch(config)
    await cg.register_component(var, config)
    cg.add(
        var.set_regulator(
            cg.RawExpression(f"DEVICE_DT_GET(DT_NODELABEL(npm1300_ldo{config[CONF_CHANNEL]}))")
        )
    )
