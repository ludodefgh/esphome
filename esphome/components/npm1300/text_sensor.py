import esphome.codegen as cg
from esphome.components import text_sensor
import esphome.config_validation as cv
from esphome.const import ENTITY_CATEGORY_DIAGNOSTIC

from . import CONF_NPM1300_ID, Npm1300Component

DEPENDENCIES = ["npm1300"]

CONF_CHARGER_STATUS = "charger_status"
CONF_CHARGER_ERROR = "charger_error"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_NPM1300_ID): cv.use_id(Npm1300Component),
        cv.Optional(CONF_CHARGER_STATUS): text_sensor.text_sensor_schema(
            icon="mdi:battery-charging"
        ),
        cv.Optional(CONF_CHARGER_ERROR): text_sensor.text_sensor_schema(
            icon="mdi:battery-alert",
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_NPM1300_ID])
    for key in (CONF_CHARGER_STATUS, CONF_CHARGER_ERROR):
        if conf := config.get(key):
            sens = await text_sensor.new_text_sensor(conf)
            cg.add(getattr(parent, f"set_{key}_text_sensor")(sens))
