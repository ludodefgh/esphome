from dataclasses import dataclass
import datetime
import random

import esphome.codegen as cg
from esphome.components.zephyr import zephyr_add_prj_conf
import esphome.config_validation as cv
from esphome.const import (
    CONF_DEVICE_CLASS,
    CONF_ID,
    CONF_MODEL,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_CARBON_DIOXIDE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_PRESENCE,
    DEVICE_CLASS_TEMPERATURE,
    __version__,
)
from esphome.core import ID, CORE, CoroPriority, coroutine_with_priority
from esphome.cpp_generator import (
    AssignmentExpression,
    MockObj,
    VariableDeclarationExpression,
)
from esphome.types import ConfigType

from .const import (
    BACNET_UNIT_NO_UNITS,
    BACNET_UNITS,
    CONF_POWER_SOURCE,
    CONF_ROUTER,
    CONF_WIPE_ON_BOOT,
    KEY_ZIGBEE,
    POWER_SOURCE,
    AnalogAttrs,
    AnalogAttrsOutput,
    BinaryAttrs,
    ZigbeeComponent,
    zigbee_ns,
)
from .const_zephyr import (
    CONF_IEEE802154_VENDOR_OUI,
    CONF_SLEEPY,
    CONF_STANDARD_CLUSTERS,
    CONF_ZIGBEE_BINARY_SENSOR,
    CONF_ZIGBEE_ID,
    CONF_ZIGBEE_NUMBER,
    CONF_ZIGBEE_SENSOR,
    CONF_ZIGBEE_SWITCH,
    KEY_EP_NUMBER,
    KEY_EP_SPECS,
    KEY_STD_ENTITIES,
    KEY_STD_PLAN,
    ZB_ZCL_BASIC_ATTRS_EXT_T,
    ZB_ZCL_CLUSTER_ID_ANALOG_INPUT,
    ZB_ZCL_CLUSTER_ID_ANALOG_OUTPUT,
    ZB_ZCL_CLUSTER_ID_BASIC,
    ZB_ZCL_CLUSTER_ID_BINARY_INPUT,
    ZB_ZCL_CLUSTER_ID_BINARY_OUTPUT,
    ZB_ZCL_CLUSTER_ID_IDENTIFY,
    ZB_ZCL_IDENTIFY_ATTRS_T,
)

ZigbeeBinarySensor = zigbee_ns.class_("ZigbeeBinarySensor", cg.Component)
ZigbeeSensor = zigbee_ns.class_("ZigbeeSensor", cg.Component)
ZigbeeSwitch = zigbee_ns.class_("ZigbeeSwitch", cg.Component)
ZigbeeNumber = zigbee_ns.class_("ZigbeeNumber", cg.Component)
ZigbeeStandardSensor = zigbee_ns.class_("ZigbeeStandardSensor", cg.Component)
ZigbeeOccupancySensor = zigbee_ns.class_("ZigbeeOccupancySensor", cg.Component)
StandardKind = zigbee_ns.enum("StandardKind", True)

zephyr_binary_sensor = cv.Schema(
    {
        cv.OnlyWith(CONF_ZIGBEE_ID, ["nrf52", "zigbee"]): cv.use_id(ZigbeeComponent),
        cv.OnlyWith(CONF_ZIGBEE_BINARY_SENSOR, ["nrf52", "zigbee"]): cv.declare_id(
            ZigbeeBinarySensor
        ),
    }
)

zephyr_sensor = cv.Schema(
    {
        cv.OnlyWith(CONF_ZIGBEE_ID, ["nrf52", "zigbee"]): cv.use_id(ZigbeeComponent),
        cv.OnlyWith(CONF_ZIGBEE_SENSOR, ["nrf52", "zigbee"]): cv.declare_id(
            ZigbeeSensor
        ),
    }
)

zephyr_switch = cv.Schema(
    {
        cv.OnlyWith(CONF_ZIGBEE_ID, ["nrf52", "zigbee"]): cv.use_id(ZigbeeComponent),
        cv.OnlyWith(CONF_ZIGBEE_SWITCH, ["nrf52", "zigbee"]): cv.declare_id(
            ZigbeeSwitch
        ),
    }
)

