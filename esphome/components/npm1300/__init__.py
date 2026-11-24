"""Nordic nPM1300 PMIC (charger, load switches, LEDs, ship mode) on Zephyr.

The PMIC is not driven by ESPHome's I2C code: Zephyr already has drivers for it
(mfd, charger as a sensor device, regulators, LEDs). This component writes the
devicetree node under the I2C bus that the `i2c:` component enables, turns the
drivers on in Kconfig, and reads the charger device from C++.

Not hardware-validated: written for the MultiSensors Battery board (nPM1300 U4,
I2C 0x6B on i2c22, GPIO0 -> nRF P1.08), compiled only. Every charger value below
must be checked against the actual cell before charging one.

BUCK1/BUCK2 are deliberately NOT declared in the devicetree: on that board BUCK2
supplies the nRF itself (3.3 V set by the VSET2 resistor at power-up), and a
regulator node would let the Zephyr driver reprogram it at boot. The forced-PWM
action below writes the two BUCK2 mode registers directly instead.
"""

from esphome import automation, pins
import esphome.codegen as cg
from esphome.components.zephyr import (
    zephyr_add_overlay_builder,
    zephyr_add_prj_conf,
    zephyr_data,
)
from esphome.components.zephyr.const import KEY_BOARD
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_NUMBER
from esphome.core import CORE

CODEOWNERS = ["@ludodefgh"]
DEPENDENCIES = ["zephyr", "i2c"]

CONF_NPM1300_ID = "npm1300_id"
CONF_INTERRUPT_PIN = "interrupt_pin"
CONF_PMIC_INTERRUPT_GPIO = "pmic_interrupt_gpio"
CONF_CHARGER = "charger"
CONF_TERMINATION_VOLTAGE = "termination_voltage"
CONF_CHARGE_CURRENT = "charge_current"
CONF_DISCHARGE_LIMIT = "discharge_limit"
CONF_TERMINATION_CURRENT = "termination_current"
CONF_THERMISTOR = "thermistor"
CONF_THERMISTOR_BETA = "thermistor_beta"
CONF_ENABLE_CHARGING = "enable_charging"
CONF_USB_STARTUP_CURRENT_LIMIT = "usb_startup_current_limit"
CONF_USB_AUTO_CURRENT_LIMIT = "usb_auto_current_limit"
CONF_LEDS = "leds"
CONF_LED0 = "led0"
CONF_LED1 = "led1"
CONF_LED2 = "led2"
CONF_SHIP_WAKE_TIME = "ship_wake_time"

# Same restriction as zephyr_i2s_mic: the I2C node label is the one the `i2c:`
# component enables on this board (esphome/components/i2c/__init__.py).
_I2C_NODE = {"raytac_an54lq_db_15/nrf54l15/cpuapp": "i2c22"}
_PMIC_ADDRESS = 0x6B  # fixed by the part (PS v1.3, TWI)

npm1300_ns = cg.esphome_ns.namespace("npm1300")
Npm1300Component = npm1300_ns.class_("Npm1300Component", cg.PollingComponent)
EnterShipModeAction = npm1300_ns.class_("EnterShipModeAction", automation.Action)
SetBuck2PwmAction = npm1300_ns.class_("SetBuck2PwmAction", automation.Action)

THERMISTORS = {"none": 0, "10k": 10000, "47k": 47000, "100k": 100000}
LED_MODES = ["error", "charging", "host"]
SHIP_WAKE_TIMES_MS = [16, 32, 64, 96, 304, 608, 1008, 3008]


def _termination_voltage(value):
    """3.50-3.65 V or 4.00-4.45 V, 50 mV steps (Zephyr npm1300-charger binding)."""
    value = cv.voltage(value)
    mv = round(value * 1000)
    if not (3500 <= mv <= 3650 or 4000 <= mv <= 4450) or mv % 50:
        raise cv.Invalid(
            "nPM1300 termination voltage must be 3.50-3.65 V or 4.00-4.45 V in 50 mV steps"
        )
    return mv * 1000


def _charge_current(value):
    """32-800 mA, 2 mA steps."""
    value = cv.current(value)
    ma = round(value * 1000)
    if not 32 <= ma <= 800 or ma % 2:
        raise cv.Invalid("nPM1300 charge current must be 32-800 mA in 2 mA steps")
    return ma * 1000


