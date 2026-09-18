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

from esphome.components.zephyr import zephyr_add_overlay
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