zephyr_number = cv.Schema(
    {
        cv.OnlyWith(CONF_ZIGBEE_ID, ["nrf52", "zigbee"]): cv.use_id(ZigbeeComponent),
        cv.OnlyWith(CONF_ZIGBEE_NUMBER, ["nrf52", "zigbee"]): cv.declare_id(
            ZigbeeNumber
        ),
    }
)


async def zephyr_to_code(config: ConfigType) -> "MockObj":
    from esphome.components.nrf52.framework import uses_zigbee_addon

    zephyr_add_prj_conf("ZIGBEE_ADD_ON" if uses_zigbee_addon() else "ZIGBEE", True)
    zephyr_add_prj_conf("ZIGBEE_APP_UTILS", True)
    if config[CONF_ROUTER]:
        zephyr_add_prj_conf("ZIGBEE_ROLE_ROUTER", True)
    else:
        zephyr_add_prj_conf("ZIGBEE_ROLE_END_DEVICE", True)

    zephyr_add_prj_conf("ZIGBEE_CHANNEL_SELECTION_MODE_MULTI", True)

    zephyr_add_prj_conf("CRYPTO", True)

    zephyr_add_prj_conf("NET_IPV6", False)
    zephyr_add_prj_conf("NET_IP_ADDR_CHECK", False)
    zephyr_add_prj_conf("NET_UDP", False)

    # disable all extra to reduce power and save flash
    zephyr_add_prj_conf("ZIGBEE_HAVE_SERIAL", False)
    zephyr_add_prj_conf("ZBOSS_ERROR_PRINT_TO_LOG", False)
    zephyr_add_prj_conf("DK_LIBRARY", False)

    cg.add_build_flag("-Wl,--wrap=zb_zcl_put_reporting_info_from_req")

    # Wrap the transceiver sleep/receive/transmit calls to measure how long the
    # radio is powered down. The span between a zb_trans_enter_sleep() and the
    # following zb_trans_enter_receive() or zb_trans_transmit() is time the
    # radio spent asleep.
    cg.add_build_flag("-Wl,--wrap=zb_trans_enter_sleep")
    cg.add_build_flag("-Wl,--wrap=zb_trans_enter_receive")
    cg.add_build_flag("-Wl,--wrap=zb_trans_transmit")

    if CONF_IEEE802154_VENDOR_OUI in config:
        zephyr_add_prj_conf("IEEE802154_VENDOR_OUI_ENABLE", True)
        random_number = config[CONF_IEEE802154_VENDOR_OUI]
        if random_number == "random":
            random_number = random.randint(0x000000, 0xFFFFFF)
        zephyr_add_prj_conf("IEEE802154_VENDOR_OUI", random_number)

    if config[CONF_WIPE_ON_BOOT]:
        if config[CONF_WIPE_ON_BOOT] == "once":
            cg.add_define(
                "USE_ZIGBEE_WIPE_ON_BOOT_MAGIC", random.randint(0x000001, 0xFFFFFF)
            )
        cg.add_define("USE_ZIGBEE_WIPE_ON_BOOT")

    # Generate attribute lists before any await that could yield (e.g., build_automation
    # waiting for variables from other components). If the hub's priority decays while
    # yielding, deferred entity jobs may add cluster list globals that reference these
    # attribute lists before they're declared.
    await _attr_to_code(config)

    var = cg.new_Pvariable(config[CONF_ID])

    await cg.register_component(var, config)

    CORE.add_job(_ctx_to_code, config)

    cg.add(var.set_sleepy(config[CONF_SLEEPY]))

    return var


