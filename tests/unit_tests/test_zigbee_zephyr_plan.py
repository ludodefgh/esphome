"""Tests for standard_clusters endpoint planning in the Zephyr Zigbee backend."""

from pathlib import Path

import pytest

from esphome.components.zigbee.const import KEY_ZIGBEE
from esphome.components.zigbee.const_zephyr import (
    CONF_STANDARD_CLUSTERS,
    KEY_EP_NUMBER,
    KEY_STD_ENTITIES,
    KEY_STD_PLAN,
)
from esphome.components.zigbee.zigbee_zephyr import (
    MAX_CLUSTERS_PER_EP,
    _kind_for,
    plan_zephyr_endpoints,
)
from esphome.const import (
    DEVICE_CLASS_CARBON_DIOXIDE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_PRESENCE,
    DEVICE_CLASS_TEMPERATURE,
)
from esphome.core import CORE


class _Id:
    """Stands in for an ESPHome ID: identity matters, not its (still unset) name."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return self.name


def _setup(entities: list[tuple[str, str, str | None]], extra_slots: int = 0):
    """entities: (id name, domain, device_class); extra_slots: switches/numbers."""
    ids = {name: _Id(name) for name, _, _ in entities}
    CORE.data[KEY_ZIGBEE] = {
        KEY_EP_NUMBER: [""] * (len(entities) + extra_slots),
        KEY_STD_ENTITIES: [(ids[n], d, c) for n, d, c in entities],
    }
    return ids


def _plan():
    return CORE.data[KEY_ZIGBEE][KEY_STD_PLAN]


@pytest.fixture(autouse=True)
def _core(setup_core: Path) -> None:
    CORE.data.pop(KEY_ZIGBEE, None)


@pytest.mark.parametrize(
    ("domain", "device_class", "kind"),
    [
        ("sensor", DEVICE_CLASS_TEMPERATURE, "temperature"),
        ("sensor", DEVICE_CLASS_HUMIDITY, "humidity"),
        ("sensor", DEVICE_CLASS_ILLUMINANCE, "illuminance"),
        ("sensor", DEVICE_CLASS_CARBON_DIOXIDE, "co2"),
        ("sensor", DEVICE_CLASS_PM25, "pm25"),
        ("sensor", None, "analog_input"),
        ("sensor", "pm10", "analog_input"),
        ("binary_sensor", DEVICE_CLASS_OCCUPANCY, "occupancy"),
        ("binary_sensor", DEVICE_CLASS_PRESENCE, "occupancy"),
        ("binary_sensor", DEVICE_CLASS_MOTION, "binary_input"),
        ("binary_sensor", None, "binary_input"),
    ],
)
def test_kind_for(domain: str, device_class: str | None, kind: str) -> None:
    assert _kind_for(domain, device_class) == kind


def test_disabled_by_default_leaves_slots_alone() -> None:
    _setup([("a", "sensor", None), ("b", "sensor", None)])
    plan_zephyr_endpoints({CONF_STANDARD_CLUSTERS: False})
    assert KEY_STD_PLAN not in CORE.data[KEY_ZIGBEE]
    assert CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER] == ["", ""]


def test_different_cluster_types_share_an_endpoint() -> None:
    ids = _setup(
        [
            ("t", "sensor", DEVICE_CLASS_TEMPERATURE),
            ("h", "sensor", DEVICE_CLASS_HUMIDITY),
            ("l", "sensor", DEVICE_CLASS_ILLUMINANCE),
        ]
    )
    plan_zephyr_endpoints({CONF_STANDARD_CLUSTERS: True})
    plan = _plan()
    assert len(plan["endpoints"]) == 1
    assert {plan["by_id"][str(i)][0] for i in ids.values()} == {0}
    assert CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER] == ["zigbee_ep1_ep"]


def test_same_cluster_type_needs_its_own_endpoint() -> None:
    # A cluster type can only appear once per endpoint: three analog inputs
    # cannot share one.
    ids = _setup([(n, "sensor", None) for n in "abc"])
    plan_zephyr_endpoints({CONF_STANDARD_CLUSTERS: True})
    plan = _plan()
    assert [plan["by_id"][str(ids[n])][0] for n in "abc"] == [0, 1, 2]
    assert len(plan["endpoints"]) == 3


def test_first_fit_backfills_earlier_endpoints() -> None:
    ids = _setup(
        [
            ("ai1", "sensor", None),
            ("ai2", "sensor", None),
            ("temp", "sensor", DEVICE_CLASS_TEMPERATURE),
        ]
    )
    plan_zephyr_endpoints({CONF_STANDARD_CLUSTERS: True})
    by_id = _plan()["by_id"]
    # temperature fits next to the first analog input instead of opening a 3rd endpoint
    assert by_id[str(ids["temp"])] == (0, "temperature")
    assert len(_plan()["endpoints"]) == 2


def test_endpoint_cluster_cap() -> None:
    kinds = [
        DEVICE_CLASS_TEMPERATURE,
        DEVICE_CLASS_HUMIDITY,
        DEVICE_CLASS_ILLUMINANCE,
        DEVICE_CLASS_CARBON_DIOXIDE,
        DEVICE_CLASS_PM25,
    ]
    assert len(kinds) == MAX_CLUSTERS_PER_EP
    _setup([(f"s{i}", "sensor", k) for i, k in enumerate(kinds)] + [("v", "sensor", None)])
    plan_zephyr_endpoints({CONF_STANDARD_CLUSTERS: True})
    # five standard clusters fill endpoint 1; the analog input still fits nowhere
    # there once it is full, so it opens endpoint 2
    plan = _plan()
    assert [len(e) for e in plan["endpoints"]] == [MAX_CLUSTERS_PER_EP, 1]


def test_switches_and_numbers_keep_their_own_slots() -> None:
    _setup(
        [("t", "sensor", DEVICE_CLASS_TEMPERATURE), ("h", "sensor", DEVICE_CLASS_HUMIDITY)],
        extra_slots=2,
    )
    plan_zephyr_endpoints({CONF_STANDARD_CLUSTERS: True})
    # 1 shared endpoint for the two sensors + the 2 reserved for switch/number
    assert CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER] == ["zigbee_ep1_ep", "", ""]


def test_full_node_fits_under_the_zboss_limit() -> None:
    """The 14 entities that motivated this (10 air sensors, radar, fan) in <= 8 endpoints."""
    entities = [
        ("presence", "binary_sensor", DEVICE_CLASS_PRESENCE),
        ("moving", "binary_sensor", DEVICE_CLASS_MOTION),
        ("still", "binary_sensor", DEVICE_CLASS_OCCUPANCY),
        ("temp", "sensor", DEVICE_CLASS_TEMPERATURE),
        ("hum", "sensor", DEVICE_CLASS_HUMIDITY),
        ("lux", "sensor", DEVICE_CLASS_ILLUMINANCE),
        ("co2", "sensor", DEVICE_CLASS_CARBON_DIOXIDE),
        ("pm1", "sensor", "pm1"),
        ("pm25", "sensor", DEVICE_CLASS_PM25),
        ("pm4", "sensor", None),
        ("pm10", "sensor", "pm10"),
        ("voc", "sensor", None),
        ("nox", "sensor", None),
        ("count", "sensor", None),
    ]
    _setup(entities, extra_slots=1)  # the fan number
    plan_zephyr_endpoints({CONF_STANDARD_CLUSTERS: True})
    assert len(CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER]) <= 8
    # and no endpoint ever carries the same cluster type twice
    for kinds in _plan()["endpoints"]:
        assert len(kinds) == len(set(kinds))
        assert len(kinds) <= MAX_CLUSTERS_PER_EP
