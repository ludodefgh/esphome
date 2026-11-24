#ifdef USE_ZEPHYR

#include "npm1300_switch.h"
#include "esphome/core/log.h"

#include <zephyr/drivers/regulator.h>

namespace esphome::npm1300 {

static const char *const TAG = "npm1300.switch";

void Npm1300LoadSwitch::setup() {
  if (this->regulator_ == nullptr || !device_is_ready(this->regulator_)) {
    ESP_LOGE(TAG, "Load switch regulator not ready");
    this->mark_failed();
    return;
  }
  bool initial = this->get_initial_state_with_restore_mode().value_or(false);
  this->write_state(initial);
}

void Npm1300LoadSwitch::write_state(bool state) {
  if (this->is_failed())
    return;
  int ret = 0;
  if (state && !this->enabled_) {
    ret = regulator_enable(this->regulator_);
    if (ret == 0)
      this->enabled_ = true;
  } else if (!state && this->enabled_) {
    ret = regulator_disable(this->regulator_);
    if (ret == 0)
      this->enabled_ = false;
  }
  if (ret != 0) {
    ESP_LOGW(TAG, "Load switch %s failed (%d)", state ? "on" : "off", ret);
    return;
  }
  this->publish_state(state);
}

void Npm1300LoadSwitch::dump_config() { LOG_SWITCH("", "nPM1300 load switch", this); }

}  // namespace esphome::npm1300

#endif  // USE_ZEPHYR