async def _attr_to_code(config: ConfigType) -> None:
    # Create the basic attributes structure and attribute list
    basic_attrs = zigbee_new_variable("zigbee_basic_attrs", ZB_ZCL_BASIC_ATTRS_EXT_T)
    zigbee_new_attr_list(
        "zigbee_basic_attrib_list",
        "ZB_ZCL_DECLARE_BASIC_ATTRIB_LIST_EXT",
        zigbee_assign(basic_attrs.zcl_version, cg.RawExpression("ZB_ZCL_VERSION")),
        zigbee_assign(basic_attrs.app_version, 0),
        zigbee_assign(basic_attrs.stack_version, 0),
        zigbee_assign(basic_attrs.hw_version, 0),
        zigbee_set_string(basic_attrs.mf_name, "esphome"),
        zigbee_set_string(basic_attrs.model_id, config[CONF_MODEL]),
        zigbee_set_string(
            basic_attrs.date_code,
            # Local build time, matching the esp32 implementation
            # (App.get_build_time() in C++).
            datetime.datetime.now().astimezone().strftime("%Y%m%d %H%M%S"),
        ),
        zigbee_assign(
            basic_attrs.power_source,
            POWER_SOURCE[config[CONF_POWER_SOURCE]],
        ),
        zigbee_set_string(basic_attrs.location_id, ""),
        zigbee_assign(
            basic_attrs.ph_env, cg.RawExpression("ZB_ZCL_BASIC_ENV_UNSPECIFIED")
        ),
        zigbee_set_string(basic_attrs.sw_ver, __version__),
    )

    # Create the identify attributes structure and attribute list
    identify_attrs = zigbee_new_variable(
        "zigbee_identify_attrs", ZB_ZCL_IDENTIFY_ATTRS_T
    )
    zigbee_new_attr_list(
        "zigbee_identify_attrib_list",
        "ZB_ZCL_DECLARE_IDENTIFY_ATTRIB_LIST",
        zigbee_assign(
            identify_attrs.identify_time,
            cg.RawExpression("ZB_ZCL_IDENTIFY_IDENTIFY_TIME_DEFAULT_VALUE"),
        ),
    )


def zigbee_new_variable(name: str, type_: str) -> cg.MockObj:
    """Create a global variable with the given name and type."""
    decl = VariableDeclarationExpression(type_, "", name)
    CORE.add_global(decl)
    return MockObj(name, ".")


def zigbee_assign(target: cg.MockObj, expression: cg.RawExpression | int) -> str:
    """Assign an expression to a target and return a reference to it."""
    cg.add(AssignmentExpression("", "", target, expression))
    return f"&{target}"


def zigbee_set_string(target: cg.MockObj, value: str) -> str:
    """Set a ZCL string value and return the target name (arrays decay to pointers)."""
    # Zigbee supports only ASCII
    value = value.encode("ascii", "ignore").decode()
    cg.add(
        cg.RawExpression(
            f"ZB_ZCL_SET_STRING_VAL({target}, {cg.safe_exp(value)}, ZB_ZCL_STRING_CONST_SIZE({cg.safe_exp(value)}))"
        )
    )
    return str(target)


def zigbee_new_attr_list(name: str, macro: str, *args: str) -> str:
    """Create an attribute list using a ZBOSS macro and return the name."""
    obj = cg.RawExpression(f"{macro}({name}, {', '.join(args)})")
    CORE.add_global(obj)
    return name


class ZigbeeClusterDesc:
    """Represents a Zigbee cluster descriptor for code generation."""

    def __init__(self, cluster_id: str, attr_list_name: str | None = None) -> None:
        self._cluster_id = cluster_id
        self._attr_list_name = attr_list_name

    @property
    def cluster_id(self) -> str:
        return self._cluster_id

    @property
    def has_attrs(self) -> bool:
        return self._attr_list_name is not None

    def __str__(self) -> str:
        role = (
            "ZB_ZCL_CLUSTER_SERVER_ROLE"
            if self._attr_list_name
            else "ZB_ZCL_CLUSTER_CLIENT_ROLE"
        )
        if self._attr_list_name:
            attr_count = f"ZB_ZCL_ARRAY_SIZE({self._attr_list_name}, zb_zcl_attr_t)"
            return f"ZB_ZCL_CLUSTER_DESC({self._cluster_id}, {attr_count}, {self._attr_list_name}, {role}, ZB_ZCL_MANUF_CODE_INVALID)"
        return f"ZB_ZCL_CLUSTER_DESC({self._cluster_id}, 0, NULL, {role}, ZB_ZCL_MANUF_CODE_INVALID)"


