import esphome.codegen as cg
from esphome.components import binary_sensor
import esphome.config_validation as cv
from esphome.const import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
    ENTITY_CATEGORY_DIAGNOSTIC,
)

from . import CONF_NPM1300_ID, Npm1300Component

DEPENDENCIES = ["npm1300"]

CONF_USB_CONNECTED = "usb_connected"
CONF_CHARGING = "charging"
CONF_CHARGE_COMPLETE = "charge_complete"
CONF_CHARGER_ERROR = "charger_error"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_NPM1300_ID): cv.use_id(Npm1300Component),
        cv.Optional(CONF_USB_CONNECTED): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_PLUG
        ),
        cv.Optional(CONF_CHARGING): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_BATTERY_CHARGING
        ),
        cv.Optional(CONF_CHARGE_COMPLETE): binary_sensor.binary_sensor_schema(),
        cv.Optional(CONF_CHARGER_ERROR): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_PROBLEM,
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NPM1300_ID])
    for key in (CONF_USB_CONNECTED, CONF_CHARGING, CONF_CHARGE_COMPLETE, CONF_CHARGER_ERROR):
        if conf := config.get(key):
            sens = await binary_sensor.new_binary_sensor(conf)
            cg.add(getattr(parent, f"set_{key}_binary_sensor")(sens))
