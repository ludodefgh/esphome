#pragma once

#ifdef USE_ZEPHYR

#include <zephyr/device.h>
#include <zephyr/sys/ring_buffer.h>

#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "uart_component.h"

namespace esphome::uart {

class ZephyrUARTComponent final : public UARTComponent, public Component {
 public:
  explicit ZephyrUARTComponent(const device *dev) : dev_(dev) {}

  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::BUS; }

  void write_array(const uint8_t *data, size_t len) override;

  bool peek_byte(uint8_t *data) override;
  bool read_array(uint8_t *data, size_t len) override;

  size_t available() override;
  UARTFlushResult flush() override;

 protected:
  void check_logger_conflict() override {}

  // Runs in interrupt context: moves whatever the UART driver has received
  // into rx_ring_ so no byte depends on the main loop being scheduled in time.
  static void rx_isr_(const device *dev, void *user_data);

  const device *dev_;
  ring_buf rx_ring_{};
  uint8_t *rx_storage_{nullptr};
  volatile uint32_t rx_dropped_{0};
};

}  // namespace esphome::uart
#endif  // USE_ZEPHYR