def zigbee_new_cluster_list(
    name: str, clusters: list[ZigbeeClusterDesc]
) -> tuple[str, list[ZigbeeClusterDesc]]:
    """Create a cluster list array and return its name and the clusters."""
    # Always include basic and identify clusters first
    all_clusters = [
        ZigbeeClusterDesc(ZB_ZCL_CLUSTER_ID_BASIC, "zigbee_basic_attrib_list"),
        ZigbeeClusterDesc(ZB_ZCL_CLUSTER_ID_IDENTIFY, "zigbee_identify_attrib_list"),
    ]
    all_clusters.extend(clusters)

    cluster_strs = [str(c) for c in all_clusters]
    CORE.add_global(
        cg.RawExpression(
            f"zb_zcl_cluster_desc_t {name}[] = {{{', '.join(cluster_strs)}}}"
        )
    )
    return (name, all_clusters)


def zigbee_register_ep(
    ep_name: str,
    cluster_list_name: str,
    report_attr_count: int,
    clusters: list[ZigbeeClusterDesc],
    slot_index: int,
    app_device_id: str,
) -> None:
    """Register a Zigbee endpoint."""
    in_cluster_num = sum(1 for c in clusters if c.has_attrs)
    out_cluster_num = len(clusters) - in_cluster_num
    cluster_ids = [c.cluster_id for c in clusters]

    # Store endpoint name for device context generation
    CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER][slot_index] = ep_name

    # Generate the endpoint declaration
    ep_id = slot_index + 1  # Endpoints are 1-indexed
    obj = cg.RawExpression(
        f"ESPHOME_ZB_HA_DECLARE_EP({ep_name}, {ep_id}, {cluster_list_name}, "
        f"{in_cluster_num}, {out_cluster_num}, {report_attr_count}, {app_device_id}, {', '.join(cluster_ids)})"
    )
    CORE.add_global(obj)


@coroutine_with_priority(CoroPriority.LATE)
async def _ctx_to_code(config: ConfigType) -> None:
    _emit_planned_endpoints()
    cg.add_define("ZIGBEE_ENDPOINTS_COUNT", len(CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER]))
    cg.add_global(
        cg.RawExpression(
            f"ZBOSS_DECLARE_DEVICE_CTX_EP_VA(zb_device_ctx, &{', &'.join(CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER])})"
        )
    )
    cg.add(cg.RawExpression("ZB_AF_REGISTER_DEVICE_CTX(&zb_device_ctx)"))


async def zephyr_setup_binary_sensor(entity: cg.MockObj, config: ConfigType) -> None:
    CORE.add_job(_add_binary_sensor, entity, config)


async def zephyr_setup_sensor(entity: cg.MockObj, config: ConfigType) -> None:
    CORE.add_job(_add_sensor, entity, config)


async def zephyr_setup_switch(entity: cg.MockObj, config: ConfigType) -> None:
    CORE.add_job(_add_switch, entity, config)


async def zephyr_setup_number(
    entity: cg.MockObj,
    config: ConfigType,
    min_value: float,
    max_value: float,
    step: float,
) -> None:
    CORE.add_job(_add_number, entity, config, min_value, max_value, step)


def get_slot_index() -> int:
    """Find the next available endpoint slot."""
    slot = next(
        (i for i, v in enumerate(CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER]) if v == ""), None
    )
    if slot is None:
        raise cv.Invalid(
            f"No available Zigbee endpoint slots ({len(CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER])} in use)"
        )
    return slot


def _declare_io_attrs(
    prefix: str,
    attrs_type,
    zcl_macro: str,
    config: ConfigType,
    extra_field_values: dict[str, int] | None = None,
) -> tuple[cg.MockObj, str]:
    """Declare the attribute struct and attribute list of an Analog/Binary Input or Output cluster."""
    attrs = zigbee_new_variable(f"{prefix}_attrs", attrs_type)

    attr_args = [
        zigbee_assign(attrs.out_of_service, 0),
        zigbee_assign(attrs.present_value, 0),
        zigbee_assign(attrs.status_flags, 0),
    ]
    # Add extra field assignments (e.g., engineering_units for sensors)
    if extra_field_values:
        for field_name, value in extra_field_values.items():
            attr_args.append(zigbee_assign(getattr(attrs, field_name), value))
    attr_args.append(zigbee_set_string(attrs.description, config[CONF_NAME]))

    return attrs, zigbee_new_attr_list(f"{prefix}_attrib_list", zcl_macro, *attr_args)


