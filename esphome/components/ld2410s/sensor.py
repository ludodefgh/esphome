import esphome.codegen as cg
from esphome.components import sensor
import esphome.config_validation as cv
from esphome.const import DEVICE_CLASS_DISTANCE, STATE_CLASS_MEASUREMENT, UNIT_CENTIMETER

from . import CONF_LD2410S_ID, LD2410SComponent

DEPENDENCIES = ["ld2410s"]

CONF_TARGET_DISTANCE = "target_distance"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_LD2410S_ID): cv.use_id(LD2410SComponent),
        cv.Optional(CONF_TARGET_DISTANCE): sensor.sensor_schema(
            unit_of_measurement=UNIT_CENTIMETER,
            accuracy_decimals=0,
            device_class=DEVICE_CLASS_DISTANCE,
            state_class=STATE_CLASS_MEASUREMENT,
            icon="mdi:signal-distance-variant",
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_LD2410S_ID])
    if conf := config.get(CONF_TARGET_DISTANCE):
        sens = await sensor.new_sensor(conf)
        cg.add(parent.set_target_distance_sensor(sens))
