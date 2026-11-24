import esphome.codegen as cg
from esphome.components import binary_sensor
import esphome.config_validation as cv
from esphome.const import CONF_HAS_TARGET, DEVICE_CLASS_OCCUPANCY

from . import CONF_LD2410S_ID, LD2410SComponent

DEPENDENCIES = ["ld2410s"]

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_LD2410S_ID): cv.use_id(LD2410SComponent),
        cv.Optional(CONF_HAS_TARGET): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_OCCUPANCY, icon="mdi:motion-sensor"
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_LD2410S_ID])
    if conf := config.get(CONF_HAS_TARGET):
        sens = await binary_sensor.new_binary_sensor(conf)
        cg.add(parent.set_has_target_binary_sensor(sens))
