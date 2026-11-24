"""Hi-Link LD2410S (low-power 24 GHz presence radar), read-only.

Parses the standard report frame of the HLK-LD2410S user manual v1.3 (section 7.2):
F4 F3 F2 F1 | length (2 bytes, LE) | target state (1 byte: 0/1 nobody, 2/3 somebody)
| distance (2 bytes, cm) | reserved | F8 F7 F6 F5, at 115200 8N1.

Not hardware-validated. No configuration commands yet: the manual's parameter table
(7.3.6) lists the same parameter word for two settings, so writing parameters waits
for a real module to check against.
"""

import esphome.codegen as cg
from esphome.components import uart
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = ["@ludodefgh"]
DEPENDENCIES = ["uart"]
MULTI_CONF = True

CONF_LD2410S_ID = "ld2410s_id"

ld2410s_ns = cg.esphome_ns.namespace("ld2410s")
LD2410SComponent = ld2410s_ns.class_("LD2410SComponent", cg.Component, uart.UARTDevice)

CONFIG_SCHEMA = (
    cv.Schema({cv.GenerateID(): cv.declare_id(LD2410SComponent)})
    .extend(uart.UART_DEVICE_SCHEMA)
    .extend(cv.COMPONENT_SCHEMA)
)

FINAL_VALIDATE_SCHEMA = uart.final_validate_device_schema(
    "ld2410s", require_rx=True, baud_rate=115200, data_bits=8, parity="NONE", stop_bits=1
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
