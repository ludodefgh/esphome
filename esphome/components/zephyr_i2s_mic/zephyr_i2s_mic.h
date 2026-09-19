#pragma once

#ifdef USE_ZEPHYR

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"

#include <zephyr/device.h>

namespace esphome::zephyr_i2s_mic {

/// Sound level (RMS, dBFS + offset) of an I2S microphone read through Zephyr's I2S driver.
/// The microphone runs continuously; each update() publishes the level since the previous one.
class ZephyrI2SMic final : public sensor::Sensor, public PollingComponent {
 public:
  explicit ZephyrI2SMic(const device *dev) : dev_(dev) {}

  void setup() override;
  void loop() override;
  void update() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }

  void set_sample_rate(uint32_t sample_rate) { this->sample_rate_ = sample_rate; }
  void set_right_channel(bool right) { this->right_channel_ = right; }
  void set_offset(float offset) { this->offset_ = offset; }

 protected:
  bool start_();
  void accumulate_(const int32_t *frames, size_t frame_count);

  const device *dev_;
  uint32_t sample_rate_{16000};
  bool right_channel_{false};
  float offset_{0.0f};

  bool running_{false};
  uint8_t blocks_to_skip_{0};
  uint32_t restarts_{0};

  // Statistics over the current measurement window (24-bit samples, DC removed at publish time).
  double sum_{0};
  double sum_squares_{0};
  uint32_t sample_count_{0};
};

}  // namespace esphome::zephyr_i2s_mic

#endif  // USE_ZEPHYR