async def _add_zigbee_ep(
    entity: cg.MockObj,
    config: ConfigType,
    component_key,
    attrs_type,
    zcl_macro: str,
    cluster_id: str,
    app_device_id: str,
    extra_field_values: dict[str, int] | None = None,
) -> None:
    slot_index = get_slot_index()

    prefix = f"zigbee_ep{slot_index + 1}"
    cluster_list_name = f"{prefix}_cluster_list"
    ep_name = f"{prefix}_ep"

    attrs, attr_list = _declare_io_attrs(
        prefix, attrs_type, zcl_macro, config, extra_field_values
    )

    # Create cluster list and register endpoint
    cluster_list_name, clusters = zigbee_new_cluster_list(
        cluster_list_name,
        [ZigbeeClusterDesc(cluster_id, attr_list)],
    )
    zigbee_register_ep(
        ep_name, cluster_list_name, 2, clusters, slot_index, app_device_id
    )

    # Create ESPHome component
    var = cg.new_Pvariable(config[component_key], entity)
    await cg.register_component(var, {})

    cg.add(var.set_endpoint(slot_index + 1))
    cg.add(var.set_cluster_attributes(attrs))

    hub = await cg.get_variable(config[CONF_ZIGBEE_ID])
    cg.add(var.set_parent(hub))


async def _add_binary_sensor(entity: cg.MockObj, config: ConfigType) -> None:
    if entry := _plan_entry(config):
        await _add_planned_entity(entity, config, *entry)
        return
    await _add_zigbee_ep(
        entity,
        config,
        CONF_ZIGBEE_BINARY_SENSOR,
        BinaryAttrs,
        "ESPHOME_ZB_ZCL_DECLARE_BINARY_INPUT_ATTRIB_LIST",
        ZB_ZCL_CLUSTER_ID_BINARY_INPUT,
        "ZB_HA_SIMPLE_SENSOR_DEVICE_ID",
    )


async def _add_sensor(entity: cg.MockObj, config: ConfigType) -> None:
    if entry := _plan_entry(config):
        await _add_planned_entity(entity, config, *entry)
        return
    # Get BACnet engineering unit from unit_of_measurement
    unit = config.get(CONF_UNIT_OF_MEASUREMENT, "")
    bacnet_unit = BACNET_UNITS.get(unit, BACNET_UNIT_NO_UNITS)

    await _add_zigbee_ep(
        entity,
        config,
        CONF_ZIGBEE_SENSOR,
        AnalogAttrs,
        "ESPHOME_ZB_ZCL_DECLARE_ANALOG_INPUT_ATTRIB_LIST",
        ZB_ZCL_CLUSTER_ID_ANALOG_INPUT,
        "ZB_HA_CUSTOM_ATTR_DEVICE_ID",
        extra_field_values={"engineering_units": bacnet_unit},
    )


async def _add_switch(entity: cg.MockObj, config: ConfigType) -> None:
    await _add_zigbee_ep(
        entity,
        config,
        CONF_ZIGBEE_SWITCH,
        BinaryAttrs,
        "ESPHOME_ZB_ZCL_DECLARE_BINARY_OUTPUT_ATTRIB_LIST",
        ZB_ZCL_CLUSTER_ID_BINARY_OUTPUT,
        "ZB_HA_CUSTOM_ATTR_DEVICE_ID",
    )


async def _add_number(
    entity: cg.MockObj,
    config: ConfigType,
    min_value: float,
    max_value: float,
    step: float,
) -> None:
    # Get BACnet engineering unit from unit_of_measurement
    unit = config.get(CONF_UNIT_OF_MEASUREMENT, "")
    bacnet_unit = BACNET_UNITS.get(unit, BACNET_UNIT_NO_UNITS)

    await _add_zigbee_ep(
        entity,
        config,
        CONF_ZIGBEE_NUMBER,
        AnalogAttrsOutput,
        "ESPHOME_ZB_ZCL_DECLARE_ANALOG_OUTPUT_ATTRIB_LIST",
        ZB_ZCL_CLUSTER_ID_ANALOG_OUTPUT,
        "ZB_HA_CUSTOM_ATTR_DEVICE_ID",
        extra_field_values={
            "max_present_value": max_value,
            "min_present_value": min_value,
            "resolution": step,
            "engineering_units": bacnet_unit,
        },
    )


