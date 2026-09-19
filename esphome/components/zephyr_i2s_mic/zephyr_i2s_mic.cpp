#ifdef USE_ZEPHYR

#include "zephyr_i2s_mic.h"
#include "esphome/core/log.h"

#include <zephyr/drivers/i2s.h>
#include <zephyr/kernel.h>

#include <cmath>

namespace esphome::zephyr_i2s_mic {

static const char *const TAG = "zephyr_i2s_mic";

// One block = 256 stereo frames of 32-bit words (16 ms at 16 kHz). The driver keeps a few blocks queued, so the
// main loop has to come back within ~4 * 16 ms; if it doesn't, the stream is restarted (see loop()).
static constexpr size_t BLOCK_FRAMES = 256;
static constexpr size_t BLOCK_SIZE = BLOCK_FRAMES * 2 * sizeof(int32_t);
static constexpr size_t BLOCK_COUNT = 6;
// The first blocks after START carry the microphone's start-up transient (INMP441: ~2^18 clocks).
static constexpr uint8_t BLOCKS_TO_SKIP = 4;

K_MEM_SLAB_DEFINE_STATIC(i2s_rx_slab, BLOCK_SIZE, BLOCK_COUNT, sizeof(uint32_t));

bool ZephyrI2SMic::start_() {
  i2s_config cfg{};
  cfg.word_size = 32;
  cfg.channels = 2;
  cfg.format = I2S_FMT_DATA_FORMAT_I2S;
  cfg.options = I2S_OPT_BIT_CLK_CONTROLLER | I2S_OPT_FRAME_CLK_CONTROLLER;
  cfg.frame_clk_freq = this->sample_rate_;
  cfg.mem_slab = &i2s_rx_slab;
  cfg.block_size = BLOCK_SIZE;
  cfg.timeout = 0;  // i2s_read() must never block the main loop
  int err = i2s_configure(this->dev_, I2S_DIR_RX, &cfg);
  if (err != 0) {
    ESP_LOGE(TAG, "i2s_configure failed: %d", err);
    return false;
  }
  err = i2s_trigger(this->dev_, I2S_DIR_RX, I2S_TRIGGER_START);
  if (err != 0) {
    ESP_LOGE(TAG, "I2S start failed: %d", err);
    return false;
  }
  this->blocks_to_skip_ = BLOCKS_TO_SKIP;
  this->running_ = true;
  return true;
}

void ZephyrI2SMic::setup() {
  if (this->dev_ == nullptr || !device_is_ready(this->dev_)) {
    ESP_LOGE(TAG, "I2S device not ready");
    this->mark_failed();
    return;
  }
  if (!this->start_()) {
    this->mark_failed();
  }
}

void ZephyrI2SMic::accumulate_(const int32_t *frames, size_t frame_count) {
  const size_t slot = this->right_channel_ ? 1 : 0;
  for (size_t i = 0; i < frame_count; i++) {
    // The microphone sends 24 bits MSB-first in a 32-bit slot: keep the top 24, sign-extended.
    const double sample = static_cast<double>(frames[i * 2 + slot] >> 8);
    this->sum_ += sample;
    this->sum_squares_ += sample * sample;
  }
  this->sample_count_ += frame_count;
}

void ZephyrI2SMic::loop() {
  if (!this->running_) {
    return;
  }
  for (;;) {
    void *block = nullptr;
    size_t size = 0;
    int err = i2s_read(this->dev_, &block, &size);
    if (err == -EAGAIN) {
      return;  // nothing queued right now
    }
    if (err != 0) {
      // The driver ran out of buffers (loop starved) and went to its error state: drop and restart.
      this->restarts_++;
      ESP_LOGW(TAG, "I2S read failed (%d), restarting the stream (%u restarts so far)", err, this->restarts_);
      i2s_trigger(this->dev_, I2S_DIR_RX, I2S_TRIGGER_DROP);
      this->running_ = false;
      this->start_();
      return;
    }
    if (this->blocks_to_skip_ > 0) {
      this->blocks_to_skip_--;
    } else {
      this->accumulate_(static_cast<const int32_t *>(block), size / (2 * sizeof(int32_t)));
    }
    k_mem_slab_free(&i2s_rx_slab, block);
  }
}

void ZephyrI2SMic::update() {
  if (this->sample_count_ == 0) {
    return;
  }
  const double n = this->sample_count_;
  const double mean = this->sum_ / n;
  // Variance, i.e. the mean-square with the microphone's DC offset removed.
  const double mean_square = std::max(this->sum_squares_ / n - mean * mean, 0.0);
  this->sum_ = 0;
  this->sum_squares_ = 0;
  this->sample_count_ = 0;

  constexpr double FULL_SCALE = 8388608.0;  // 2^23
  // Floor at 1 LSB rms so digital silence reads about -138 dBFS instead of -inf.
  const double rms = std::max(std::sqrt(mean_square), 1.0);
  this->publish_state(static_cast<float>(20.0 * std::log10(rms / FULL_SCALE)) + this->offset_);
}

void ZephyrI2SMic::dump_config() {
  LOG_SENSOR("", "I2S microphone", this);
  ESP_LOGCONFIG(TAG,
                "  Sample rate: %u Hz\n"
                "  Channel: %s\n"
                "  Offset: %.1f dB\n"
                "  Stream restarts: %u",
                this->sample_rate_, this->right_channel_ ? "right" : "left", static_cast<double>(this->offset_),
                this->restarts_);
  LOG_UPDATE_INTERVAL(this);
}

}  // namespace esphome::zephyr_i2s_mic

#endif  // USE_ZEPHYR
