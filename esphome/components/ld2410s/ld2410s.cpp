#include "ld2410s.h"
#include "esphome/core/log.h"

namespace esphome::ld2410s {

static const char *const TAG = "ld2410s";

static constexpr uint8_t HEADER[4] = {0xF4, 0xF3, 0xF2, 0xF1};
static constexpr uint8_t FOOTER[4] = {0xF8, 0xF7, 0xF6, 0xF5};

void LD2410SComponent::loop() {
  uint8_t byte;
  while (this->available() && this->read_byte(&byte)) {
    // Resynchronise on the 4-byte header.
    if (this->pos_ < 4) {
      if (byte != HEADER[this->pos_]) {
        this->pos_ = byte == HEADER[0] ? 1 : 0;
        if (this->pos_ == 1)
          this->buffer_[0] = byte;
        continue;
      }
    }
    this->buffer_[this->pos_++] = byte;
    if (this->pos_ < 6)
      continue;
    size_t length = this->buffer_[4] | (this->buffer_[5] << 8);
    size_t total = 6 + length + 4;
    if (length < 3 || total > MAX_FRAME) {
      this->bad_frames_++;
      this->pos_ = 0;
      continue;
    }
    if (this->pos_ < total)
      continue;
    if (memcmp(this->buffer_ + 6 + length, FOOTER, 4) == 0) {
      this->handle_frame_();
    } else {
      this->bad_frames_++;
    }
    this->pos_ = 0;
  }
}

void LD2410SComponent::handle_frame_() {
  this->frames_++;
  int state = this->buffer_[6];
  int distance = this->buffer_[7] | (this->buffer_[8] << 8);
#ifdef USE_BINARY_SENSOR
  if (this->has_target_binary_sensor_ != nullptr && state != this->last_state_)
    this->has_target_binary_sensor_->publish_state(state >= 2);
#endif
#ifdef USE_SENSOR
  if (this->target_distance_sensor_ != nullptr && distance != this->last_distance_)
    this->target_distance_sensor_->publish_state(distance);
#endif
  this->last_state_ = state;
  this->last_distance_ = distance;
}

void LD2410SComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "LD2410S: %" PRIu32 " frames, %" PRIu32 " rejected", this->frames_, this->bad_frames_);
#ifdef USE_BINARY_SENSOR
  LOG_BINARY_SENSOR("  ", "Has target", this->has_target_binary_sensor_);
#endif
#ifdef USE_SENSOR
  LOG_SENSOR("  ", "Target distance", this->target_distance_sensor_);
#endif
}

}  // namespace esphome::ld2410s