def _usb_limit(value):
    """100-1500 mA, 100 mA steps."""
    value = cv.current(value)
    ma = round(value * 1000)
    if not 100 <= ma <= 1500 or ma % 100:
        raise cv.Invalid("nPM1300 VBUS current limit must be 100-1500 mA in 100 mA steps")
    return ma * 1000


def _discharge_limit(value):
    value = cv.current(value)
    ma = round(value * 1000)
    if ma not in (200, 1000):
        raise cv.Invalid("nPM1300 discharge limit is 200 mA or 1000 mA")
    return ma * 1000


def _ship_wake_time(value):
    value = cv.positive_time_period_milliseconds(value)
    if value.total_milliseconds not in SHIP_WAKE_TIMES_MS:
        raise cv.Invalid(f"ship_wake_time must be one of {SHIP_WAKE_TIMES_MS} ms")
    return value


CHARGER_SCHEMA = cv.Schema(
    {
        # Defaults are placeholders for a 1-cell Li-ion/LiPo: they MUST be
        # checked against the real cell's datasheet before charging it.
        cv.Optional(CONF_TERMINATION_VOLTAGE, default="4.2V"): _termination_voltage,
        cv.Optional(CONF_CHARGE_CURRENT, default="100mA"): _charge_current,
        cv.Optional(CONF_DISCHARGE_LIMIT, default="1000mA"): _discharge_limit,
        cv.Optional(CONF_TERMINATION_CURRENT, default="10%"): cv.All(
            cv.percentage_int, cv.int_, cv.one_of(10, 20, int=True)
        ),
        # "none": NTC pin tied to GND, temperature monitoring disabled
        # (PS v1.3 6.2: must also be disabled in BCHGDISABLESET, which the
        # Zephyr driver does when thermistor-ohms = 0).
        cv.Optional(CONF_THERMISTOR, default="none"): cv.one_of(*THERMISTORS, lower=True),
        cv.Optional(CONF_THERMISTOR_BETA, default=3380): cv.int_range(min=1),
        cv.Optional(CONF_ENABLE_CHARGING, default=True): cv.boolean,
        # Applied by the PMIC at every USB plug-in (VBUSINILIMSTARTUP).
        cv.Optional(CONF_USB_STARTUP_CURRENT_LIMIT, default="500mA"): _usb_limit,
        # Raise the limit to 1500 mA when CC1/CC2 advertise 1.5 A or 3 A,
        # else keep 500 mA (USB default). Re-checked at every update.
        cv.Optional(CONF_USB_AUTO_CURRENT_LIMIT, default=True): cv.boolean,
    }
)

LEDS_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_LED0, default="charging"): cv.one_of(*LED_MODES, lower=True),
        cv.Optional(CONF_LED1, default="host"): cv.one_of(*LED_MODES, lower=True),
        cv.Optional(CONF_LED2, default="host"): cv.one_of(*LED_MODES, lower=True),
    }
)


def _validate(config):
    board = zephyr_data()[KEY_BOARD]
    if board not in _I2C_NODE:
        raise cv.Invalid(
            f"npm1300 is only implemented for {', '.join(_I2C_NODE)} so far (board is '{board}')"
        )
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Npm1300Component),
            # nRF pin wired to one of the PMIC's GPIOs (MultiSensors Battery: P1.08).
            cv.Optional(CONF_INTERRUPT_PIN): pins.internal_gpio_input_pin_schema,
            cv.Optional(CONF_PMIC_INTERRUPT_GPIO, default=0): cv.int_range(min=0, max=4),
            cv.Optional(CONF_CHARGER, default={}): CHARGER_SCHEMA,
            cv.Optional(CONF_LEDS, default={}): LEDS_SCHEMA,
            cv.Optional(CONF_SHIP_WAKE_TIME, default="96ms"): _ship_wake_time,
        }
    ).extend(cv.polling_component_schema("60s")),
    cv.only_on_nrf52,
    _validate,
)


