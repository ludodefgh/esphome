"""I2S microphone (INMP441 and similar) sound level on Zephyr (nRF54L15 only for now).

ESPHome's `microphone` / `sound_level` stack is ESP32-only (ESP-IDF I2S driver,
audio and ring_buffer components), so this is a standalone sensor platform: it
owns i2s20, reads the microphone as an I2S controller (drives BCLK + LRCLK) and
publishes the RMS level in dBFS.
"""

from esphome import pins
import esphome.codegen as cg
from esphome.components import sensor
from esphome.components.zephyr import zephyr_add_overlay, zephyr_add_prj_conf, zephyr_data
from esphome.components.zephyr.const import KEY_BOARD
import esphome.config_validation as cv
from esphome.const import (
    CONF_CHANNEL,
    CONF_ID,
    CONF_NUMBER,
    CONF_OFFSET,
    CONF_SAMPLE_RATE,
    STATE_CLASS_MEASUREMENT,
    UNIT_DECIBEL,
)

DEPENDENCIES = ["zephyr"]

CONF_BCLK_PIN = "bclk_pin"
CONF_LRCLK_PIN = "lrclk_pin"
CONF_DIN_PIN = "din_pin"
CONF_LEFT = "left"
CONF_RIGHT = "right"

# Only the Raytac AN54LQ-15 is known to work: instance names and the
# family -> GPIO port rule below are nRF54L15's.
_NRF54L_BOARDS = ("raytac_an54lq_db_15/nrf54l15/cpuapp",)
# nRF54L ties each serial instance family to one GPIO port (20/21/22 -> P1).
_I2S_PORT = 1

zephyr_i2s_mic_ns = cg.esphome_ns.namespace("zephyr_i2s_mic")
ZephyrI2SMic = zephyr_i2s_mic_ns.class_(
    "ZephyrI2SMic", sensor.Sensor, cg.PollingComponent
)


def _validate(config):
    board = zephyr_data()[KEY_BOARD]
    if board not in _NRF54L_BOARDS:
        raise cv.Invalid(
            f"zephyr_i2s_mic is only implemented for {', '.join(_NRF54L_BOARDS)} "
            f"so far (board is '{board}')"
        )
    for opt in (CONF_BCLK_PIN, CONF_LRCLK_PIN, CONF_DIN_PIN):
        if config[opt][CONF_NUMBER] // 32 != _I2S_PORT:
            raise cv.Invalid(
                f"i2s20 can only use GPIO port P{_I2S_PORT} pins", path=[opt]
            )
    return config


CONFIG_SCHEMA = cv.All(
    sensor.sensor_schema(
        ZephyrI2SMic,
        unit_of_measurement=UNIT_DECIBEL,
        icon="mdi:microphone",
        accuracy_decimals=1,
        state_class=STATE_CLASS_MEASUREMENT,
    )
    .extend(
        {
            cv.Required(CONF_BCLK_PIN): pins.internal_gpio_output_pin_schema,
            cv.Required(CONF_LRCLK_PIN): pins.internal_gpio_output_pin_schema,
            cv.Required(CONF_DIN_PIN): pins.internal_gpio_input_pin_schema,
            cv.Optional(CONF_SAMPLE_RATE, default=16000): cv.int_range(
                min=8000, max=48000
            ),
            # INMP441: L/R (SEL) low -> left slot, high -> right slot.
            cv.Optional(CONF_CHANNEL, default=CONF_LEFT): cv.one_of(
                CONF_LEFT, CONF_RIGHT, lower=True
            ),
            # Added to the dBFS value. 0 publishes plain dBFS; ~120 turns an
            # INMP441 (-26 dBFS at 94 dB SPL) into an approximate dB SPL.
            cv.Optional(CONF_OFFSET, default=0.0): cv.float_,
        }
    )
    .extend(cv.polling_component_schema("5s")),
    cv.only_on_nrf52,
    _validate,
)


def _psel(fun: str, pin: dict) -> str:
    n = pin[CONF_NUMBER]
    return f"NRF_PSEL({fun}, {n // 32}, {n % 32})"


async def to_code(config):
    zephyr_add_prj_conf("I2S", True)

    psels = [
        _psel("I2S_SCK_M", config[CONF_BCLK_PIN]),
        _psel("I2S_LRCK_M", config[CONF_LRCLK_PIN]),
        _psel("I2S_SDIN", config[CONF_DIN_PIN]),
    ]
    psel_list = ", ".join(f"<{p}>" for p in psels)
    zephyr_add_overlay(
        f"""
        &pinctrl {{
            i2s20_esphome_default: i2s20_esphome_default {{
                group1 {{
                    psels = {psel_list};
                }};
            }};
            i2s20_esphome_sleep: i2s20_esphome_sleep {{
                group1 {{
                    psels = {psel_list};
                    low-power-enable;
                }};
            }};
        }};

        &i2s20 {{
            status = "okay";
            pinctrl-0 = <&i2s20_esphome_default>;
            pinctrl-1 = <&i2s20_esphome_sleep>;
            pinctrl-names = "default", "sleep";
        }};
        """
    )

    var = await sensor.new_sensor(
        config,
        cg.RawExpression("DEVICE_DT_GET_OR_NULL(DT_NODELABEL(i2s20))"),
    )
    await cg.register_component(var, config)
    cg.add(var.set_sample_rate(config[CONF_SAMPLE_RATE]))
    cg.add(var.set_right_channel(config[CONF_CHANNEL] == CONF_RIGHT))
    cg.add(var.set_offset(config[CONF_OFFSET]))
