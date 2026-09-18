#ifdef USE_ZEPHYR

#include "uart_component_zephyr.h"

#include <zephyr/drivers/uart.h>

#include "esphome/core/log.h"

namespace esphome::uart {

static const char *const TAG = "uart.zephyr";

static constexpr size_t DEFAULT_RX_BUFFER_SIZE = 256;

void ZephyrUARTComponent::setup() {
  if (this->dev_ == nullptr || !device_is_ready(this->dev_)) {
    ESP_LOGE(TAG, "UART device is not ready");
    this->mark_failed();
    return;
  }

  uart_config cfg{};
  cfg.baudrate = this->baud_rate_;
  switch (this->parity_) {
    case UART_CONFIG_PARITY_EVEN:
      cfg.parity = UART_CFG_PARITY_EVEN;
      break;
    case UART_CONFIG_PARITY_ODD:
      cfg.parity = UART_CFG_PARITY_ODD;
      break;
    default:
      cfg.parity = UART_CFG_PARITY_NONE;
      break;
  }
  cfg.stop_bits = this->stop_bits_ == 2 ? UART_CFG_STOP_BITS_2 : UART_CFG_STOP_BITS_1;
  switch (this->data_bits_) {
    case 5:
      cfg.data_bits = UART_CFG_DATA_BITS_5;
      break;
    case 6:
      cfg.data_bits = UART_CFG_DATA_BITS_6;
      break;
    case 7:
      cfg.data_bits = UART_CFG_DATA_BITS_7;
      break;
    default:
      cfg.data_bits = UART_CFG_DATA_BITS_8;
      break;
  }
  cfg.flow_ctrl = UART_CFG_FLOW_CTRL_NONE;

  // The devicetree `current-speed` enum can't express every baud rate (nRF54L's
  // stops at 230400 then 250000), so the real rate is always applied here.
  int err = uart_configure(this->dev_, &cfg);
  if (err != 0) {
    ESP_LOGE(TAG, "uart_configure(%u baud) failed: %d", this->baud_rate_, err);
    this->mark_failed();
    return;
  }

  size_t size = this->rx_buffer_size_ > 0 ? this->rx_buffer_size_ : DEFAULT_RX_BUFFER_SIZE;
  this->rx_storage_ = new uint8_t[size];  // NOLINT(cppcoreguidelines-owning-memory)
  ring_buf_init(&this->rx_ring_, size, this->rx_storage_);

  uart_irq_callback_user_data_set(this->dev_, &ZephyrUARTComponent::rx_isr_, this);
  uart_irq_rx_enable(this->dev_);
}

void ZephyrUARTComponent::rx_isr_(const device *dev, void *user_data) {
  auto *self = static_cast<ZephyrUARTComponent *>(user_data);
  uint8_t chunk[16];
  while (uart_irq_update(dev) && uart_irq_is_pending(dev)) {
    if (!uart_irq_rx_ready(dev))
      break;
    int n = uart_fifo_read(dev, chunk, sizeof(chunk));
    if (n <= 0)
      break;
    uint32_t stored = ring_buf_put(&self->rx_ring_, chunk, static_cast<uint32_t>(n));
    if (stored < static_cast<uint32_t>(n))
      self->rx_dropped_ += static_cast<uint32_t>(n) - stored;
  }
}

void ZephyrUARTComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "UART Bus:");
  LOG_PIN("  TX Pin: ", this->tx_pin_);
  LOG_PIN("  RX Pin: ", this->rx_pin_);
  if (this->rx_pin_ != nullptr) {
    ESP_LOGCONFIG(TAG, "  RX Buffer Size: %u", this->rx_buffer_size_);
  }
  ESP_LOGCONFIG(TAG,
                "  Baud Rate: %u baud\n"
                "  Data Bits: %u\n"
                "  Parity: %s\n"
                "  Stop bits: %u\n"
                "  RX bytes dropped (buffer full): %u",
                this->baud_rate_, this->data_bits_, LOG_STR_ARG(parity_to_str(this->parity_)), this->stop_bits_,
                static_cast<unsigned>(this->rx_dropped_));
}

void ZephyrUARTComponent::write_array(const uint8_t *data, size_t len) {
  if (this->dev_ == nullptr || this->is_failed())
    return;
  // uart_poll_out() blocks until each byte has been shifted out, so nothing is
  // left in flight when this returns.
  for (size_t i = 0; i < len; i++) {
    uart_poll_out(this->dev_, data[i]);
  }
#ifdef USE_UART_DEBUGGER
  for (size_t i = 0; i < len; i++) {
    this->debug_callback_.call(UART_DIRECTION_TX, data[i]);
  }
#endif
}

bool ZephyrUARTComponent::peek_byte(uint8_t *data) {
  if (!this->check_read_timeout_())
    return false;
  return ring_buf_peek(&this->rx_ring_, data, 1) == 1;
}

bool ZephyrUARTComponent::read_array(uint8_t *data, size_t len) {
  if (!this->check_read_timeout_(len))
    return false;
  uint32_t got = ring_buf_get(&this->rx_ring_, data, static_cast<uint32_t>(len));
#ifdef USE_UART_DEBUGGER
  for (uint32_t i = 0; i < got; i++) {
    this->debug_callback_.call(UART_DIRECTION_RX, data[i]);
  }
#endif
  return got == len;
}

size_t ZephyrUARTComponent::available() {
  if (this->rx_storage_ == nullptr)
    return 0;
  return ring_buf_size_get(&this->rx_ring_);
}

UARTFlushResult ZephyrUARTComponent::flush() {
  // write_array() is synchronous (uart_poll_out), there is no TX queue to drain.
  return UARTFlushResult::UART_FLUSH_RESULT_ASSUMED_SUCCESS;
}

}  // namespace esphome::uart
#endif  // USE_ZEPHYR