def _regulator_nodes() -> str:
    """LDO1/LDO2 children requested by `switch: platform: npm1300`."""
    channels = CORE.data.get("npm1300", {}).get("load_switches", set())
    nodes = []
    for ch in sorted(channels):
        nodes.append(
            f"""
                npm1300_ldo{ch}: LDO{ch} {{
                    regulator-initial-mode = <NPM13XX_LDSW_MODE_LDSW>;
                }};"""
        )
    if not nodes:
        return ""
    body = "".join(nodes)
    return f"""
            npm1300_regulators: regulators {{
                compatible = "nordic,npm1300-regulator";{body}
            }};"""


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    charger = config[CONF_CHARGER]
    leds = config[CONF_LEDS]
    i2c_node = _I2C_NODE[zephyr_data()[KEY_BOARD]]

    zephyr_add_prj_conf("I2C", True)
    zephyr_add_prj_conf("MFD", True)
    zephyr_add_prj_conf("SENSOR", True)
    zephyr_add_prj_conf("LED", True)
    zephyr_add_prj_conf("GPIO", True)

    interrupt = ""
    if pin := config.get(CONF_INTERRUPT_PIN):
        n = pin[CONF_NUMBER]
        interrupt = f"""
            host-int-gpios = <&gpio{n // 32} {n % 32} 0>;
            pmic-int-pin = <{config[CONF_PMIC_INTERRUPT_GPIO]}>;"""

    charging_enable = "\n                charging-enable;" if charger[CONF_ENABLE_CHARGING] else ""

    # The regulator children depend on the switch platforms, which run after
    # this to_code(): build that part of the overlay at the end.
    regulators_marker = "/*NPM1300_REGULATORS*/"
    overlay = f"""
        #include <dt-bindings/regulator/npm13xx.h>

        &{i2c_node} {{
            npm1300_pmic: pmic@{_PMIC_ADDRESS:x} {{
                compatible = "nordic,npm1300";
                reg = <{_PMIC_ADDRESS:#x}>;{interrupt}
                ship-to-active-time-ms = <{int(config[CONF_SHIP_WAKE_TIME].total_milliseconds)}>;

                npm1300_charger: charger {{
                    compatible = "nordic,npm1300-charger";
                    term-microvolt = <{charger[CONF_TERMINATION_VOLTAGE]}>;
                    current-microamp = <{charger[CONF_CHARGE_CURRENT]}>;
                    dischg-limit-microamp = <{charger[CONF_DISCHARGE_LIMIT]}>;
                    term-current-percent = <{charger[CONF_TERMINATION_CURRENT]}>;
                    vbus-limit-microamp = <{charger[CONF_USB_STARTUP_CURRENT_LIMIT]}>;
                    thermistor-ohms = <{THERMISTORS[charger[CONF_THERMISTOR]]}>;
                    thermistor-beta = <{charger[CONF_THERMISTOR_BETA]}>;{charging_enable}
                }};

                npm1300_leds: leds {{
                    compatible = "nordic,npm1300-led";
                    nordic,led0-mode = "{leds[CONF_LED0]}";
                    nordic,led1-mode = "{leds[CONF_LED1]}";
                    nordic,led2-mode = "{leds[CONF_LED2]}";
                }};
                {regulators_marker}
            }};
        }};
        """

    def _build() -> str:
        regs = _regulator_nodes()
        if regs:
            zephyr_add_prj_conf("REGULATOR", True)
        return overlay.replace(regulators_marker, regs)

    zephyr_add_overlay_builder(_build)

    cg.add(var.set_charger(cg.RawExpression("DEVICE_DT_GET(DT_NODELABEL(npm1300_charger))")))
    cg.add(var.set_mfd(cg.RawExpression("DEVICE_DT_GET(DT_NODELABEL(npm1300_pmic))")))
    cg.add(var.set_usb_auto_current_limit(charger[CONF_USB_AUTO_CURRENT_LIMIT]))
    cg.add_define("USE_NPM1300")


NPM1300_ACTION_SCHEMA = automation.maybe_simple_id(
    {cv.GenerateID(): cv.use_id(Npm1300Component)}
)


@automation.register_action(
    "npm1300.enter_ship_mode", EnterShipModeAction, NPM1300_ACTION_SCHEMA, synchronous=True
)
async def enter_ship_mode_to_code(config, action_id, template_arg, args):
    parent = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(action_id, template_arg, parent)


CONF_PWM = "pwm"


@automation.register_action(
    "npm1300.set_buck2_pwm",
    SetBuck2PwmAction,
    cv.Schema(
        {
            cv.GenerateID(): cv.use_id(Npm1300Component),
            cv.Required(CONF_PWM): cv.templatable(cv.boolean),
        }
    ),
    synchronous=True,
)
async def set_buck2_pwm_to_code(config, action_id, template_arg, args):
    parent = await cg.get_variable(config[CONF_ID])
    var = cg.new_Pvariable(action_id, template_arg, parent)
    template_ = await cg.templatable(config[CONF_PWM], args, bool)
    cg.add(var.set_pwm(template_))
    return var
