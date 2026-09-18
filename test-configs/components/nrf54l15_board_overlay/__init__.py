"""Bring-up overlay for the Raytac AN54LQ-15 DB board.

raytac_an54lq_db_15_common.dtsi aliases watchdog0 -> &wdt31, but wdt31 (like
every peripheral node in the nRF54L SoC dtsi) ships status = "disabled" by
default; the board file never turns it on. nrf52's to_code() unconditionally
requests CONFIG_WATCHDOG, and esphome/components/zephyr/hal.cpp resolves it
via DEVICE_DT_GET(DT_ALIAS(watchdog0)) - which needs the node actually
enabled, not just aliased. Scoped to this test as a project overlay rather
than patched into the nrf52 component itself, since the right node per
nRF54 family/board isn't known generically yet (see MultiSensors issue #25).
"""

from esphome.components.zephyr import zephyr_add_overlay, zephyr_add_prj_conf
import esphome.config_validation as cv

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    zephyr_add_overlay(
        """
        &wdt31 {
            status = "okay";
        };
        """
    )

    # RTT logging: what the `debug` component would enable, without the rest
    # of it - debug_zephyr.cpp pokes nRF52-specific NRF_UICR fields
    # (PSELRESET/NFCPINS/NRFFW/NRFHW) that don't exist on nRF54L15's UICR
    # layout, so pulling in `debug:` wholesale fails to compile on this SoC.
    # logger_zephyr.cpp's write_msg_() already calls printk() unconditionally
    # when CONFIG_PRINTK is set (on by default) - routing printk to RTT here
    # is enough, paired with `logger: baud_rate: 0` in the YAML so the logger
    # component skips its UART path entirely (no uart0 on this board either).
    #
    # RTT_CONSOLE lives under `if CONSOLE` in
    # zephyr/drivers/console/Kconfig, but nrf52's to_code() sets
    # CONFIG_CONSOLE=False as a soft default (required=False) - silently
    # dropped RTT_CONSOLE from .config entirely (no build error, just no
    # console backend, so printk() had nowhere to go). nrf52's to_code()
    # runs at CoroPriority.PLATFORM, ahead of this component's default
    # priority, so its softer False is already on record by the time this
    # runs and a required=True override here doesn't conflict.
    zephyr_add_prj_conf("CONSOLE", True)
    zephyr_add_prj_conf("USE_SEGGER_RTT", True)
    zephyr_add_prj_conf("RTT_CONSOLE", True)
