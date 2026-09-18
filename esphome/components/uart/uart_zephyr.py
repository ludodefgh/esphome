"""Zephyr backend code generation for the uart component (nRF54L15 only for now)."""

import esphome.codegen as cg
from esphome.components.zephyr import (
    zephyr_add_overlay,
    zephyr_add_prj_conf,
    zephyr_data,
)
from esphome.components.zephyr.const import KEY_BOARD
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_NUMBER, CONF_RX_PIN, CONF_TX_PIN
from esphome.core import CORE
from esphome.cpp_generator import MockObj
from esphome.types import ConfigType

DOMAIN = "uart_zephyr"

# Only implemented (and only tested) for this board so far: the serial instance
# names and pin rules below are nRF54L15's. nRF52 boards (uart0/uart1) would
# need their own table.
_NRF54L_BOARDS = ("raytac_an54lq_db_15/nrf54l15/cpuapp",)

# GPIO port -> serial instance. nRF54L15 ties each serial instance family to a
# GPIO port (00 -> P2, 20/21/22 -> P1, 30 -> P0), and:
#  - uart20 is left out: the board already enables it as its console with its
#    own P1.04-P1.07 pinctrl;
#  - uart22 is left out: instance 22 is shared with i2c22, the sensor bus.
_PORT_INSTANCES = {0: "uart30", 1: "uart21", 2: "uart00"}

# UARTE00 is the only instance clocked above 16 MHz (the only one that can hit
# rates such as 256000 exactly), but its P2 pins are NOT freely assignable:
# each function has a fixed pair (Nordic DevZone 120890, and nrf/tests uart
# overlays for nrf54l15dk): RX = P2.00 or P2.07, TX = P2.02 or P2.08.
_UART00_RX_PINS = (64, 71)
_UART00_TX_PINS = (66, 72)


def _state() -> dict:
    return CORE.data.setdefault(DOMAIN, {"by_id": {}, "owners": {}})


def validate_zephyr_uart(config: ConfigType) -> ConfigType:
    board = zephyr_data()[KEY_BOARD]
    if board not in _NRF54L_BOARDS:
        raise cv.Invalid(
            f"UART on Zephyr is only implemented for {', '.join(_NRF54L_BOARDS)} "
            f"so far (board is '{board}')"
        )
    pin_confs = {
        opt: config[opt] for opt in (CONF_TX_PIN, CONF_RX_PIN) if opt in config
    }
    if not pin_confs:
        raise cv.Invalid("A Zephyr UART needs tx_pin and/or rx_pin")
    ports = {pin[CONF_NUMBER] // 32 for pin in pin_confs.values()}
    if len(ports) != 1:
        raise cv.Invalid(
            "tx_pin and rx_pin must be on the same GPIO port: nRF54L serial "
            "instances are tied to one port each"
        )
    port = ports.pop()
    if port not in _PORT_INSTANCES:
        raise cv.Invalid(f"No UART instance is available on GPIO port P{port}")
    instance = _PORT_INSTANCES[port]

    if instance == "uart00":
        if CONF_RX_PIN in pin_confs and pin_confs[CONF_RX_PIN][CONF_NUMBER] not in (
            _UART00_RX_PINS
        ):
            raise cv.Invalid(
                "uart00 (P2) RX must be P2.00 or P2.07: the pins of this instance "
                "are fixed per function",
                path=[CONF_RX_PIN],
            )
        if CONF_TX_PIN in pin_confs and pin_confs[CONF_TX_PIN][CONF_NUMBER] not in (
            _UART00_TX_PINS
        ):
            raise cv.Invalid(
                "uart00 (P2) TX must be P2.02 or P2.08: the pins of this instance "
                "are fixed per function",
                path=[CONF_TX_PIN],
            )

    state = _state()
    uart_id = str(config[CONF_ID])
    owner = state["owners"].setdefault(instance, uart_id)
    if owner != uart_id:
        raise cv.Invalid(
            f"{instance} (GPIO port P{port}) is already used by UART '{owner}'"
        )
    state["by_id"][uart_id] = instance
    return config


async def zephyr_to_code(config: ConfigType) -> "MockObj":
    instance = _state()["by_id"][str(config[CONF_ID])]

    zephyr_add_prj_conf("SERIAL", True)
    # Interrupt-driven, not uart_poll_in(): the nRF UARTE (EasyDMA) only re-arms
    # its next 1-byte reception when the driver is polled again, so any byte
    # arriving between two polls is lost.
    zephyr_add_prj_conf("UART_INTERRUPT_DRIVEN", True)
    # The real baud rate is applied at runtime (uart_configure), because the
    # devicetree `current-speed` enum has no 256000.
    zephyr_add_prj_conf("UART_USE_RUNTIME_CONFIGURE", True)

    psels = []
    if CONF_TX_PIN in config:
        n = config[CONF_TX_PIN][CONF_NUMBER]
        psels.append(f"NRF_PSEL(UART_TX, {n // 32}, {n % 32})")
    rx_psel = None
    if CONF_RX_PIN in config:
        n = config[CONF_RX_PIN][CONF_NUMBER]
        rx_psel = f"NRF_PSEL(UART_RX, {n // 32}, {n % 32})"

    groups = ""
    if psels:
        groups += f"""
                    group1 {{
                        psels = <{psels[0]}>;
                    }};"""
    if rx_psel:
        groups += f"""
                    group2 {{
                        psels = <{rx_psel}>;
                        bias-pull-up;
                    }};"""
    sleep_psels = ", ".join(f"<{p}>" for p in psels + ([rx_psel] if rx_psel else []))

    zephyr_add_overlay(
        f"""
            &pinctrl {{
                {instance}_esphome_default: {instance}_esphome_default {{{groups}
                }};
                {instance}_esphome_sleep: {instance}_esphome_sleep {{
                    group1 {{
                        psels = {sleep_psels};
                        low-power-enable;
                    }};
                }};
            }};

            &{instance} {{
                status = "okay";
                current-speed = <115200>;
                pinctrl-0 = <&{instance}_esphome_default>;
                pinctrl-1 = <&{instance}_esphome_sleep>;
                pinctrl-names = "default", "sleep";
            }};
        """
    )
    if instance == "uart00":
        # spi00 (with its external-flash child mx25r64) is the same hardware
        # block as uart00; the board enables it by default and Zephyr's
        # instance validation refuses both at once. No external flash on the
        # Raytac breakout.
        zephyr_add_overlay(
            """
            &spi00 {
                status = "disabled";
            };

            &mx25r64 {
                status = "disabled";
            };
            """
        )

    return cg.new_Pvariable(
        config[CONF_ID], MockObj(f"DEVICE_DT_GET_OR_NULL(DT_NODELABEL({instance}))")
    )
