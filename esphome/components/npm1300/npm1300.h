#pragma once

#ifdef USE_ZEPHYR

#include "esphome/core/automation.h"
#include "esphome/core/component.h"
#include "esphome/core/defines.h"

#ifdef USE_SENSOR
#include "esphome/components/sensor/sensor.h"
#endif
#ifdef USE_BINARY_SENSOR
#include "esphome/components/binary_sensor/binary_sensor.h"
#endif
#ifdef USE_TEXT_SENSOR
#include "esphome/components/text_sensor/text_sensor.h"
#endif

#include <zephyr/device.h>

namespace esphome::npm1300 {

/// nPM1300 PMIC through Zephyr's drivers: the charger is a Zephyr sensor device, the PMIC
/// itself an MFD device. Each update() samples the charger (VBAT, IBAT, NTC, die temperature,
/// charge status), publishes the configured entities and, if enabled, applies the USB current
/// limit advertised on CC1/CC2.
class Npm1300Component : public PollingComponent {
 public:
  void setup() override;
  void update() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }

  void set_charger(const device *dev) { this->charger_ = dev; }
  void set_mfd(const device *dev) { this->mfd_ = dev; }
  void set_usb_auto_current_limit(bool enable) { this->usb_auto_current_limit_ = enable; }

  /// Enter ship mode (TASKENTERSHIPMODE). The PMIC cuts every output, the nRF included; only
  /// SHPHLD (SW3) held low or a USB plug-in wakes it up.
  bool enter_ship_mode();
  /// Force BUCK2 into PWM mode (true) or back to automatic PWM/hysteretic mode (false).
  bool set_buck2_pwm(bool pwm);

#ifdef USE_SENSOR
  SUB_SENSOR(battery_voltage)
  SUB_SENSOR(battery_current)
  SUB_SENSOR(battery_temperature)
  SUB_SENSOR(die_temperature)
  SUB_SENSOR(usb_current_limit)
#endif
#ifdef USE_BINARY_SENSOR
  SUB_BINARY_SENSOR(usb_connected)
  SUB_BINARY_SENSOR(charging)
  SUB_BINARY_SENSOR(charge_complete)
  SUB_BINARY_SENSOR(charger_error)
#endif
#ifdef USE_TEXT_SENSOR
  SUB_TEXT_SENSOR(charger_status)
  SUB_TEXT_SENSOR(charger_error)
#endif

 protected:
  void update_usb_current_limit_(bool usb_present);

  const device *charger_{nullptr};
  const device *mfd_{nullptr};
  bool usb_auto_current_limit_{true};
  int32_t applied_usb_limit_ua_{-1};
  bool usb_present_{false};
};

template<typename... Ts> class EnterShipModeAction final : public Action<Ts...> {
 public:
  explicit EnterShipModeAction(Npm1300Component *parent) : parent_(parent) {}
  void play(const Ts &...x) override { this->parent_->enter_ship_mode(); }

 protected:
  Npm1300Component *parent_;
};

template<typename... Ts> class SetBuck2PwmAction final : public Action<Ts...> {
 public:
  explicit SetBuck2PwmAction(Npm1300Component *parent) : parent_(parent) {}
  TEMPLATABLE_VALUE(bool, pwm)
  void play(const Ts &...x) override { this->parent_->set_buck2_pwm(this->pwm_.value(x...)); }

 protected:
  Npm1300Component *parent_;
};

}  // namespace esphome::npm1300

#endif  // USE_ZEPHYR
