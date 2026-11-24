#pragma once

#include "esphome/core/component.h"
#include "esphome/core/defines.h"
#include "esphome/components/uart/uart.h"

#ifdef USE_SENSOR
#include "esphome/components/sensor/sensor.h"
#endif
#ifdef USE_BINARY_SENSOR
#include "esphome/components/binary_sensor/binary_sensor.h"
#endif

namespace esphome::ld2410s {

/// Hi-Link LD2410S report-frame parser (user manual v1.3, 7.2). Publishes on change only.
class LD2410SComponent final : public Component, public uart::UARTDevice {
 public:
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }

#ifdef USE_SENSOR
  SUB_SENSOR(target_distance)
#endif
#ifdef USE_BINARY_SENSOR
  SUB_BINARY_SENSOR(has_target)
#endif

 protected:
  void handle_frame_();

  // Header (4) + length (2) + payload + footer (4). The manual's payload is 37 bytes
  // (state 1 + distance 2 + reserved 34); allow some slack for firmware variants.
  static constexpr size_t MAX_FRAME = 64;
  uint8_t buffer_[MAX_FRAME];
  size_t pos_{0};
  uint32_t frames_{0};
  uint32_t bad_frames_{0};
  int last_state_{-1};
  int last_distance_{-1};
};

}  // namespace esphome::ld2410s