# ---------------------------------------------------------------------------
# standard_clusters: sensors sharing endpoints through their standard ZCL clusters
#
# By default every entity gets an endpoint of its own carrying one generic Analog
# Input cluster, and ZBOSS - shipped as a prebuilt library compiled with
# CONFIG_ZB_MAX_EP_NUMBER 8 - caps a device at 8 endpoints. With
# `standard_clusters: true`, sensors whose device_class has a standard ZCL
# measurement cluster use it instead, and clusters of *different* types are packed
# onto the same endpoint (a cluster type can appear only once per endpoint).
# Sensors without such a class keep an Analog/Binary Input cluster, packed the same
# way.
# ---------------------------------------------------------------------------

# Entity clusters (Basic and Identify come on top) allowed on one endpoint. The
# native firmware this was modelled on carries 5 on its main endpoint.
MAX_CLUSTERS_PER_EP = 5


@dataclass(frozen=True)
class _Kind:
    # C macro name, kept as text so it reaches ZB_ZCL_CLUSTER_DESC unexpanded
    # (passing it through another macro level pre-expands it and breaks the
    # `cluster_id##_SERVER_ROLE_INIT` token pasting inside).
    cluster_id: str
    report_attrs: int


_KINDS = {
    "temperature": _Kind("ZB_ZCL_CLUSTER_ID_TEMP_MEASUREMENT", 1),
    "humidity": _Kind("ZB_ZCL_CLUSTER_ID_REL_HUMIDITY_MEASUREMENT", 1),
    "illuminance": _Kind("ZB_ZCL_CLUSTER_ID_ILLUMINANCE_MEASUREMENT", 1),
    "co2": _Kind("ZB_ZCL_CLUSTER_ID_CARBON_DIOXIDE_MEASUREMENT", 1),
    "pm25": _Kind("ZB_ZCL_CLUSTER_ID_PM2_5_MEASUREMENT", 1),
    "occupancy": _Kind("ZB_ZCL_CLUSTER_ID_OCCUPANCY_SENSING", 1),
    "analog_input": _Kind(ZB_ZCL_CLUSTER_ID_ANALOG_INPUT, 2),
    "binary_input": _Kind(ZB_ZCL_CLUSTER_ID_BINARY_INPUT, 2),
}

_SENSOR_KINDS = {
    DEVICE_CLASS_TEMPERATURE: "temperature",
    DEVICE_CLASS_HUMIDITY: "humidity",
    DEVICE_CLASS_ILLUMINANCE: "illuminance",
    DEVICE_CLASS_CARBON_DIOXIDE: "co2",
    DEVICE_CLASS_PM25: "pm25",
}
_OCCUPANCY_CLASSES = (DEVICE_CLASS_OCCUPANCY, DEVICE_CLASS_PRESENCE)


def _kind_for(domain: str, device_class: str | None) -> str:
    if domain == "binary_sensor":
        return "occupancy" if device_class in _OCCUPANCY_CLASSES else "binary_input"
    return _SENSOR_KINDS.get(device_class, "analog_input")


def _ep_name(slot: int) -> str:
    return f"zigbee_ep{slot + 1}_ep"


def record_std_entity(domain: str, config: ConfigType) -> None:
    """Called for every sensor / binary sensor exposed over Zigbee, at validation."""
    entities: list = CORE.data.setdefault(KEY_ZIGBEE, {}).setdefault(
        KEY_STD_ENTITIES, []
    )
    # The ID object, not its name: auto-generated IDs have none yet at validation
    # time (str() of all of them would collide), it is filled in by the ID pass.
    entity_id = config[CONF_ID]
    if all(e[0] is not entity_id for e in entities):
        entities.append((entity_id, domain, config.get(CONF_DEVICE_CLASS)))


