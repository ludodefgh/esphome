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

    # logger: hardware_uart only ever tries `uart0`/`uart1`/USB CDC, via
    # DT_NODELABEL() (logger_zephyr.cpp) - a devicetree *label* lookup, not
    # an *alias* lookup (DT_ALIAS(), what the watchdog fix above actually
    # uses). Neither label exists on this SoC at all (real peripheral labels
    # are uart00/uart20/uart21/uart22/uart30 - no plain "uart0"), so
    # `aliases { uart0 = &uart20; }` doesn't help DT_NODELABEL() and
    # `&uart0 { ... }` (logger/__init__.py's own overlay, needed once
    # baud_rate > 0) fails to compile outright ("undefined node label
    # 'uart0'"). USB_CDC (baud_rate>0's other option) fails the same way -
    # needs a `zephyr_udc0` node this breakout doesn't have wired at all.
    # Getting ESPHome's own logger output onto uart20 (the board's actual
    # default console UART, already enabled) needs DT_NODELABEL(uart0)
    # itself made board-aware in logger_zephyr.cpp, a real but separate fix
    # (see MultiSensors issue #25) - not done here. `baud_rate: 0` stays the
    # working choice for now: RTT keeps carrying Zephyr's own printk()
    # output (banner, asserts, etc.) since that path never goes through
    # Logger's baud_rate gate at all; only ESPHome's *own* ESP_LOGx lines are
    # unavailable until that fix lands, verified instead by reading sensor
    # state directly from target RAM over the debug probe.

    # RTT logging: what the `debug` component would enable, without the rest
    # of it - debug_zephyr.cpp pokes nRF52-specific NRF_UICR fields
    # (PSELRESET/NFCPINS/NRFFW/NRFHW) that don't exist on nRF54L15's UICR
    # layout, so pulling in `debug:` wholesale fails to compile on this SoC.
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
