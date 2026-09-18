"""Tests for the Zephyr UART backend's board/pin/instance rules."""

from pathlib import Path

import pytest

from esphome.components.uart import uart_zephyr
from esphome.components.uart.uart_zephyr import DOMAIN, validate_zephyr_uart
from esphome.components.zephyr.const import KEY_BOARD, KEY_ZEPHYR
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_NUMBER, CONF_RX_PIN, CONF_TX_PIN
from esphome.core import CORE

BOARD = "raytac_an54lq_db_15/nrf54l15/cpuapp"


def _cfg(uart_id: str, tx: int | None = None, rx: int | None = None) -> dict:
    cfg = {CONF_ID: uart_id}
    if tx is not None:
        cfg[CONF_TX_PIN] = {CONF_NUMBER: tx}
    if rx is not None:
        cfg[CONF_RX_PIN] = {CONF_NUMBER: rx}
    return cfg


@pytest.fixture(autouse=True)
def _zephyr_board(setup_core: Path) -> None:
    CORE.data[KEY_ZEPHYR] = {KEY_BOARD: BOARD}
    CORE.data.pop(DOMAIN, None)


def _instance(uart_id: str) -> str:
    return uart_zephyr._state()["by_id"][uart_id]


def test_p2_pins_select_uart00() -> None:
    # P2.08 = 2*32+8, P2.07 = 2*32+7: what firmware-nrf54l15 wires the LD2450 to
    validate_zephyr_uart(_cfg("radar", tx=72, rx=71))
    assert _instance("radar") == "uart00"


@pytest.mark.parametrize(("tx", "rx"), [(66, 64), (72, 64), (66, 71)])
def test_uart00_accepts_every_fixed_pin_pair(tx: int, rx: int) -> None:
    validate_zephyr_uart(_cfg("u", tx=tx, rx=rx))
    assert _instance("u") == "uart00"


def test_uart00_rejects_free_choice_of_rx_pin() -> None:
    # P2.03: UARTE00 RX can only be P2.00 or P2.07 (PSEL writes succeed but do nothing)
    with pytest.raises(cv.Invalid, match="RX must be P2.00 or P2.07"):
        validate_zephyr_uart(_cfg("u", tx=72, rx=67))


def test_uart00_rejects_free_choice_of_tx_pin() -> None:
    with pytest.raises(cv.Invalid, match="TX must be P2.02 or P2.08"):
        validate_zephyr_uart(_cfg("u", tx=67, rx=71))


@pytest.mark.parametrize(("pin", "instance"), [(32 + 4, "uart21"), (0, "uart30")])
def test_other_ports_pick_their_instance(pin: int, instance: str) -> None:
    validate_zephyr_uart(_cfg("u", tx=pin, rx=pin + 1))
    assert _instance("u") == instance


def test_tx_and_rx_on_different_ports_rejected() -> None:
    with pytest.raises(cv.Invalid, match="same GPIO port"):
        validate_zephyr_uart(_cfg("u", tx=72, rx=32 + 5))


def test_two_uarts_on_the_same_port_rejected() -> None:
    validate_zephyr_uart(_cfg("a", tx=72, rx=71))
    with pytest.raises(cv.Invalid, match="already used by UART 'a'"):
        validate_zephyr_uart(_cfg("b", tx=66, rx=64))


def test_revalidating_the_same_uart_is_fine() -> None:
    validate_zephyr_uart(_cfg("a", tx=72, rx=71))
    validate_zephyr_uart(_cfg("a", tx=72, rx=71))


def test_unsupported_board_rejected() -> None:
    CORE.data[KEY_ZEPHYR] = {KEY_BOARD: "adafruit_feather_nrf52840"}
    with pytest.raises(cv.Invalid, match="only implemented for"):
        validate_zephyr_uart(_cfg("u", tx=8, rx=9))