def plan_zephyr_endpoints(config: ConfigType) -> None:
    """First-fit packing of the recorded entities onto endpoints, by cluster type."""
    if not config.get(CONF_STANDARD_CLUSTERS) or KEY_ZIGBEE not in CORE.data:
        return
    data = CORE.data[KEY_ZIGBEE]
    slots: list[str] = data[KEY_EP_NUMBER]
    entities = data.get(KEY_STD_ENTITIES, [])

    endpoints: list[list[str]] = []
    by_id: dict[str, tuple[int, str]] = {}
    for entity_id, domain, device_class in entities:
        kind = _kind_for(domain, device_class)
        slot = next(
            (
                i
                for i, kinds in enumerate(endpoints)
                if kind not in kinds and len(kinds) < MAX_CLUSTERS_PER_EP
            ),
            None,
        )
        if slot is None:
            endpoints.append([])
            slot = len(endpoints) - 1
        endpoints[slot].append(kind)
        by_id[str(entity_id)] = (slot, kind)

    # consume_endpoint() reserved one slot per entity of any type; sensors and
    # binary sensors now share endpoints, switches and numbers keep their own.
    other = len(slots) - len(entities)
    slots[:] = [_ep_name(i) for i in range(len(endpoints))] + [""] * other
    data[KEY_STD_PLAN] = {"by_id": by_id, "endpoints": endpoints}


def _plan_entry(config: ConfigType) -> tuple[int, str] | None:
    plan = CORE.data.get(KEY_ZIGBEE, {}).get(KEY_STD_PLAN)
    if not plan:
        return None
    return plan["by_id"].get(str(config[CONF_ID]))


def _declare_std_attrs(prefix: str, kind: str) -> str:
    """Declare attribute storage and list for a standard cluster; returns the list name."""
    attrs = f"{prefix}_attrs"
    name = f"{prefix}_attrib_list"
    nan = '__builtin_nanf("")'
    if kind == "temperature":
        # int16, 0.01 degC; 0x8000 = invalid. Range of the SHT4x.
        CORE.add_global(
            cg.RawExpression(
                f"zb_zcl_temp_measurement_attrs_t {attrs} = {{(zb_int16_t) 0x8000, -4000, 12500, 0}}"
            )
        )
        return zigbee_new_attr_list(
            name,
            "ZB_ZCL_DECLARE_TEMP_MEASUREMENT_ATTRIB_LIST",
            f"&{attrs}.measure_value",
            f"&{attrs}.min_measure_value",
            f"&{attrs}.max_measure_value",
            f"&{attrs}.tolerance",
        )
    if kind == "humidity":
        CORE.add_global(
            cg.RawExpression(
                f"esphome::zigbee::HumidityAttrs {attrs} = {{0xFFFF, 0, 10000}}"
            )
        )
        return zigbee_new_attr_list(
            name,
            "ZB_ZCL_DECLARE_REL_HUMIDITY_MEASUREMENT_ATTRIB_LIST",
            f"&{attrs}.rel_humidity",
            f"&{attrs}.min_val",
            f"&{attrs}.max_val",
        )
    if kind == "illuminance":
        CORE.add_global(
            cg.RawExpression(f"esphome::zigbee::IlluminanceAttrs {attrs} = {{0xFFFF}}")
        )
        return zigbee_new_attr_list(
            name,
            "ZB_ZCL_DECLARE_ILLUMINANCE_MEASUREMENT_ATTRIB_LIST",
            f"&{attrs}.log_lux",
            "NULL",
            "NULL",
        )
    if kind == "co2":
        # single, molar fraction (0.0-1.0), NaN = no value yet
        CORE.add_global(
            cg.RawExpression(
                f"zb_zcl_carbon_dioxide_measurement_attrs_t {attrs} = {{{nan}, 0.0f, 1.0f, 0.0f}}"
            )
        )
        return zigbee_new_attr_list(
            name, "ZB_ZCL_DECLARE_CARBON_DIOXIDE_MEASUREMENT_ATTR_LIST", attrs
        )
    if kind == "pm25":
        CORE.add_global(
            cg.RawExpression(
                f"zb_zcl_pm2_5_measurement_attrs_t {attrs} = {{{nan}, 0.0f, 1000.0f, 0.0f}}"
            )
        )
        return zigbee_new_attr_list(
            name, "ZB_ZCL_DECLARE_PM2_5_MEASUREMENT_ATTR_LIST", attrs
        )
    if kind == "occupancy":
        # ZCL has no radar sensor type; PIR is the closest of the standard ones
        CORE.add_global(
            cg.RawExpression(
                f"esphome::zigbee::OccupancyAttrs {attrs} = {{0, "
                "ZB_ZCL_OCCUPANCY_SENSING_OCCUPANCY_SENSOR_TYPE_PIR, "
                "ZB_ZCL_OCCUPANCY_SENSING_OCCUPANCY_SENSOR_TYPE_BITMAP_PIR}"
            )
        )
        return zigbee_new_attr_list(
            name,
            "ZB_ZCL_DECLARE_OCCUPANCY_SENSING_ATTRIB_LIST",
            f"&{attrs}.occupancy",
            f"&{attrs}.sensor_type",
            f"&{attrs}.sensor_type_bitmap",
        )
    raise NotImplementedError(kind)


