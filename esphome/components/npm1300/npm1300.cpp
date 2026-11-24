#ifdef USE_ZEPHYR

#include "npm1300.h"
#include "esphome/core/log.h"

#include <zephyr/drivers/mfd/npm13xx.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/sensor/npm13xx_charger.h>

namespace esphome::npm1300 {

static const char *const TAG = "npm1300";

// Register map, nPM1300 PS v1.3 (only what the Zephyr drivers do not expose).
static constexpr uint8_t BUCK_BASE = 0x04;
static constexpr uint8_t BUCK2_PWM_SET = 0x06;  // TASKBUCK2PWMSET
static constexpr uint8_t BUCK2_PWM_CLR = 0x07;  // TASKBUCK2PWMCLR
static constexpr uint8_t SHIP_BASE = 0x0B;
static constexpr uint8_t SHIP_ENTER_SHIP_MODE = 0x02;  // TASKENTERSHIPMODE

// BCHGCHARGESTATUS (0x34) bits.
static constexpr uint8_t CHG_STATUS_BATTERY_DETECTED = 1 << 0;
static constexpr uint8_t CHG_STATUS_COMPLETED = 1 << 1;
static constexpr uint8_t CHG_STATUS_TRICKLE = 1 << 2;
static constexpr uint8_t CHG_STATUS_CONSTANT_CURRENT = 1 << 3;
static constexpr uint8_t CHG_STATUS_CONSTANT_VOLTAGE = 1 << 4;
static constexpr uint8_t CHG_STATUS_DIE_TEMP_PAUSED = 1 << 6;
static constexpr uint8_t CHG_STATUS_CHARGING =
    CHG_STATUS_TRICKLE | CHG_STATUS_CONSTANT_CURRENT | CHG_STATUS_CONSTANT_VOLTAGE;

static const char *charger_status_text(uint8_t status, bool usb_present) {
  if (status & CHG_STATUS_DIE_TEMP_PAUSED)
    return "Paused (die temperature)";
  if (status & CHG_STATUS_TRICKLE)
    return "Trickle charge";
  if (status & CHG_STATUS_CONSTANT_CURRENT)
    return "Constant current";
  if (status & CHG_STATUS_CONSTANT_VOLTAGE)
    return "Constant voltage";
  if (status & CHG_STATUS_COMPLETED)
    return "Complete";
  if (!(status & CHG_STATUS_BATTERY_DETECTED))
    return "No battery";
  return usb_present ? "Not charging" : "On battery";
}

// BCHGERRREASON (0x36): latched, first set bit reported.
static const char *charger_error_text(uint8_t error) {
  if (error == 0)
    return "None";
  if (error & (1 << 0))
    return "NTC sensor error";
  if (error & (1 << 1))
    return "VBAT sensor error";
  if (error & (1 << 2))
    return "VBAT low";
  if (error & (1 << 3))
    return "Vtrickle error";
  if (error & (1 << 4))
    return "Measurement timeout";
  if (error & (1 << 5))
    return "Charge timer timeout";
  return "Trickle timer timeout";
}

void Npm1300Component::setup() {
  if (this->charger_ == nullptr || !device_is_ready(this->charger_) || this->mfd_ == nullptr ||
      !device_is_ready(this->mfd_)) {
    ESP_LOGE(TAG, "nPM1300 not ready (I2C wiring, address 0x6B, or driver init failed)");
    this->mark_failed();
    return;
  }
}

void Npm1300Component::update_usb_current_limit_(bool usb_present) {
  if (!usb_present) {
    // The PMIC falls back to VBUSINILIMSTARTUP by itself on removal.
    this->applied_usb_limit_ua_ = -1;
    return;
  }
  sensor_value detected{};
  // Driver: 0 = nothing on CC, 500 mA = default USB, 1500 mA = CC advertises 1.5 A or 3 A.
  if (sensor_attr_get(this->charger_, SENSOR_CHAN_CURRENT, SENSOR_ATTR_UPPER_THRESH, &detected) != 0)
    return;
  int32_t limit_ua = detected.val1 * 1000000 + detected.val2;
  if (limit_ua <= 0)
    limit_ua = 500000;  // VBUS present but no CC termination seen (legacy cable): USB default
  if (limit_ua == this->applied_usb_limit_ua_)
    return;
  sensor_value set{.val1 = limit_ua / 1000000, .val2 = limit_ua % 1000000};
  if (sensor_attr_set(this->charger_, SENSOR_CHAN_CURRENT, SENSOR_ATTR_CONFIGURATION, &set) == 0) {
    this->applied_usb_limit_ua_ = limit_ua;
    ESP_LOGI(TAG, "USB input current limit set to %" PRId32 " mA", limit_ua / 1000);
  } else {
    ESP_LOGW(TAG, "Could not set the USB input current limit");
  }
}

void Npm1300Component::update() {
  if (sensor_sample_fetch(this->charger_) != 0) {
    ESP_LOGW(TAG, "Charger sample fetch failed");
    this->status_set_warning();
    return;
  }
  this->status_clear_warning();

  sensor_value val{};
  uint8_t status = 0;
  uint8_t error = 0;
  if (sensor_channel_get(this->charger_, (sensor_channel) SENSOR_CHAN_NPM13XX_CHARGER_STATUS, &val) == 0)
    status = val.val1;
  if (sensor_channel_get(this->charger_, (sensor_channel) SENSOR_CHAN_NPM13XX_CHARGER_ERROR, &val) == 0)
    error = val.val1;

  bool usb_present = false;
  if (sensor_attr_get(this->charger_, (sensor_channel) SENSOR_CHAN_NPM13XX_CHARGER_VBUS_STATUS,
                      (sensor_attribute) SENSOR_ATTR_NPM13XX_CHARGER_VBUS_PRESENT, &val) == 0)
    usb_present = val.val1 != 0;
  this->usb_present_ = usb_present;

  if (this->usb_auto_current_limit_)
    this->update_usb_current_limit_(usb_present);

#ifdef USE_SENSOR
  if (this->battery_voltage_sensor_ != nullptr &&
      sensor_channel_get(this->charger_, SENSOR_CHAN_GAUGE_VOLTAGE, &val) == 0)
    this->battery_voltage_sensor_->publish_state(sensor_value_to_float(&val));
  // Driver sign convention (calc_current in npm13xx_charger.c): positive while charging, negative
  // while discharging. Full scale follows discharge_limit (1 A -> ~1 mA steps), so a sleeping
  // board's few uA are not measurable. Published as is, in A.
  if (this->battery_current_sensor_ != nullptr &&
      sensor_channel_get(this->charger_, SENSOR_CHAN_GAUGE_AVG_CURRENT, &val) == 0)
    this->battery_current_sensor_->publish_state(sensor_value_to_float(&val));
  // -ENOTSUP without a thermistor (thermistor: none): left unpublished.
  if (this->battery_temperature_sensor_ != nullptr &&
      sensor_channel_get(this->charger_, SENSOR_CHAN_GAUGE_TEMP, &val) == 0)
    this->battery_temperature_sensor_->publish_state(sensor_value_to_float(&val));
  if (this->die_temperature_sensor_ != nullptr && sensor_channel_get(this->charger_, SENSOR_CHAN_DIE_TEMP, &val) == 0)
    this->die_temperature_sensor_->publish_state(sensor_value_to_float(&val));
  if (this->usb_current_limit_sensor_ != nullptr)
    this->usb_current_limit_sensor_->publish_state(
        usb_present && this->applied_usb_limit_ua_ > 0 ? this->applied_usb_limit_ua_ / 1e6f : 0.0f);
#endif
#ifdef USE_BINARY_SENSOR
  if (this->usb_connected_binary_sensor_ != nullptr)
    this->usb_connected_binary_sensor_->publish_state(usb_present);
  if (this->charging_binary_sensor_ != nullptr)
    this->charging_binary_sensor_->publish_state((status & CHG_STATUS_CHARGING) != 0);
  if (this->charge_complete_binary_sensor_ != nullptr)
    this->charge_complete_binary_sensor_->publish_state((status & CHG_STATUS_COMPLETED) != 0);
  if (this->charger_error_binary_sensor_ != nullptr)
    this->charger_error_binary_sensor_->publish_state(error != 0);
#endif
#ifdef USE_TEXT_SENSOR
  if (this->charger_status_text_sensor_ != nullptr)
    this->charger_status_text_sensor_->publish_state(charger_status_text(status, usb_present));
  if (this->charger_error_text_sensor_ != nullptr)
    this->charger_error_text_sensor_->publish_state(charger_error_text(error));
#endif
}

bool Npm1300Component::enter_ship_mode() {
  ESP_LOGW(TAG, "Entering ship mode: everything powers off until SHPHLD or USB");
  return mfd_npm13xx_reg_write(this->mfd_, SHIP_BASE, SHIP_ENTER_SHIP_MODE, 1U) == 0;
}

bool Npm1300Component::set_buck2_pwm(bool pwm) {
  int ret = mfd_npm13xx_reg_write(this->mfd_, BUCK_BASE, pwm ? BUCK2_PWM_SET : BUCK2_PWM_CLR, 1U);
  if (ret != 0) {
    ESP_LOGW(TAG, "BUCK2 mode change failed (%d)", ret);
    return false;
  }
  ESP_LOGD(TAG, "BUCK2 %s", pwm ? "forced PWM" : "automatic mode");
  return true;
}

void Npm1300Component::dump_config() {
  ESP_LOGCONFIG(TAG,
                "nPM1300:\n"
                "  USB current limit from CC: %s",
                YESNO(this->usb_auto_current_limit_));
  LOG_UPDATE_INTERVAL(this);
  if (this->is_failed())
    ESP_LOGE(TAG, "  Not ready");
#ifdef USE_SENSOR
  LOG_SENSOR("  ", "Battery voltage", this->battery_voltage_sensor_);
  LOG_SENSOR("  ", "Battery current", this->battery_current_sensor_);
  LOG_SENSOR("  ", "Battery temperature", this->battery_temperature_sensor_);
  LOG_SENSOR("  ", "Die temperature", this->die_temperature_sensor_);
  LOG_SENSOR("  ", "USB current limit", this->usb_current_limit_sensor_);
#endif
#ifdef USE_BINARY_SENSOR
  LOG_BINARY_SENSOR("  ", "USB connected", this->usb_connected_binary_sensor_);
  LOG_BINARY_SENSOR("  ", "Charging", this->charging_binary_sensor_);
  LOG_BINARY_SENSOR("  ", "Charge complete", this->charge_complete_binary_sensor_);
  LOG_BINARY_SENSOR("  ", "Charger error", this->charger_error_binary_sensor_);
#endif
#ifdef USE_TEXT_SENSOR
  LOG_TEXT_SENSOR("  ", "Charger status", this->charger_status_text_sensor_);
  LOG_TEXT_SENSOR("  ", "Charger error", this->charger_error_text_sensor_);
#endif
}

}  // namespace esphome::npm1300

#endif  // USE_ZEPHYR
