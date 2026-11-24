#pragma once

#ifdef USE_ZEPHYR

#include "esphome/core/component.h"
#include "esphome/components/switch/switch.h"

#include <zephyr/device.h>

namespace esphome::npm1300 {

/// One nPM1300 LDO configured as a load switch, driven through Zephyr's regulator API.
class Npm1300LoadSwitch final : public switch_::Switch, public Component {
 public:
  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }

  void set_regulator(const device *dev) { this->regulator_ = dev; }

 protected:
  void write_state(bool state) override;

  const device *regulator_{nullptr};
  bool enabled_{false};  // our own regulator_enable() reference, Zephyr counts them
};

}  // namespace esphome::npm1300

#endif  // USE_ZEPHYR