async def _add_planned_entity(
    entity: cg.MockObj, config: ConfigType, slot: int, kind: str
) -> None:
    prefix = f"zigbee_ep{slot + 1}_{kind}"
    hub = await cg.get_variable(config[CONF_ZIGBEE_ID])

    if kind == "analog_input":
        unit = config.get(CONF_UNIT_OF_MEASUREMENT, "")
        attrs, attr_list = _declare_io_attrs(
            prefix,
            AnalogAttrs,
            "ESPHOME_ZB_ZCL_DECLARE_ANALOG_INPUT_ATTRIB_LIST",
            config,
            {"engineering_units": BACNET_UNITS.get(unit, BACNET_UNIT_NO_UNITS)},
        )
        var = cg.new_Pvariable(config[CONF_ZIGBEE_SENSOR], entity)
        await cg.register_component(var, {})
        cg.add(var.set_cluster_attributes(attrs))
    elif kind == "binary_input":
        attrs, attr_list = _declare_io_attrs(
            prefix,
            BinaryAttrs,
            "ESPHOME_ZB_ZCL_DECLARE_BINARY_INPUT_ATTRIB_LIST",
            config,
        )
        var = cg.new_Pvariable(config[CONF_ZIGBEE_BINARY_SENSOR], entity)
        await cg.register_component(var, {})
        cg.add(var.set_cluster_attributes(attrs))
    else:
        attr_list = _declare_std_attrs(prefix, kind)
        if kind == "occupancy":
            var_id = ID(f"{prefix}_zb", is_declaration=True, type=ZigbeeOccupancySensor)
            var = cg.new_Pvariable(var_id, entity)
        else:
            var_id = ID(f"{prefix}_zb", is_declaration=True, type=ZigbeeStandardSensor)
            var = cg.new_Pvariable(var_id, entity, getattr(StandardKind, kind.upper()))
        # These entities are created here, not declared in the YAML schema, so
        # the config ID pass never saw them: register_component() only accepts
        # IDs collected there.
        CORE.component_ids.add(var_id.id)
        await cg.register_component(var, {})

    cg.add(var.set_endpoint(slot + 1))
    cg.add(var.set_parent(hub))
    specs: dict = CORE.data[KEY_ZIGBEE].setdefault(KEY_EP_SPECS, {})
    specs.setdefault(slot, []).append(
        ZigbeeClusterDesc(_KINDS[kind].cluster_id, attr_list)
    )


def _emit_planned_endpoints() -> None:
    """Declare the packed endpoints once every entity has registered its cluster."""
    plan = CORE.data.get(KEY_ZIGBEE, {}).get(KEY_STD_PLAN)
    if not plan:
        return
    specs: dict = CORE.data[KEY_ZIGBEE].get(KEY_EP_SPECS, {})
    for slot, kinds in enumerate(plan["endpoints"]):
        cluster_list_name, clusters = zigbee_new_cluster_list(
            f"zigbee_ep{slot + 1}_cluster_list", specs.get(slot, [])
        )
        zigbee_register_ep(
            _ep_name(slot),
            cluster_list_name,
            sum(_KINDS[k].report_attrs for k in kinds),
            clusters,
            slot,
            "ZB_HA_CUSTOM_ATTR_DEVICE_ID",
        )
